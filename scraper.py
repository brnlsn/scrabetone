import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://www.abetone-cutigliano.it/impianti-skipass/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0"

BASE = Path(__file__).parent
CACHE_HTML = BASE / "data" / "impianti-skipass.html"
OUTPUT_JSON = BASE / "docs" / "impianti.json"
CATALOGO_JSON = BASE / "catalogo.json"

AREE = ("Multipass", "La Doganaccia")
TIPI = ("Piste", "Impianti", "Piste fondo")
VERSIONE_SCHEMA = 2

def scarica_html() -> str:
    print(f"→ Scarico {URL}")
    r = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    CACHE_HTML.parent.mkdir(parents=True, exist_ok=True)
    CACHE_HTML.write_text(r.text, encoding="utf-8")
    print(f"  salvato in {CACHE_HTML.relative_to(BASE)} ({len(r.text):,} byte)")
    return r.text

def leggi_cache() -> str:
    if not CACHE_HTML.exists():
        sys.exit(f"✗ Cache assente: {CACHE_HTML}")
    print(f"→ Leggo cache {CACHE_HTML.relative_to(BASE)}")
    return CACHE_HTML.read_text(encoding="utf-8")

def contesto(tabella):
    area = tipo = None
    for h in tabella.find_all_previous("h2"):
        t = h.get_text(strip=True)
        if area is None and t in AREE:
            area = t
        if tipo is None and t in TIPI:
            tipo = t
        if area and tipo:
            break
    return area, tipo

def estrai(html: str):
    soup = BeautifulSoup(html, "html.parser")
    elementi = []
    for tabella in soup.find_all("table"):
        area, tipo = contesto(tabella)
        tbody = tabella.find("tbody")
        if not tbody or not area or not tipo:
            continue
        
        # Sostituisce "Multipass" con "Abetone"
        if area == "Multipass":
            area = "Abetone"

        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            stato_txt = tds[0].get_text(strip=True)
            stato = "Aperto" if "Aperto" in stato_txt else "Chiuso"
            nome = " ".join(tds[1].get_text(strip=True).split())
            elementi.append({
                "area": area,
                "tipo": tipo,
                "stato": stato,
                "nome": nome,
            })
    return elementi

def main():
    p = argparse.ArgumentParser(description="Scraper piste/impianti Abetone")
    p.add_argument("--local", action="store_true", help="usa HTML in cache")
    args = p.parse_args()

    html = leggi_cache() if args.local else scarica_html()
    elementi = estrai(html)

    # Carica il catalogo e crea un dizionario per il match veloce
    with open(CATALOGO_JSON, "r", encoding="utf-8") as f:
        catalogo = json.load(f)
    
    # The source page has names and types, not IDs; resolve them once at ingestion.
    cat_dict = {(c["nome_sito"], c["tipo"]): c["id"] for c in catalogo}

    non_trovati = []
    for el in elementi:
        el_id = cat_dict.get((el["nome"], el["tipo"]))
        if el_id:
            el["id"] = el_id
        else:
            el["id"] = "unknown"
            non_trovati.append(el["nome"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "versione_schema": VERSIONE_SCHEMA,
        "aggiornato": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": URL,
        "elementi": elementi,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ Scritti {len(elementi)} elementi in {OUTPUT_JSON.relative_to(BASE)}")
    
    if non_trovati:
        print(f"⚠️ Attenzione, {len(non_trovati)} elementi non hanno trovato un ID:")
        for n in set(non_trovati):
            print(f"  - {n}")
    else:
        print("✓ Tutti gli elementi hanno un ID valido.")

if __name__ == "__main__":
    main()