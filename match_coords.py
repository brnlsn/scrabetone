import json
import re
import os
import requests
import time

BBOX = "44.08,10.58,44.20,10.75"

# Lista di server alternativi per Overpass
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

CACHE_FILE = "osm_cache.json"

QUERY = f"""
[out:json][timeout:60];
(
  way["piste:type"]({BBOX});
  way["aerialway"]({BBOX});
  node["aerialway"]({BBOX});
);
out geom;
"""

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

def normalizza(testo):
    testo = testo.lower()
    testo = re.sub(r'[^a-zàèéìòù\s]', '', testo)
    return " ".join(testo.split())

def scarica_da_overpass():
    # Se abbiamo già i dati in cache, li usiamo (evita di stressare i server)
    if os.path.exists(CACHE_FILE):
        print(f"✓ Uso i dati OSM salvati in {CACHE_FILE}")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print("Scarico dati da OpenStreetMap (Overpass)...")
    headers = {
        "User-Agent": "Scrabetone/1.0 (https://github.com/brnlsn/scrabetone)",
        "Accept": "application/json"
    }
    
    for server in SERVERS:
        print(f"  Provo {server} ...")
        try:
            r = requests.post(server, data={"data": QUERY}, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json().get("elements", [])
                # Salva in cache per le prossime esecuzioni
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                print("  ✅ Download completato e salvato in cache!")
                return data
            else:
                print(f"  ❌ Errore {r.status_code}. Provo il prossimo server...")
        except Exception as e:
            print(f"  ❌ Timeout/Errore: {e}. Provo il prossimo server...")
        
        time.sleep(1) # Piccola pausa prima di riprovare con un altro server

    raise Exception("Tutti i server Overpass hanno fallito. Riprova più tardi.")

def main():
    osm_data = scarica_da_overpass()

    osm_features = {}
    for el in osm_data:
        tags = el.get("tags", {})
        nome = tags.get("name")
        if not nome: continue

        geometry = []
        if "geometry" in el:
            geometry = [[p["lat"], p["lon"]] for p in el["geometry"]]

        if geometry:
            center_lat = sum(p[0] for p in geometry) / len(geometry)
            center_lon = sum(p[1] for p in geometry) / len(geometry)
        elif "lat" in el:
            center_lat, center_lon = el["lat"], el["lon"]
        elif "center" in el:
            center_lat, center_lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue

        osm_features[normalizza(nome)] = {
            "center": [center_lat, center_lon],
            "geometry": geometry
        }

    print(f"Trovati {len(osm_features)} elementi con nome su OSM.")

    with open("docs/impianti.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    non_trovati = []
    trovati_osm = 0
    trovati_manuali = 0
    geometrie_aggiunte = 0

    for el in data["elementi"]:
        nome_originale = el["nome"]
        nome_norm = normalizza(nome_originale)
        
        trovato = False
        
        if nome_norm in osm_features:
            feat = osm_features[nome_norm]
            el["lat"], el["lon"] = feat["center"]
            if feat["geometry"]: 
                el["geometry"] = feat["geometry"]
                geometrie_aggiunte += 1
            trovati_osm += 1
            trovato = True
        else:
            for osm_nome, feat in osm_features.items():
                if osm_nome in nome_norm or nome_norm in osm_nome:
                    el["lat"], el["lon"] = feat["center"]
                    if feat["geometry"]: 
                        el["geometry"] = feat["geometry"]
                        geometrie_aggiunte += 1
                    trovati_osm += 1
                    trovato = True
                    break
            
            if not trovato:
                if nome_originale in MANUAL_COORDS:
                    el["lat"] = MANUAL_COORDS[nome_originale][0]
                    el["lon"] = MANUAL_COORDS[nome_originale][1]
                    trovati_manuali += 1
                else:
                    non_trovati.append(nome_originale)

    with open("docs/impianti.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Matchati da OSM: {trovati_osm} (di cui {geometrie_aggiunte} con geometria)")
    print(f"✅ Matchati manualmente: {trovati_manuali}")
    print(f"⚠️ Ancora non trovati: {len(non_trovati)}")

if __name__ == "__main__":
    main()