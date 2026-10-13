"""Computergegner für den Spielmodus.

Alle Bots wählen aus `empfehlung.optionen` und damit nur erlaubte Optionen.
"""
from __future__ import annotations

import math
import random
from collections.abc import Iterable

from .engine import Empfehlung, Option
from .regeln import STRASSE, bewerte


class Bot:
    stufe = ""

    def waehle(self, empfehlung: Empfehlung, rng: random.Random) -> Option:
        raise NotImplementedError


class Profi(Bot):
    """Spielt immer die Empfehlung der Engine."""
    stufe = "Profi"

    def waehle(self, empfehlung, rng):
        return empfehlung.beste.option


def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


class Fortgeschritten(Bot):
    """Macht kleine Fehler, aber keine groben: Optionen, deren Chance, nicht zu verlieren,
    mehr als `grenze` unter der besten liegt, wählt er nie. Unter den übrigen wählt er zufällig,
    gewichtet per Softmax über die Log-Odds der Chance. Log-Odds statt der Chance selbst, weil bei
    vielen Gegnern alle Chancen nahe 100 % liegen und klare Fehler dann nur kleine Abstände haben
    (6,6,1 nach Wurf 2 gegen 5 Gegner: Drehen 99,9 %, 6,6 liegen lassen 92,6 %).
    Je höher die Temperatur, desto öfter weicht er von der besten Option ab."""
    stufe = "Fortgeschritten"

    def __init__(self, temperatur: float = 0.3, grenze: float = 0.10):
        self.temperatur = temperatur
        self.grenze = grenze

    def waehle(self, empfehlung, rng):
        beste = empfehlung.beste.nutzen
        kandidaten = [b for b in empfehlung.optionen if beste - b.nutzen <= self.grenze]
        gewichte = [math.exp((logit(b.nutzen) - logit(beste)) / self.temperatur) for b in kandidaten]
        return rng.choices(kandidaten, weights=gewichte)[0].option


class Anfaenger(Bot):
    """Faustregel ohne Engine: ab Straße stehen bleiben, sonst die höchsten Würfel
    liegen lassen und den Rest neu würfeln. Dreht nie."""
    stufe = "Anfänger"

    def waehle(self, empfehlung, rng):
        erlaubt = {b.option.neu_fest: b.option for b in empfehlung.optionen if b.option.aktion != "drehen"}
        stehen = next(o for o in erlaubt.values() if o.aktion == "stehen")
        wurf = stehen.neu_fest
        if bewerte(wurf)[0] >= STRASSE:
            return stehen
        behalten = tuple(w for w in wurf if w == max(wurf))
        return erlaubt.get(behalten, stehen)


STUFEN: dict[str, type[Bot]] = {b.stufe: b for b in (Anfaenger, Fortgeschritten, Profi)}

NAMEN = ("Ana", "Jenni", "Hanna", "Anika", "Roman", "Piotl", "Tess", "Danny", "Andy")


def bot_namen(anzahl: int, rng: random.Random, gesperrt: str | Iterable[str] = ()) -> list[str]:
    """Verschiedene zufällige Namen aus NAMEN. Die Namen der Menschen sind gesperrt
    (Groß-/Kleinschreibung egal)."""
    belegt = {g.strip().casefold() for g in ([gesperrt] if isinstance(gesperrt, str) else gesperrt)}
    frei = [n for n in NAMEN if n.casefold() not in belegt]
    return rng.sample(frei, anzahl)
