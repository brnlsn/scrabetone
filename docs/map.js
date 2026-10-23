const listElement = document.querySelector("#item-list");
const listState = document.querySelector("#list-state");
const errorElement = document.querySelector("#error-message");
const refreshButton = document.querySelector("#refresh-button");
const searchInput = document.querySelector("#search");
const updatedElement = document.querySelector("#updated-at");
const resultCount = document.querySelector("#result-count");
const routeLayerIds = ["routes-piste", "routes-fondo", "routes-impianti"];
const hillshadeUrl =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}";
const itemColors = {
  Piste: { Aperto: "#25835b", Chiuso: "#c44e40" },
  "Piste fondo": { Aperto: "#167f83", Chiuso: "#bd742e" },
  Impianti: { Aperto: "#28699d", Chiuso: "#765395" },
};

let map;
let mapLoaded = false;
let allItems = [];
let layersByKey = new Map();
let selectedKey = null;
let activeStatus = "tutti";

function showError(error) {
  errorElement.hidden = false;
  errorElement.textContent = `Impossibile caricare i dati: ${error.message}`;
  listState.textContent = "Riprova tra poco oppure aggiorna i dati.";
}

async function getJson(filename) {
  const response = await fetch(new URL(filename, document.baseURI), {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`${filename}: HTTP ${response.status}`);
  }
  return response.json();
}

function isCoordinate(point) {
  return (
    Array.isArray(point) &&
    point.length >= 2 &&
    Number.isFinite(point[0]) &&
    Number.isFinite(point[1])
  );
}

function statusClass(item) {
  return item.stato === "Aperto" ? "is-open" : "is-closed";
}

function itemFeature(item) {
  const segments = Array.isArray(item.coordinates?.segments)
    ? item.coordinates.segments
    : [];
  const lines = segments.length
    ? segments
    : item.coordinates?.geometry
      ? [item.coordinates.geometry]
      : [];
  const coordinates = lines
    .map((line) =>
      line
        .filter(isCoordinate)
        .map(([latitude, longitude]) => [longitude, latitude]),
    )
    .filter((line) => line.length >= 2);

  if (coordinates.length) {
    return {
      type: "Feature",
      id: item.key,
      properties: {
        itemKey: item.key,
        id: item.id,
        name: item.nome,
        area: item.area,
        type: item.tipo,
        status: item.stato,
      },
      geometry: { type: "MultiLineString", coordinates },
    };
  }

  const { lat, lon } = item.coordinates ?? {};
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return {
    type: "Feature",
    id: item.key,
    properties: {
      itemKey: item.key,
      id: item.id,
      name: item.nome,
      area: item.area,
      type: item.tipo,
      status: item.stato,
    },
    geometry: { type: "Point", coordinates: [lon, lat] },
  };
}

function visibleItems() {
  const query = searchInput.value.trim().toLocaleLowerCase("it");
  return allItems.filter((item) => {
    const matchesStatus =
      activeStatus === "tutti" || item.stato === activeStatus;
    const searchable = `${item.nome} ${item.area} ${item.tipo}`
      .toLocaleLowerCase("it");
    return matchesStatus && searchable.includes(query);
  });
}

function updateMapFeatures(items) {
  if (!mapLoaded) return;
  map.getSource("routes").setData({
    type: "FeatureCollection",
    features: items.map(itemFeature).filter(Boolean),
  });
}

function renderList() {
  const items = visibleItems();
  const fragment = document.createDocumentFragment();
  const groups = new Map();

  for (const item of items) {
    if (!groups.has(item.tipo)) groups.set(item.tipo, new Map());
    const areas = groups.get(item.tipo);
    if (!areas.has(item.area)) areas.set(item.area, []);
    areas.get(item.area).push(item);
  }

  for (const [type, areas] of groups) {
    const typeHeading = document.createElement("h3");
    typeHeading.className = "group-heading";
    typeHeading.textContent = type;
    fragment.append(typeHeading);

    for (const [area, areaItems] of areas) {
      const areaHeading = document.createElement("h4");
      areaHeading.className = "area-heading";
      areaHeading.textContent = area;
      fragment.append(areaHeading);

      for (const item of areaItems) {
        const button = document.createElement("button");
        const dot = document.createElement("span");
        const copy = document.createElement("span");
        const name = document.createElement("span");
        const meta = document.createElement("span");
        const mapStatus = document.createElement("span");
        const state = document.createElement("span");
        const stateStyle = statusClass(item);
        const isMapped = layersByKey.has(item.key);

        button.type = "button";
        button.className = "item-row";
        button.dataset.key = item.key;
        button.setAttribute(
          "aria-label",
          `${item.nome}, ${item.stato.toLocaleLowerCase("it")}`,
        );
        if (item.key === selectedKey) button.classList.add("is-selected");

        dot.className = `status-dot ${stateStyle}`;
        copy.className = "item-copy";
        name.className = "item-name";
        name.textContent = item.nome;
        meta.className = "item-meta";
        meta.textContent = item.tipo;
        if (!isMapped) {
          mapStatus.className = "item-map-status";
          mapStatus.textContent = "Da mappare";
          mapStatus.title = "Geometria non ancora disponibile";
        }
        state.className = `item-status ${stateStyle}`;
        state.textContent = item.stato;
        copy.append(name, meta);
        if (!isMapped) copy.append(mapStatus);
        button.append(dot, copy, state);
        button.addEventListener("click", () => selectItem(item));
        fragment.append(button);
      }
    }
  }

  listElement.replaceChildren(fragment);
  listState.hidden = items.length > 0;
  if (items.length === 0) {
    listState.textContent =
      allItems.length === 0
        ? "Nessun dato disponibile."
        : "Nessun risultato. Prova a cambiare i filtri.";
  }
  resultCount.textContent = `${items.length} ${
    items.length === 1 ? "elemento" : "elementi"
  }`;
  updateMapFeatures(items);
}

function createPopup(item) {
  const content = document.createElement("div");
  const title = document.createElement("p");
  const subtitle = document.createElement("p");
  title.className = "popup-title";
  subtitle.className = "popup-subtitle";
  title.textContent = item.nome;
  subtitle.textContent = `${item.area} · ${item.tipo} · ${item.stato}`;
  content.append(title, subtitle);
  return content;
}

function selectItem(item, mapPoint) {
  selectedKey = item.key;
  listElement.querySelectorAll(".item-row").forEach((row) => {
    row.classList.toggle("is-selected", row.dataset.key === selectedKey);
  });

  const feature = itemFeature(item);
  if (!mapLoaded || !feature) return;
  const bounds = new maplibregl.LngLatBounds();
  const geometry = feature.geometry;
  const lines =
    geometry.type === "Point"
      ? [[geometry.coordinates]]
      : geometry.coordinates;
  for (const line of lines) {
    for (const coordinate of line) bounds.extend(coordinate);
  }
  if (bounds.isEmpty()) return;

  const center = mapPoint ?? bounds.getCenter();
  if (!mapPoint) {
    map.fitBounds(bounds, {
      padding: { top: 90, right: 70, bottom: 90, left: 70 },
      maxZoom: 15.5,
      duration: 650,
    });
  }
  new maplibregl.Popup({ closeButton: true, closeOnClick: false, offset: 12 })
    .setLngLat(center)
    .setDOMContent(createPopup(item))
    .addTo(map);
}

function setStatusFilter(button) {
  activeStatus = button.dataset.status;
  document.querySelectorAll(".filter-button").forEach((filter) => {
    const active = filter === button;
    filter.classList.toggle("is-active", active);
    filter.setAttribute("aria-pressed", String(active));
  });
  renderList();
}

function setUpdatedAt(value) {
  const date = new Date(value);
  updatedElement.textContent = Number.isNaN(date.getTime())
    ? "Aggiornamento non disponibile"
    : `Aggiornato ${new Intl.DateTimeFormat("it-IT", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date)}`;
}

function fitAllRoutes() {
  if (!mapLoaded || layersByKey.size === 0) return;
  const bounds = new maplibregl.LngLatBounds();
  for (const item of layersByKey.values()) {
    const feature = itemFeature(item);
    if (!feature) continue;
    const geometry = feature.geometry;
    const lines =
      geometry.type === "Point"
        ? [[geometry.coordinates]]
        : geometry.coordinates;
    for (const line of lines) {
      for (const coordinate of line) bounds.extend(coordinate);
    }
  }
  if (!bounds.isEmpty()) {
    map.fitBounds(bounds, {
      padding: { top: 70, right: 60, bottom: 70, left: 60 },
      maxZoom: 13.5,
      duration: 0,
    });
  }
}

async function loadData() {
  refreshButton.disabled = true;
  errorElement.hidden = true;
  listState.hidden = false;
  listState.textContent = "Caricamento piste e impianti…";
  try {
    const [statusData, coordinateData] = await Promise.all([
      getJson("impianti.json"),
      getJson("coords.json"),
    ]);
    if (!Array.isArray(statusData.elementi)) {
      throw new Error("il formato del file impianti.json non è valido");
    }

    allItems = statusData.elementi
      .filter(
        (item) =>
          item &&
          typeof item.id === "string" &&
          typeof item.nome === "string" &&
          typeof item.area === "string" &&
          typeof item.tipo === "string" &&
          typeof item.stato === "string",
      )
      .map((item, index) => ({
        ...item,
        key: `${item.id}-${index}`,
        coordinates: item.id === "unknown" ? undefined : coordinateData[item.id],
      }))
      .sort(
        (a, b) =>
          a.tipo.localeCompare(b.tipo, "it") ||
          a.area.localeCompare(b.area, "it") ||
          a.nome.localeCompare(b.nome, "it"),
      );

    layersByKey = new Map(
      allItems.filter((item) => itemFeature(item)).map((item) => [item.key, item]),
    );
    const openCount = allItems.filter((item) => item.stato === "Aperto").length;
    const mappedCount = layersByKey.size;
    document.querySelector("#open-count").textContent = String(openCount);
    document.querySelector("#mapped-count").textContent = String(mappedCount);
    document.querySelector("#total-count").textContent = String(allItems.length);
    document.querySelector("#unmapped-count").textContent =
      allItems.length > mappedCount
        ? `${allItems.length - mappedCount} senza traccia`
        : "";
    setUpdatedAt(statusData.aggiornato);
    renderList();
  } catch (error) {
    showError(error);
  } finally {
    refreshButton.disabled = false;
  }
}

function addRouteLayers() {
  map.addSource("routes", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  });

  const firstStyleLayer = map
    .getStyle()
    .layers.find((layer) => layer.id !== "background")?.id;
  const firstSymbolLayer = map
    .getStyle()
    .layers.find((layer) => layer.type === "symbol")?.id;
  map.addSource("terrain-hillshade", {
    type: "raster",
    tiles: [hillshadeUrl],
    tileSize: 256,
    maxzoom: 19,
    attribution:
      'Hillshade © <a href="https://goto.arcgisonline.com/maps/Elevation/World_Hillshade" target="_blank" rel="noreferrer">Esri</a>',
  });
  map.addLayer(
    {
      id: "terrain-hillshade",
      type: "raster",
      source: "terrain-hillshade",
      paint: {
        "raster-opacity": 0.17,
        "raster-saturation": -0.2,
      },
    },
    firstStyleLayer,
  );

  const layerStyles = [
    { id: "routes-piste", type: "Piste", width: 4.5 },
    { id: "routes-fondo", type: "Piste fondo", width: 3.8, dash: [2.5, 1.5] },
    { id: "routes-impianti", type: "Impianti", width: 3.2, dash: [1.5, 1.5] },
  ];
  for (const style of layerStyles) {
    map.addLayer(
      {
        id: style.id,
        type: "line",
        source: "routes",
        filter: ["==", ["get", "type"], style.type],
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": [
            "match",
            ["get", "status"],
            "Aperto",
            itemColors[style.type].Aperto,
            itemColors[style.type].Chiuso,
          ],
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            10,
            style.width * 0.65,
            15,
            style.width,
            18,
            style.width + 1.5,
          ],
          "line-opacity": 0.94,
          ...(style.dash ? { "line-dasharray": style.dash } : {}),
        },
      },
      firstSymbolLayer,
    );
  }

  for (const type of ["Piste", "Piste fondo", "Impianti"]) {
    map.addLayer(
      {
        id: `route-points-${type}`,
        type: "circle",
        source: "routes",
        filter: [
          "all",
          ["==", ["geometry-type"], "Point"],
          ["==", ["get", "type"], type],
        ],
        paint: {
          "circle-radius": 6,
          "circle-color": [
            "match",
            ["get", "status"],
            "Aperto",
            itemColors[type].Aperto,
            itemColors[type].Chiuso,
          ],
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1.5,
        },
      },
      firstSymbolLayer,
    );
  }
}

function start() {
  if (!window.maplibregl) {
    showError(new Error("la mappa non è disponibile. Verifica la connessione."));
    return;
  }

  map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [10.66, 44.145],
    zoom: 12,
    maxZoom: 18,
    attributionControl: false,
    cooperativeGestures: true,
  });
  map.addControl(
    new maplibregl.NavigationControl({ showCompass: false }),
    "top-right",
  );
  map.addControl(
    new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }),
    "bottom-left",
  );
  map.addControl(
    new maplibregl.AttributionControl({
      compact: false,
      customAttribution:
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · Hillshade © <a href="https://goto.arcgisonline.com/maps/Elevation/World_Hillshade" target="_blank" rel="noreferrer">Esri</a>',
    }),
    "bottom-right",
  );

  map.on("load", () => {
    mapLoaded = true;
    addRouteLayers();
    renderList();
    fitAllRoutes();
  });
  map.on("click", (event) => {
    const features = map.queryRenderedFeatures(event.point, {
      layers: [...routeLayerIds, "route-points-Piste", "route-points-Piste fondo", "route-points-Impianti"],
    });
    const itemKey = features[0]?.properties.itemKey;
    const item = allItems.find((candidate) => candidate.key === itemKey);
    if (item) selectItem(item, event.lngLat);
  });
  map.on("mouseenter", routeLayerIds, () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", routeLayerIds, () => {
    map.getCanvas().style.cursor = "";
  });

  refreshButton.addEventListener("click", loadData);
  searchInput.addEventListener("input", renderList);
  document.querySelectorAll(".filter-button").forEach((button) => {
    button.addEventListener("click", () => setStatusFilter(button));
  });
  loadData();
}

start();
