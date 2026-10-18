import json
from collections import Counter

for fn in ("piste_impianti.geojson", "piste_abetone.geojson", "impianti_abetone.geojson"):
    gj = json.load(open(fn, encoding="utf-8"))
    feats = gj["features"]
    print(fn, Counter((f.get("geometry") or {}).get("type") for f in feats))
    for f in feats:
        t = (f.get("geometry") or {}).get("type")
        if t not in ("LineString", "MultiLineString"):
            print("   non-linea:", t, (f.get("properties") or {}).get("name"))