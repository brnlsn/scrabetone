import json

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

def main():
    with open("docs/impianti.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    aggiornati = 0
    for el in data["elementi"]:
        nome = el["nome"]
        # Se l'elemento non ha geometria o coordinate (perché fallito in precedenza)
        if ("geometry" not in el or not el["geometry"]) and "lat" not in el:
            if nome in MANUAL_COORDS:
                el["lat"] = MANUAL_COORDS[nome][0]
                el["lon"] = MANUAL_COORDS[nome][1]
                aggiornati += 1

    with open("docs/impianti.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Aggiunte coordinate manuali a {aggiornati} elementi.")

if __name__ == "__main__":
    main()