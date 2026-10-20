"""Computergegner für den Spielmodus.

Alle Bots wählen aus `empfehlung.optionen` und damit nur erlaubte Optionen.
"""
from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

from .engine import Empfehlung, Option
from .regeln import MAX, NORMAL, PASCH, STRASSE, Wurf, bewerte

MITTE_GENERAL = 3   # Phase 1: liegen höchstens so viele Bricken in der Mitte, geht man mit Max auf den General
MITTE_VIEL = 6      # Phase 1: liegen mehr in der Mitte, klopft man mit Max 5 oder Max 6
EIGENE_VIEL = 6     # Phase 2: wer mehr eigene Bricken hat, klopft nach Wurf 1 ab Straße
PASCH_REICHT = 3    # Phase 2: wer höchstens so viele Bricken hat, gibt sie mit 6,6,6 alle ab und klopft


@dataclass(frozen=True)
class Lage:
    """Was ein Bot außer der Empfehlung über seinen Zug weiß."""
    wurf: Wurf
    wurf_nr: int
    startspieler: bool = False   # legt durch sein Klopfen die Wurfgrenze fest
    bricken: int = 0             # eigene Bricken in der laufenden Hälfte
    phase: int = 1               # 1 = Verteilen, 2 = Abgeben
    mitte: int = 15              # Bricken in der Mitte


def plan(lage: Lage) -> str | None:
    """Was ein Kneipengänger mit einem guten Wurf vorhat: "klopfen", "max" (1,1 liegen lassen, für einen
    höheren Max oder den General), "drehen" (6,6,6 zu 1,1) oder None (keine Faustregel, die Engine
    entscheidet).

    6,6,6 lässt man so gut wie nie stehen, sondern dreht zu 1,1 (sicherer Max, Chance auf den General).
    Nur in Phase 2 mit höchstens PASCH_REICHT eigenen Bricken klopft man: Der Pasch gibt alle ab
    (vom Nutzer 2026-10-20).
    Phase 1 (Verteilen):
    * Max 2 hält man nie, man würfelt auf einen höheren Max.
    * Ende der Hälfte (höchstens MITTE_GENERAL in der Mitte): mit jedem Max auf den General.
    * Anfang der Hälfte (mehr als MITTE_VIEL in der Mitte): mit Max 5 oder Max 6 klopfen.
    Phase 2 (Abgeben), man will gewinnen und abgeben:
    * Mehr als EIGENE_VIEL eigene Bricken: nach Wurf 1 ab Straße klopfen, auch mit Max 2.
    * Sonst mit Max klopfen, wenn er für alle eigenen Bricken reicht, sonst auf einen höheren Max;
      mit Straße oder Pasch nach Wurf 1 klopfen.
    """
    kategorie, wert = bewerte(lage.wurf)
    if lage.wurf == (6, 6, 6):
        return "klopfen" if lage.phase == 2 and lage.bricken <= PASCH_REICHT else "drehen"
    if lage.phase == 1:
        if kategorie != MAX:
            return None
        if wert == 2 or lage.mitte <= MITTE_GENERAL:
            return "max"
        return "klopfen" if lage.mitte > MITTE_VIEL and wert >= 5 else None
    if lage.bricken > EIGENE_VIEL:
        return "klopfen" if lage.wurf_nr == 1 and STRASSE <= kategorie <= MAX else None
    if kategorie == MAX:
        return "klopfen" if wert >= lage.bricken else "max"
    return "klopfen" if lage.wurf_nr == 1 and kategorie in (STRASSE, PASCH) else None


def faustregel(option: Option, lage: Lage) -> bool:
    """Hält `option` die Faustregeln der Kneipengänger ein?

    * Mit Max, Pasch oder Straße je nach Phase und Bricken klopfen oder auf einen höheren Max
      gehen, 6,6,6 zu 1,1 drehen (siehe `plan`).
    * Als Startspieler nach Wurf 1 mit 6,6 oder 6,1 nicht klopfen (kein Schuss).
    * Wer weiterwürfelt, lässt alle 1en liegen und neben einer einzelnen 1 auch eine 6.
      Drehen ist davon ausgenommen.
    """
    wurf, fest = lage.wurf, option.neu_fest
    kategorie = bewerte(wurf)[0]
    vorhaben = plan(lage)
    if vorhaben == "klopfen":
        return option.aktion == "klopfen"
    if vorhaben == "max":
        return fest == (1, 1)
    if vorhaben == "drehen":
        return option.aktion == "drehen" and fest == (1, 1)
    if option.aktion == "klopfen":
        sechs_und = wurf.count(6) >= 2 or (6 in wurf and 1 in wurf)
        return not (lage.startspieler and lage.wurf_nr == 1 and kategorie == NORMAL and sechs_und)
    if option.aktion == "drehen":
        return True
    if fest.count(1) < wurf.count(1):
        return False
    return not (wurf.count(1) == 1 and 6 in wurf and 6 not in fest)


class Bot:
    stufe = ""

    def waehle(self, empfehlung: Empfehlung, rng: random.Random, lage: Lage) -> Option:
        raise NotImplementedError


class Mathematiker(Bot):
    """Spielt immer die Empfehlung der Engine."""
    stufe = "Mathematiker"

    def waehle(self, empfehlung, rng, lage):
        return empfehlung.beste.option


def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


class Kneipengaenger(Bot):
    """Spielt nach den Faustregeln (`faustregel`) und unter den Optionen, die sie erlauben, meist gut.

    In `regeltreue` der Fälle hält er sich an die Faustregeln; erlauben sie keine Option, gelten alle.
    Optionen, deren Chance, nicht zu verlieren, mehr als `grenze` unter der besten verbliebenen liegt,
    wählt er nie. Unter den übrigen wählt er zufällig, gewichtet per Softmax über die Log-Odds der Chance.
    Log-Odds statt der Chance selbst, weil bei vielen Gegnern alle Chancen nahe 100 % liegen und klare
    Fehler dann nur kleine Abstände haben (6,6,1 nach Wurf 2 gegen 5 Gegner: Drehen 99,9 %,
    6,6 liegen lassen 92,6 %). Je höher die Temperatur, desto öfter weicht er von der besten Option ab."""
    stufe = "Kneipengänger"

    def __init__(self, temperatur: float = 0.3, grenze: float = 0.03, regeltreue: float = 1.0):
        self.temperatur = temperatur
        self.grenze = grenze
        self.regeltreue = regeltreue

    def waehle(self, empfehlung, rng, lage):
        kandidaten = empfehlung.optionen
        if self.regeltreue >= 1 or rng.random() < self.regeltreue:
            kandidaten = [b for b in kandidaten if faustregel(b.option, lage)] or kandidaten
        beste = kandidaten[0].nutzen
        kandidaten = [b for b in kandidaten if beste - b.nutzen <= self.grenze]
        gewichte = [math.exp((logit(b.nutzen) - logit(beste)) / self.temperatur) for b in kandidaten]
        return rng.choices(kandidaten, weights=gewichte)[0].option


class Anfaenger(Kneipengaenger):
    """Wie der Kneipengänger, aber mit größeren Fehlern (bis 15 Prozentpunkte unter der besten Option)
    und nur in einem Drittel der Fälle nach den Faustregeln."""
    stufe = "Anfänger"

    def __init__(self, temperatur: float = 0.3, grenze: float = 0.15, regeltreue: float = 1 / 3):
        super().__init__(temperatur, grenze, regeltreue)


STUFEN: dict[str, type[Bot]] = {b.stufe: b for b in (Anfaenger, Kneipengaenger, Mathematiker)}

NAMEN = ("Ana", "Jenni", "Hanna", "Anika", "Roman", "Peter", "Tess", "Danny", "Andy")


def bot_namen(anzahl: int, rng: random.Random, gesperrt: str | Iterable[str] = ()) -> list[str]:
    """Verschiedene zufällige Namen aus NAMEN. Die Namen der Menschen sind gesperrt
    (Groß-/Kleinschreibung egal)."""
    belegt = {g.strip().casefold() for g in ([gesperrt] if isinstance(gesperrt, str) else gesperrt)}
    frei = [n for n in NAMEN if n.casefold() not in belegt]
    return rng.sample(frei, anzahl)
