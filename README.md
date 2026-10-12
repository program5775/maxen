# Maxen – Würfelspiel-Assistent

Eine kleine Web-App für das Würfelspiel „Maxen“ (regional auch Schocken oder Knobeln genannt).
Nach jedem Wurf empfiehlt sie, welche Würfel liegen bleiben sollen, und zeigt die Wahrscheinlichkeiten dazu.
Gedacht ist sie fürs Handy am Spieltisch.

Es gibt viele Varianten von Maxen. Die App rechnet mit den Regeln unten.

## Spielregeln

Jeder Spieler hat drei Würfel. Wer am Ende der Runde das niedrigste Ergebnis hat, verliert.

### Würfe pro Runde

Wer die Runde beginnt, legt fest, wie viele Würfe erlaubt sind:

- **1 Wurf** (Schuss)
- **2 Würfe**
- **3 Würfe**

Man darf jederzeit früher stehen bleiben. Der letzte Wurf bleibt verdeckt.

### Liegen lassen und neu würfeln

Nach jedem Wurf zählen alle drei Würfel. Du darfst beliebig viele davon liegen lassen und den Rest neu würfeln.
Auch Würfel, die du vorher herausgelegt hast, dürfen wieder mitgewürfelt werden.

### Drehen

Sechsen lassen sich in Einsen umwandeln:

- **Zwei 6en → eine 1:** Eine der beiden 6en wird auf die 1 gedreht, die andere wird neu gewürfelt.
  Den dritten Würfel darfst du liegen lassen oder ebenfalls neu würfeln.
- **Drei 6en → zwei 1en:** Zwei der 6en werden auf die 1 gedreht, die dritte wird neu gewürfelt.

Beim Drehen wird also immer mindestens ein Würfel neu geworfen.

Wann gedreht werden darf, hängt von der Anzahl der Würfe ab:

| Erlaubte Würfe | Drehen erlaubt nach | Hinweis |
|---|---|---|
| 3 | Wurf 1, 2 und 3 | Drehen nach Wurf 3 ergibt einen 4. Wurf (Bonuswurf). Nach dem Bonuswurf wird nicht mehr gedreht. |
| 2 | nur Wurf 1 | |
| 1 (Schuss) | nie | |

### Rangfolge

Vom besten zum schlechtesten Ergebnis:

| Rang | Kombination | Würfel |
|---|---|---|
| 1 | General | 1, 1, 1 |
| 2–6 | Max 6 … Max 2 | 1, 1, 6 … 1, 1, 2 |
| 7–11 | 6er Pasch … 2er Pasch | 6, 6, 6 … 2, 2, 2 |
| 12–15 | Straße 6 … Straße 3 | 6, 5, 4 … 3, 2, 1 |
| ab 16 | Normal | Würfel absteigend sortiert und als Zahl gelesen |

Bei normalen Würfen ist die höhere Zahl besser: 6, 5, 5 ergibt 655 und schlägt 6, 4, 4 (644).
Jede Straße schlägt jeden normalen Wurf, auch 3, 2, 1 schlägt 6, 6, 5.

## So entsteht die Empfehlung

Die App optimiert die Chance, **nicht zu verlieren**, nicht die höchste Augenzahl.
Dabei nimmt sie an, dass auch die Mitspieler optimal spielen. Ein Gleichstand zählt halb.
Alle Wahrscheinlichkeiten werden exakt über alle möglichen Würfelausgänge berechnet, nicht simuliert.

Deshalb empfiehlt die App nicht immer die Option mit der besten Chance auf eine bestimmte Kombination.
Ein Beispiel: Bei 2, 3, 5 hat „2, 3 liegen lassen“ die höchste Chance auf eine Straße.
Die App rät trotzdem, alle drei neu zu würfeln, weil eine Straße relativ niedrig rangiert und Neuwürfeln die Chance auf Max oder Pasch offen hält.

Die App zeigt deshalb immer beides: die Empfehlung und für jede Option die Chance auf „≥ Max“, „≥ Pasch“ und „≥ Straße“.
„≥“ bedeutet dabei: diese Kombination oder eine bessere.

## Lokal starten

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Tests (benötigen zusätzlich `pytest`):

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests
```
