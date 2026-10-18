import json
import re

# Carica le geometrie estratte da OSM (offline)
with open("piste_impianti.geojson", "r", encoding="utf-8") as f:
    geojson = json.load(f)

def normalizza(testo):
    testo = testo.lower()
    testo = re.sub(r'[^a-zàèéìòù\s]', '', testo)
    return " ".join(testo.split())

osm_features = {}
for feature in geojson["features"]:
    props = feature.get("properties", {})
    nome = props.get("name")
    if not nome:
        continue

    geom = feature.get("geometry", {})
    coords = geom.get("coordinates", [])
    tipo_geom = geom.get("type")

    geometry = []
    if tipo_geom == "LineString":
        geometry = [[p[1], p[0]] for p in coords]  # GeoJSON è [lon, lat]
    elif tipo_geom == "MultiLineString":
        for line in coords:
            geometry.extend([[p[1], p[0]] for p in line])
    elif tipo_geom == "Point":
        geometry = []  # punto isolato, niente polilinea

    # Calcola il centro (media dei punti)
    if geometry:
        center_lat = sum(p[0] for p in geometry) / len(geometry)
        center_lon = sum(p[1] for p in geometry) / len(geometry)
    else:
        # Se è un punto, usa le coordinate direttamente
        if tipo_geom == "Point":
            center_lon, center_lat = coords[0], coords[1]
        else:
            continue

    osm_features[normalizza(nome)] = {
        "center": [center_lat, center_lon],
        "geometry": geometry
    }

print(f"Trovati {len(osm_features)} elementi con nome nel file OSM locale.")

# Carica il tuo JSON degli stati
with open("docs/impianti.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Dizionario manuale per gli elementi che OSM non ha (o ha con nomi diversi)
MANUAL_COORDS = {
    "13. Tapis Roulant Ovovia": [44.144, 10.665],
    "Faggio di Maria": [44.124, 10.652],
    "Angela": [44.125, 10.655],
    "Raccordino": [44.126, 10.653],
    "Panoramica": [44.127, 10.654],
    "Anello Lazzi – Doganaccia": [44.122, 10.650],
    "Anello Croce – Arcana": [44.135, 10.660],
    "Cutigliano – Doganaccia* (*sab e dom 8-12:50 e 14-17)": [44.122, 10.648],
    "Doganaccia – Croce Arcana": [44.136, 10.661],
    "Tapis Roulant 1": [44.122, 10.649],
    "Tapis Roulant 2": [44.123, 10.650]
}

trovati_osm = 0
trovati_manuali = 0
non_trovati = []

for el in data["elementi"]:
    nome_originale = el["nome"]
    nome_norm = normalizza(nome_originale)

    trovato = False

    # 1. Match esatto o parziale con OSM
    if nome_norm in osm_features:
        feat = osm_features[nome_norm]
        el["lat"], el["lon"] = feat["center"]
        if feat["geometry"]:
            el["geometry"] = feat["geometry"]
        trovati_osm += 1
        trovato = True
    else:
        for osm_nome, feat in osm_features.items():
            if osm_nome in nome_norm or nome_norm in osm_nome:
                el["lat"], el["lon"] = feat["center"]
                if feat["geometry"]:
                    el["geometry"] = feat["geometry"]
                trovati_osm += 1
                trovato = True
                break

    # 2. Fallback manuale
    if not trovato:
        if nome_originale in MANUAL_COORDS:
            el["lat"] = MANUAL_COORDS[nome_originale][0]
            el["lon"] = MANUAL_COORDS[nome_originale][1]
            trovati_manuali += 1
        else:
            non_trovati.append(nome_originale)

# Salva il JSON aggiornato
with open("docs/impianti.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ Matchati da OSM: {trovati_osm}")
print(f"✅ Matchati manualmente: {trovati_manuali}")
print(f"⚠️ Ancora non trovati: {len(non_trovati)}")
for n in non_trovati:
    print(f"  - {n}")