#!/usr/bin/env python3
"""
Genera docs/coords.json unendo catalogo.json e i GeoJSON esportati da QGIS/OSM.

Regole (nessun fuzzy matching, nessuna ambiguità):
  1. Piste e impianti sono SEMPRE separati: il tipo viene dalle proprietà OSM
     (aerialway=* -> impianto, piste:type=* -> pista), mai dal nome o dal numero.
  2. Piste    -> si usa SOLO  piste:ref
     Impianti -> si usa  ref  (ripiego: aerialway:ref, perché in OSM molti
                 impianti dell'Abetone hanno il numero solo lì)
  3. Il numero viene confrontato con il numero nell'id del catalogo
     (mp_pista_12a -> "12a", mp_imp_05 -> "5"), nello spazio (area, tipo, numero).
     Quindi pista 11 e impianto 11 non si incontrano mai.
  4. La Doganaccia nel catalogo non ha numeri: lì si matcha per nome normalizzato,
     sempre dentro (area, tipo). (Per ora disattivata: vedi AREAS.)
  5. Tratti da escludere (backcountry, freeride, extreme, abbandonati, razed,
     in costruzione, stazioni, piloni) vengono scartati.
  6. Eccezioni manuali in OVERRIDES (osm_id -> id catalogo).
  7. Ogni id prende la geometria dal PRIMO file che lo fornisce (in ordine
     alfabetico di nome file): un file successivo non può sovrascriverlo né
     duplicarlo.
"""
import glob
import json
import os
import re
import unicodedata
from collections import defaultdict

# ----------------------------------------------------------------------------
# CONFIGURAZIONE
# ----------------------------------------------------------------------------

# Riquadro geografico: le feature con il centro fuori da qui vengono ignorate
MIN_LAT, MAX_LAT = 44.00, 44.25
MIN_LON, MAX_LON = 10.50, 10.90

# A est di questa longitudine siamo alla Doganaccia, a ovest all'Abetone
DOGANACCIA_MIN_LON = 10.70

# Aree da elaborare. Aggiungi "La Doganaccia" quando sarà il momento.
AREAS = {"Multipass"}

# osm_id (stringa) -> id catalogo. Per i casi in cui il numero OSM non coincide.
OVERRIDES = {
    "1338722684": "mp_pista_18b",  # Campo Scuola Ovovia: in OSM ref 19a, sul sito 18b
}

# Piste con queste difficoltà non sono piste battute: si scartano
SKIP_DIFFICULTY = {"extreme", "freeride"}
# Valori di aerialway che non sono impianti in funzione
SKIP_AERIALWAY = {"razed", "abandoned", "construction", "station", "pylon", "no", "none"}


# ----------------------------------------------------------------------------
# FUNZIONI DI SUPPORTO
# ----------------------------------------------------------------------------

def norm(s):
    """Testo normalizzato: minuscolo, senza accenti né punteggiatura."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_ref(r):
    """Numero normalizzato: '05' -> '5', '12A' -> '12a', vuoto -> None."""
    if r is None:
        return None
    r = str(r).strip().lower()
    if not r:
        return None
    return re.sub(r"^0+(?=\d)", "", r)


def tipo_of_catalog(c):
    """Tipo di una voce del catalogo: 'impianto' oppure 'pista'.
    Il catalogo usa "Piste", "Piste fondo", "Impianti".
    (Attenzione: "pista" NON è contenuto in "piste", quindi si testa 'impiant'.)"""
    return "impianto" if "impiant" in c["tipo"].lower() else "pista"


def ref_from_id(cid):
    """Numero ricavato dall'id del catalogo.
    mp_pista_12a -> '12a'; mp_imp_05 -> '5'; dg_* -> None (nessun numero)."""
    if not cid.startswith("mp_"):
        return None
    return norm_ref(cid.rsplit("_", 1)[-1])


def tipo_of_feature(props):
    """Tipo di una feature OSM, deciso solo dalle proprietà (mai da nome/numero)."""
    if props.get("aerialway"):
        return "impianto"
    if props.get("piste:type"):
        return "pista"
    return None


def feature_ref(props, tipo):
    """Numero della feature: piste:ref per le piste; ref (poi aerialway:ref) per gli impianti."""
    if tipo == "pista":
        return norm_ref(props.get("piste:ref"))
    return norm_ref(props.get("ref")) or norm_ref(props.get("aerialway:ref"))


def skip_feature(props, tipo):
    """True se la feature non va disegnata (fuori servizio, freeride, ecc.)."""
    if tipo == "impianto":
        return str(props.get("aerialway")).lower() in SKIP_AERIALWAY
    if props.get("abandoned:piste"):
        return True
    if str(props.get("piste:grooming")).lower() == "backcountry":
        return True
    if str(props.get("piste:difficulty")).lower() in SKIP_DIFFICULTY:
        return True
    return False


def chain_segments(segs):
    """Unisce i tratti che si toccano agli estremi in polilinee continue.
    Restituisce una lista di catene (una per ogni gruppo di tratti connessi)."""
    segs = [list(s) for s in segs if len(s) >= 2]
    chains = []
    while segs:
        chain = segs.pop(0)
        changed = True
        while changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == chain[-1]:            # s continua la catena
                    chain += s[1:]
                elif s[-1] == chain[-1]:         # s va girato e aggiunto in coda
                    chain += s[::-1][1:]
                elif s[-1] == chain[0]:          # s precede la catena
                    chain = s[:-1] + chain
                elif s[0] == chain[0]:           # s va girato e messo in testa
                    chain = s[::-1][:-1] + chain
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        chains.append(chain)
    return chains


# ----------------------------------------------------------------------------
# CATALOGO: costruzione degli indici di ricerca
# ----------------------------------------------------------------------------
with open("catalogo.json", encoding="utf-8") as f:
    catalogo = json.load(f)

by_ref = {}                   # (area, tipo, numero) -> id        [Abetone]
by_name = defaultdict(list)   # (area, tipo, nome normalizzato) -> [id]  [Doganaccia]
for c in catalogo:
    tipo = tipo_of_catalog(c)
    r = ref_from_id(c["id"])
    if r:
        by_ref[(c["area"], tipo, r)] = c["id"]
    else:
        for field in ("nome_osm", "nome_sito"):
            k = (c["area"], tipo, norm(c.get(field)))
            if c["id"] not in by_name[k]:
                by_name[k].append(c["id"])

# ----------------------------------------------------------------------------
# GEOJSON: lettura e assegnazione delle feature agli id del catalogo
# ----------------------------------------------------------------------------
segments = defaultdict(list)   # id -> lista di tratti (ognuno è una lista di [lat, lon])
source_of = {}                 # id -> file da cui è arrivata la geometria
unmatched = []                 # feature valide ma senza id nel catalogo
skipped = 0                    # feature scartate (extreme, abbandonate, ecc.)

for fp in sorted(glob.glob("*.geojson")):
    fname = os.path.basename(fp)
    with open(fp, encoding="utf-8") as f:
        gj = json.load(f)

    for feat in gj.get("features", []):
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}

        # Si usano solo linee (punti e poligoni non servono)
        if geom.get("type") not in ("LineString", "MultiLineString"):
            continue

        # 1) tipo deciso dalle proprietà OSM; poi scarto dei tratti non sciabili
        tipo = tipo_of_feature(props)
        if tipo is None or skip_feature(props, tipo):
            skipped += 1
            continue

        # 2) coordinate GeoJSON [lon, lat] -> [lat, lon]
        arr = geom["coordinates"]
        lines = [arr] if geom["type"] == "LineString" else arr
        lines = [[[p[1], p[0]] for p in ln if len(p) >= 2] for ln in lines]
        pts = [p for ln in lines for p in ln]
        if not pts:
            continue

        # 3) centro della feature: deve stare nel riquadro geografico
        clat = sum(p[0] for p in pts) / len(pts)
        clon = sum(p[1] for p in pts) / len(pts)
        if not (MIN_LAT <= clat <= MAX_LAT and MIN_LON <= clon <= MAX_LON):
            continue

        # 4) area dedotta dalla longitudine; si elaborano solo le aree in AREAS
        area = "La Doganaccia" if clon >= DOGANACCIA_MIN_LON else "Multipass"
        if area not in AREAS:
            continue

        osm_id = str(props.get("osm_id"))

        # 5) assegnazione: prima gli override manuali, poi numero (Abetone)
        #    o nome (Doganaccia)
        cid = OVERRIDES.get(osm_id)
        if cid is None:
            ref = feature_ref(props, tipo)
            if area == "Multipass":
                cid = by_ref.get((area, tipo, ref)) if ref else None
            else:
                ids = by_name.get((area, tipo, norm(props.get("name"))), [])
                cid = ids[0] if len(ids) == 1 else None

        if cid is None:
            unmatched.append((fname, tipo, area, props.get("name"),
                              feature_ref(props, tipo), osm_id))
            continue

        # 6) un id prende la geometria dal primo file che lo fornisce
        if source_of.setdefault(cid, fname) != fname:
            continue

        segments[cid].extend(lines)

# ----------------------------------------------------------------------------
# OUTPUT: docs/coords.json
# ----------------------------------------------------------------------------
coords = {}
for cid, segs in segments.items():
    chains = chain_segments(segs)
    flat = [p for ch in chains for p in ch]
    coords[cid] = {
        "lat": sum(p[0] for p in flat) / len(flat),   # centro, per i marker
        "lon": sum(p[1] for p in flat) / len(flat),
        "geometry": flat,      # lista piatta: compatibile con l'app attuale
        "segments": chains,    # polilinee separate: da usare per disegnare senza salti
    }

os.makedirs("docs", exist_ok=True)
with open("docs/coords.json", "w", encoding="utf-8") as f:
    json.dump(coords, f, ensure_ascii=False, indent=2)

# ----------------------------------------------------------------------------
# REPORT
# ----------------------------------------------------------------------------
catalogo_area = [c for c in catalogo if c["area"] in AREAS]
missing = [c for c in catalogo_area if c["id"] not in coords]

print("=" * 72)
print(f"  AREE: {', '.join(sorted(AREAS))}")
print(f"  MATCHATI: {len(coords)}  |  CATALOGO (aree attive): {len(catalogo_area)}"
      f"  |  SENZA GEOMETRIA: {len(missing)}")
print(f"  Tratti scartati (backcountry/extreme/abbandonati/...): {skipped}")
print("=" * 72)

print(f"\n--- CATALOGO SENZA GEOMETRIA ({len(missing)}) ---")
for c in missing:
    print(f"  {c['id']:<14} [{c['tipo']:<11}] {c['nome_sito']}")

print(f"\n--- FEATURE GEOJSON NON ASSEGNATE ({len(unmatched)}) ---")
seen = set()
for fn, tipo, area, name, ref, oid in unmatched:
    key = (tipo, area, name, ref)
    if key in seen:        # una riga sola per ogni combinazione uguale
        continue
    seen.add(key)
    print(f"  [{fn}] {tipo:<8} {area:<14} name={name!r} ref={ref!r} (osm {oid})")

print(f"\nOK docs/coords.json scritto ({len(coords)} elementi)")