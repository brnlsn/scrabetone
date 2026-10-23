#!/usr/bin/env python3
"""Generate docs/coords.json by dissolving GeoJSON features by catalog_id."""
import glob
import json
import os
from collections import defaultdict

MIN_LAT, MAX_LAT = 44.00, 44.25
MIN_LON, MAX_LON = 10.50, 10.90

# Enable La Doganaccia once its traced features have catalog_id properties.
AREAS = {"Multipass"}

SKIP_DIFFICULTY = {"extreme", "freeride"}
SKIP_AERIALWAY = {
    "razed",
    "abandoned",
    "construction",
    "station",
    "pylon",
    "no",
    "none",
}


def feature_type(properties):
    if properties.get("aerialway"):
        return "impianto"
    if properties.get("piste:type"):
        return "pista"
    return None


def skip_feature(properties, kind):
    if kind == "impianto":
        return str(properties.get("aerialway")).lower() in SKIP_AERIALWAY
    return (
        bool(properties.get("abandoned:piste"))
        or str(properties.get("piste:grooming")).lower() == "backcountry"
        or str(properties.get("piste:difficulty")).lower() in SKIP_DIFFICULTY
    )


def chain_segments(lines):
    """Dissolve line features that share an endpoint into continuous paths."""
    remaining = [list(line) for line in lines if len(line) >= 2]
    chains = []
    while remaining:
        chain = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            for index, line in enumerate(remaining):
                if line[0] == chain[-1]:
                    chain.extend(line[1:])
                elif line[-1] == chain[-1]:
                    chain.extend(reversed(line[:-1]))
                elif line[-1] == chain[0]:
                    chain = line[:-1] + chain
                elif line[0] == chain[0]:
                    chain = list(reversed(line[1:])) + chain
                else:
                    continue
                remaining.pop(index)
                changed = True
                break
        chains.append(chain)
    return chains


with open("catalogo.json", encoding="utf-8") as file:
    catalog = json.load(file)

catalog_by_id = {item["id"]: item for item in catalog}
segments_by_id = defaultdict(list)
source_by_id = {}
unmatched = []
type_mismatches = []
skipped = 0

for path in sorted(glob.glob("*.geojson")):
    with open(path, encoding="utf-8") as file:
        geojson = json.load(file)

    for feature in geojson.get("features", []):
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in ("LineString", "MultiLineString"):
            continue

        catalog_id = properties.get("catalog_id")
        item = catalog_by_id.get(catalog_id)
        if item is None:
            unmatched.append((path, catalog_id, properties.get("name")))
            continue

        kind = feature_type(properties)
        catalog_kind = "impianto" if item["tipo"] == "Impianti" else "pista"
        if kind != catalog_kind:
            type_mismatches.append((path, catalog_id, item["tipo"], kind))
            continue
        if skip_feature(properties, kind):
            skipped += 1
            continue

        coordinates = geometry["coordinates"]
        lines = [coordinates] if geometry["type"] == "LineString" else coordinates
        lines = [
            [[point[1], point[0]] for point in line if len(point) >= 2]
            for line in lines
        ]
        points = [point for line in lines for point in line]
        if not points:
            continue

        center_lat = sum(point[0] for point in points) / len(points)
        center_lon = sum(point[1] for point in points) / len(points)
        if not (
            MIN_LAT <= center_lat <= MAX_LAT
            and MIN_LON <= center_lon <= MAX_LON
            and item["area"] in AREAS
        ):
            continue

        first_source = source_by_id.setdefault(catalog_id, path)
        if first_source != path:
            continue
        segments_by_id[catalog_id].extend(lines)

if type_mismatches:
    details = ", ".join(
        f"{path}: {catalog_id} ({catalog_type} != {feature_type_value})"
        for path, catalog_id, catalog_type, feature_type_value in type_mismatches
    )
    raise SystemExit(f"GeoJSON catalog_id/type mismatch: {details}")

coordinates_by_id = {}
for catalog_id, lines in segments_by_id.items():
    chains = chain_segments(lines)
    points = [point for chain in chains for point in chain]
    if not points:
        continue
    coordinates_by_id[catalog_id] = {
        "lat": sum(point[0] for point in points) / len(points),
        "lon": sum(point[1] for point in points) / len(points),
        "geometry": points,
        "segments": chains,
    }

os.makedirs("docs", exist_ok=True)
with open("docs/coords.json", "w", encoding="utf-8") as file:
    json.dump(coordinates_by_id, file, ensure_ascii=False, indent=2)

active_catalog = [item for item in catalog if item["area"] in AREAS]
missing = [item for item in active_catalog if item["id"] not in coordinates_by_id]
print(
    f"AREAS: {', '.join(sorted(AREAS))} | "
    f"MATCHED: {len(coordinates_by_id)} | "
    f"CATALOG: {len(active_catalog)} | MISSING: {len(missing)}"
)
print(f"Skipped non-skiable features: {skipped}")

if missing:
    print("Catalog items without geometry:")
    for item in missing:
        print(f"  {item['id']:<14} [{item['tipo']:<11}] {item['nome_sito']}")

if unmatched:
    print(f"GeoJSON features without a valid catalog_id: {len(unmatched)}")
    for path, catalog_id, name in unmatched[:10]:
        print(f"  [{path}] catalog_id={catalog_id!r} name={name!r}")
    if len(unmatched) > 10:
        print(f"  ... and {len(unmatched) - 10} more")

print(f"Wrote docs/coords.json ({len(coordinates_by_id)} items)")
