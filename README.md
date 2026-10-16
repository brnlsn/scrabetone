# scrabetone

Stato piste e impianti di Abetone Cutigliano in formato JSON, aggiornato automaticamente ogni giorno.

## Dati

- Fonte: https://www.abetone-cutigliano.it/impianti-skipass/
- Output pubblico: https://TUONOME.github.io/scrabetone/impianti.json
- Aggiornamento: GitHub Actions, ogni giorno alle 09:00 UTC

## Struttura JSON

    {
      "versione_schema": 1,
      "aggiornato": "2026-10-16T15:57:43+00:00",
      "fonte": "https://www.abetone-cutigliano.it/impianti-skipass/",
      "elementi": [
        { "area": "Multipass", "tipo": "Piste", "stato": "Chiuso", "nome": "6. Chierroni" }
      ]
    }

## Licenza

Vedi LICENSE.
