import json
import os
import re
import glob

def normalizza(testo):
    if not testo:
        return ""
    testo = str(testo).lower()
    testo = re.sub(r'[^a-zàèéìòù\s]', '', testo)
    return " ".join(testo.split())

def main():
    with open("catalogo.json", "r", encoding="utf-8") as f:
        catalogo = json.load(f)

    match_dict = {}
    for c in catalogo:
        match_dict[normalizza(c["nome_osm"])] = c["id"]
        match_dict[normalizza(c["nome_sito"])] = c["id"]
        
        num_match = re.match(r'^(\d+[a-z]?)\.', c["nome_sito"])
        if num_match:
            match_dict[f"ref_{num_match.group(1)}"] = c["id"]

    coords = {}
    files = glob.glob("*.geojson") 
    
    if not files:
        print("❌ Nessun file .geojson trovato.")
        return

    trovati = 0
    non_trovati = []

    MIN_LAT, MAX_LAT = 44.05, 44.20
    MIN_LON, MAX_LON = 10.55, 10.75

    for file_path in files:
        print(f"Elaboro {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)

        for feature in geojson["features"]:
            props = feature.get("properties", {})
            
            if props.get("aerialway") in ["abandoned", "station"]:
                continue
                
            geom = feature.get("geometry", {})
            if not geom: continue
                
            coords_arr = geom.get("coordinates", [])
            tipo_geom = geom.get("type")

            geometry = []
            if tipo_geom == "LineString":
                geometry = [[p[1], p[0]] for p in coords_arr]
            elif tipo_geom == "MultiLineString":
                for line in coords_arr:
                    geometry.extend([[p[1], p[0]] for p in line])
            else:
                continue # Per ora ignoriamo poligoni
            
            if not geometry: continue

            center_lat = sum(p[0] for p in geometry) / len(geometry)
            center_lon = sum(p[1] for p in geometry) / len(geometry)

            if not (MIN_LAT <= center_lat <= MAX_LAT and MIN_LON <= center_lon <= MAX_LON):
                continue

            nome = props.get("name")
            # Cerca il numero sia negli impianti (ref) che nelle piste (piste:ref)
            ref = props.get("ref") or props.get("piste:ref")
            
            el_id = None
            
            if ref and f"ref_{ref}" in match_dict:
                el_id = match_dict[f"ref_{ref}"]
            
            if not el_id and nome:
                nome_norm = normalizza(nome)
                if nome_norm in match_dict:
                    el_id = match_dict[nome_norm]
            
            if not el_id:
                continue # Se non è nel catalogo, lo ignoriamo (es. piste non segnalate dal sito)

            coords[el_id] = {
                "lat": center_lat,
                "lon": center_lon,
                "geometry": geometry
            }
            trovati += 1

    os.makedirs("docs", exist_ok=True)
    with open("docs/coords.json", "w", encoding="utf-8") as f:
        json.dump(coords, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Esportati {trovati} elementi (piste e impianti) in docs/coords.json")

if __name__ == "__main__":
    main()