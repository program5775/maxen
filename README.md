# Maxen – Würfelspiel-Assistent

Eine kleine Web-App für das Würfelspiel „Maxen“ (regional auch Schocken oder Knobeln genannt).
Nach jedem Wurf empfiehlt sie, welche Würfel liegen bleiben sollen, und zeigt die Wahrscheinlichkeiten dazu.
Gedacht ist sie fürs Handy am Spieltisch.

Es gibt viele Varianten von Maxen. Hier stehen die Regeln, mit denen wir spielen und mit denen die App rechnet.

## Spielregeln

### Begriffe

Von klein nach groß:

- **Durchgang:** Jeder beteiligte Spieler ist einmal an der Reihe.
- **Hälfte:** besteht aus mehreren Durchgängen, bis ein Spieler sie verloren hat.
- **Runde:** besteht aus mindestens zwei Hälften.

Jeder Spieler hat drei Würfel. Gespielt wird im Uhrzeigersinn.

### Ziel und Bricken

Ziel ist es, möglichst keine **Bricken** (Strafpunkte) zu haben.
Pro Hälfte liegen 15 Bricken in der Mitte. In jedem Durchgang verliert der Spieler mit dem schlechtesten Ergebnis.
Wie viele Bricken er bekommt, bestimmt das **beste** Ergebnis des Durchgangs:

| Bestes Ergebnis | Bricken |
|---|---|
| General | Die Hälfte ist nach diesem Durchgang beendet. Der Spieler mit dem schlechtesten Ergebnis hat sie verloren. |
| Max 6 … Max 2 | 6 … 2 |
| jeder Pasch | 3 |
| jede Straße | 2 |
| alles darunter | 1 |

### Ablauf einer Hälfte

**Phase 1 – Verteilen:** Alle Spieler spielen mit. Der Verlierer eines Durchgangs bekommt die Bricken aus der Mitte.
Liegen dort nicht mehr genug, bekommt er nur den Rest. Das geht so weiter, bis die Mitte leer ist.
Hat dann ein einziger Spieler alle 15 Bricken, hat er die Hälfte verloren.

**Phase 2 – Abgeben:** Sonst spielen nur noch die Spieler mit Bricken weiter. Wer keine hat, hat „Urlaub“.
Jetzt muss der Spieler mit dem besten Ergebnis Bricken an den Spieler mit dem schlechtesten abgeben, so viele, wie die Tabelle oben sagt.
Hat er weniger, gibt er alle ab, die er noch hat. Wer keine Bricken mehr hat, geht in Urlaub.
Gespielt wird, bis ein Spieler alle 15 Bricken hat. Er hat die Hälfte verloren.

Ein General beendet die Hälfte in jeder Phase nach dem laufenden Durchgang.
Gibt es mehrere Generäle, wird der Verlierer nach den normalen Regeln bestimmt.

### Ablauf einer Runde

Eine Runde hat zwei Hälften. Verliert derselbe Spieler beide, hat er mit einem **glatten Gang** verloren.
Verlieren zwei verschiedene Spieler je eine Hälfte, spielen nur diese beiden ein **Finale**: eine eigene vollständige Hälfte mit 15 Bricken.
Wer das Finale verliert, hat die Runde verloren.

Spieler im Urlaub steigen in der zweiten Hälfte wieder ein, nach einem glatten Gang oder nach dem Finale.

### Wer beginnt?

- Der allererste Durchgang der allerersten Runde ist ein **Schuss** (ein einziger Wurf) für alle.
- Danach beginnt immer der Spieler, der im letzten Durchgang Bricken bekommen hat.
- Die zweite Hälfte und das Finale beginnt der Verlierer der ersten Hälfte.
- Eine neue Runde beginnt der Verlierer der letzten Runde. Einen Schuss gibt es dann nicht mehr.

### Ablauf eines Durchgangs

1. **Der Startspieler** würfelt höchstens dreimal. Wie oft er würfelt, so oft dürfen die anderen in diesem Durchgang höchstens würfeln.
   Bleibt er schon nach dem ersten Wurf stehen, haben also alle anderen nur einen Schuss. Sein letzter Wurf bleibt verdeckt.
2. **Die anderen** sind reihum dran und würfeln höchstens so oft wie der Startspieler. Früher stehen bleiben ist erlaubt.
3. **Aufdecken:** Wenn alle dran waren, deckt der Startspieler auf, danach reihum die anderen.
4. **Bonuswurf:** Wer beim Aufdecken nach seinem dritten Wurf drehen darf (siehe unten), muss sich sofort entscheiden, also bevor die Spieler nach ihm aufdecken.
   Der vierte Wurf bleibt verdeckt. Zum Schluss werden die vierten Würfe der Reihe nach aufgedeckt, beginnend beim Startspieler bzw. beim ersten Spieler, der gedreht hat.

### Liegen lassen und neu würfeln

Nach jedem Wurf zählen alle drei Würfel. Du darfst beliebig viele davon liegen lassen und den Rest neu würfeln.
Auch Würfel, die du vorher herausgelegt hast, dürfen wieder mitgewürfelt werden.

### Drehen

Sechsen lassen sich in Einsen umwandeln:

- **Zwei 6en → eine 1:** Eine der beiden 6en wird auf die 1 gedreht, die andere wird neu gewürfelt.
  Den dritten Würfel darfst du liegen lassen oder ebenfalls neu würfeln.
- **Drei 6en → zwei 1en:** Zwei der 6en werden auf die 1 gedreht, die dritte wird neu gewürfelt.

Beim Drehen wird also immer mindestens ein Würfel neu geworfen.

Wann gedreht werden darf, hängt davon ab, wie oft in diesem Durchgang gewürfelt werden darf:

| Erlaubte Würfe | Drehen erlaubt nach | Hinweis |
|---|---|---|
| 3 | Wurf 1, 2 und 3 | Drehen nach Wurf 3 passiert beim Aufdecken und ergibt einen 4. Wurf (Bonuswurf). Danach wird nicht mehr gedreht. |
| 2 | nur Wurf 1 | |
| 1 (Schuss) | nie | |

Drehen beim Aufdecken gibt es nur nach dem dritten Wurf. Wer nach Wurf 1 oder 2 stehen bleibt, konnte schon in seinem Zug drehen.

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

### Gleichstand

Haben mehrere Spieler das gleiche beste oder schlechteste Ergebnis, wird **gestochen**:
zuerst unter den Besten, wer abgibt (nur in Phase 2), danach unter den Schlechtesten, wer die Bricken bekommt.

Beim Stechen würfelt jeder Beteiligte einmal mit allen drei Würfeln. Es zählt nur die **Augensumme**:
6, 6, 6 (18) ist das höchste, 1, 1, 1 (3) das niedrigste Ergebnis. Bei gleicher Summe wird neu geworfen, zum Beispiel bei 6, 5, 1 gegen 4, 4, 4.

## So entsteht die Empfehlung

Die App bewertet einen einzelnen Durchgang. Sie optimiert die Chance, **in diesem Durchgang nicht Letzter zu werden**, nicht die höchste Augenzahl.
Dabei nimmt sie an, dass auch die Mitspieler optimal spielen. Ein Gleichstand zählt halb.
Alle Wahrscheinlichkeiten werden exakt über alle möglichen Würfelausgänge berechnet, nicht simuliert.

Deshalb empfiehlt die App nicht immer die Option mit der besten Chance auf eine bestimmte Kombination.
Ein Beispiel: Bei 2, 3, 5 hat „2, 3 liegen lassen“ die höchste Chance auf eine Straße.
Die App rät trotzdem, alle drei neu zu würfeln, weil eine Straße relativ niedrig rangiert und Neuwürfeln die Chance auf Max oder Pasch offen hält.

Die App zeigt deshalb immer beides: die Empfehlung und für jede Option die Chance auf „≥ Max“, „≥ Pasch“ und „≥ Straße“.
„≥“ bedeutet dabei: diese Kombination oder eine bessere.

**Als Startspieler** schaltest du „Ich bin Startspieler“ ein. Die App berücksichtigt dann, dass dein Stehenbleiben die Würfe der anderen begrenzt.
Ein Beispiel mit zwei Gegnern: Mit 6, 4, 4 nach dem zweiten Wurf rät sie dem Startspieler, stehen zu bleiben (56 % Chance, nicht Letzter zu werden), weil die anderen dann nur zwei Würfe haben.
Ein normaler Spieler sollte mit demselben Wurf weiterwürfeln.

Noch nicht berücksichtigt sind die Bricken selbst: In Phase 2 lohnt es sich zum Beispiel, Bester zu sein, weil der Beste Bricken abgibt.
Auch der Spielstand fließt nicht in die Empfehlung ein.

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
