import json

def main():
    with open("docs/impianti.json", "r", encoding="utf-8") as f:
        impianti = json.load(f)["elementi"]
    
    with open("docs/coords.json", "r", encoding="utf-8") as f:
        coords = json.load(f)

    print("=== DIAGNOSI DATI ===\n")
    
    mancanti_coord = []
    id_sconosciuti = []

    for el in impianti:
        el_id = el.get("id")
        
        # 1. Controlla se lo scraper non ha trovato l'ID
        if el_id == "unknown" or not el_id:
            id_sconosciuti.append(f"{el['nome']} ({el['tipo']})")
        # 2. Controlla se l'ID esiste ma non ha geometria in coords.json
        elif el_id not in coords:
            mancanti_coord.append(f"{el['nome']} (ID: {el_id})")

    if id_sconosciuti:
        print(f"⚠️ Elementi senza ID (controlla catalogo.json):")
        for x in id_sconosciuti:
            print(f"  - {x}")
    else:
        print("✅ Tutti gli elementi hanno un ID.")

    print("\n")
    
    if mancanti_coord:
        print(f"⚠️ Elementi senza geometria (mancano in coords.json / QGIS):")
        for x in mancanti_coord:
            print(f"  - {x}")
    else:
        print("✅ Tutti gli elementi hanno una geometria.")

if __name__ == "__main__":
    main()