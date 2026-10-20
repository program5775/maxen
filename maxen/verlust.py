"""Chance, die Hälfte zu verlieren: Zielfunktion für Bots und Tipps im Spiel.

Die Engine optimiert von sich aus die Chance, im Durchgang nicht Letzter zu sein. Im Spiel
geht es aber um die Hälfte: Bricken, Abgeben, Urlaub und der General, der die Hälfte beendet.
Dieses Modul bewertet jedes Endergebnis eines Durchgangs danach, wie wahrscheinlich man
danach die Hälfte verliert. Die Engine-DP bleibt, nur ihr Nutzen je Endergebnis wird ersetzt
(`Engine.mit_nutzen`).

Modell
------
* Spielstand: Phase, Mitte und die Bricken der Spieler. Die Spieler sind austauschbar, also
  zählen nur die sortierten Bricken. In Phase 2 spielen nur Spieler mit Bricken (die anderen
  haben Urlaub und können die Hälfte nicht mehr verlieren); es gibt nur 176 Aufteilungen von 15.
* Pro Durchgang würfelt jeder beteiligte Spieler unabhängig ein Ergebnis aus der Verteilung,
  die die Engine bei 3 erlaubten Würfen für „nicht verlieren“ liefert. Wer anfängt und wie oft
  die anderen würfeln dürfen, fließt in die Werte der Spielstände nicht ein (Näherung).
* Bei Gleichstand wird fair gestochen. Dadurch ist bei gleichen Spielern jeder gleich
  wahrscheinlich der Schlechteste bzw. der Beste, unabhängig davon, welches Ergebnis das beste ist.
* Phase 1 endet immer (die Mitte nimmt ab), Phase 2 kann hin und her gehen: Dort lösen wir ein
  lineares Gleichungssystem.

Für den eigenen Zug rechnet `nutzen` genauer: Die Gegner würfeln mit der Verteilung der
aktuellen Wurfgrenze, und für jedes eigene Ergebnis wird exakt bestimmt, wie wahrscheinlich man
Bester, Schlechtester oder keins von beiden ist und wie viele Bricken das beste Ergebnis kostet.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from math import factorial

import numpy as np

from .engine import Engine, Verteilung
from .regeln import ABGEBEN, ALLE_WUERFE, BRICKEN, VERTEILEN, Schluessel, bewerte
from .regeln import bricken as kosten

ICH, ANDERE = "ich", "andere"

Stand = tuple[int, ...]           # Bricken der beteiligten Spieler, absteigend sortiert


ALLE_SCHLUESSEL = sorted({bewerte(w) for w in ALLE_WUERFE})       # schlechtestes zuerst


@lru_cache(maxsize=None)
def gegner_verteilung(grenze: int, gegner: int) -> Verteilung:
    """Ergebnisverteilung eines Spielers, der bei `grenze` Würfen gegen `gegner` andere auf
    „nicht verlieren“ spielt (Fixpunkt der Engine)."""
    return Engine(grenze, gegner).gegner_verteilung


def kosten_des_besten(verteilung: Verteilung, anzahl: int) -> dict[int | None, float]:
    """Verteilung der Kosten des besten von `anzahl` unabhängigen Ergebnissen."""
    d: dict[int | None, float] = defaultdict(float)
    cdf = 0.0
    for s in ALLE_SCHLUESSEL:
        p = verteilung.get(s, 0.0)
        if p:
            d[kosten(s)] += (cdf + p) ** anzahl - cdf ** anzahl
            cdf += p
    return dict(d)


def ereignisse(verteilung: Verteilung, k: int) -> dict[Schluessel, dict[tuple, float]]:
    """Für jedes eigene Ergebnis gegen `k` Gegner mit `verteilung`: Wahrscheinlichkeit von
    (Kosten des besten Ergebnisses, wer gibt ab, wer bekommt). Wer gibt/bekommt ist ICH oder
    ANDERE; beim General ist „bekommt“ der Verlierer der Hälfte, „gibt“ ist dann None.
    In Phase 1 zählt nur, wer bekommt."""
    ergebnis = {}
    m = k + 1
    for r in ALLE_SCHLUESSEL:
        p_a = sum(p for s, p in verteilung.items() if s > r)
        p_e = verteilung.get(r, 0.0)
        p_b = 1.0 - p_a - p_e
        # Kosten des besten Gegners, wenn n_a Gegner besser sind (bedingt auf „besser als r“)
        ueber = {s: p / p_a for s, p in verteilung.items() if s > r} if p_a > 0 else {}
        d: dict[tuple, float] = defaultdict(float)
        for n_a in range(k + 1):
            for n_e in range(k - n_a + 1):
                n_b = k - n_a - n_e
                w = (factorial(k) / (factorial(n_a) * factorial(n_e) * factorial(n_b))
                     * p_a ** n_a * p_e ** n_e * p_b ** n_b)
                if w == 0:
                    continue
                # Wer bekommt: ich nur, wenn niemand schlechter ist, dann fair gestochen unter den Gleichen
                ich_unten = 1 / (n_e + 1) if n_b == 0 else 0.0
                if n_a > 0:
                    for a, q in kosten_des_besten(ueber, n_a).items():
                        geber = None if a is None else ANDERE
                        d[(a, geber, ICH)] += w * q * ich_unten
                        d[(a, geber, ANDERE)] += w * q * (1 - ich_unten)
                    continue
                a = kosten(r)
                if a is None:                               # mein General
                    d[(None, None, ICH)] += w * ich_unten
                    d[(None, None, ANDERE)] += w * (1 - ich_unten)
                    continue
                ich_oben = 1 / (n_e + 1)
                if n_b == 0:                                # alle gleich: ein gemeinsames Stechen
                    d[(a, ICH, ANDERE)] += w / m
                    d[(a, ANDERE, ICH)] += w / m
                    d[(a, ANDERE, ANDERE)] += w * (m - 2) / m
                else:
                    d[(a, ICH, ANDERE)] += w * ich_oben
                    d[(a, ANDERE, ANDERE)] += w * (1 - ich_oben)
        ergebnis[r] = {e: p for e, p in d.items() if p > 0}
    return ergebnis


def _sortiert(bricken) -> Stand:
    return tuple(sorted(bricken, reverse=True))


class Haelftenmodell:
    """Chance jedes Spielers, die Hälfte zu verlieren, für alle Spielstände einer Hälfte mit
    `n` Teilnehmern."""

    def __init__(self, n: int):
        self.n = n
        self._kosten = {m: kosten_des_besten(gegner_verteilung(3, m - 1), m) for m in range(2, n + 1)}
        self._phase2 = self._loese_phase2()
        self._phase1: dict[tuple[int, Stand], tuple[float, ...]] = {}

    # --- Phase 2 -----------------------------------------------------------------
    def _loese_phase2(self) -> dict[Stand, tuple[float, ...]]:
        """Lineares Gleichungssystem über alle Aufteilungen der 15 Bricken auf 2 bis n aktive Spieler."""
        staende = [s for s in _aufteilungen(BRICKEN, self.n) if len(s) >= 2]
        index, nr = {}, 0
        for s in staende:
            for j in range(len(s)):
                index[s, j] = nr
                nr += 1
        a = np.eye(nr)
        b = np.zeros(nr)
        for s in staende:
            m = len(s)
            for (betrag, q) in self._kosten[m].items():
                if betrag is None:                          # General: jeder verliert mit 1/m
                    for j in range(m):
                        b[index[s, j]] += q / m
                    continue
                p = q / (m * (m - 1))
                for g in range(m):
                    for e in range(m):
                        if g == e:
                            continue
                        t = min(betrag, s[g])
                        neu = list(s)
                        neu[g] -= t
                        neu[e] += t
                        if neu[e] == BRICKEN:
                            b[index[s, e]] += p
                            continue
                        ziel = _sortiert(x for x in neu if x > 0)
                        for j in range(m):
                            if neu[j] > 0:                  # wer 0 hat, hat Urlaub und ist sicher
                                a[index[s, j], index[ziel, ziel.index(neu[j])]] -= p
        x = np.linalg.solve(a, b)
        return {s: tuple(float(x[index[s, j]]) for j in range(len(s))) for s in staende}

    # --- Werte -------------------------------------------------------------------
    def verlust(self, phase: int, mitte: int, bricken: Stand) -> tuple[float, ...]:
        """Chance jedes Spielers (in der Reihenfolge von `bricken`), die Hälfte zu verlieren.
        In Phase 1 sind es alle Teilnehmer, in Phase 2 zählen Spieler mit 0 Bricken als Urlauber."""
        if phase == ABGEBEN:
            if BRICKEN in bricken:
                return tuple(1.0 if x == BRICKEN else 0.0 for x in bricken)
            aktiv = _sortiert(x for x in bricken if x > 0)
            werte = dict(zip(aktiv, self._phase2[aktiv]))
        else:
            s = _sortiert(bricken)
            werte = dict(zip(s, self._verlust_phase1(mitte, s)))   # gleiche Bricken, gleiche Chance
        return tuple(werte.get(x, 0.0) for x in bricken)

    def _verlust_phase1(self, mitte: int, s: Stand) -> tuple[float, ...]:
        if (mitte, s) in self._phase1:
            return self._phase1[mitte, s]
        n = len(s)
        v = [0.0] * n
        for betrag, q in self._kosten[n].items():
            if betrag is None:
                for j in range(n):
                    v[j] += q / n
                continue
            t = min(betrag, mitte)
            for e in range(n):                              # jeder ist gleich wahrscheinlich der Schlechteste
                neu = list(s)
                neu[e] += t
                for j, w in enumerate(self._nach_phase1(mitte - t, neu)):
                    v[j] += q / n * w
        self._phase1[mitte, s] = tuple(v)
        return self._phase1[mitte, s]

    def _nach_phase1(self, mitte: int, neu: list[int]) -> tuple[float, ...]:
        """Verlustchancen der Spieler in der Reihenfolge von `neu`, nachdem die Mitte auf `mitte` gesunken ist."""
        # Mitte leer: weiter in Phase 2, außer einer hat alle 15 (dann verliert er, das deckt `verlust` ab)
        return self.verlust(ABGEBEN if mitte == 0 else VERTEILEN, mitte, tuple(neu))

    def _ich_verliere(self, phase: int, mitte: int, ich: int, andere: list[int]) -> float:
        """Meine Verlustchance in einem Spielstand nach dem Durchgang."""
        if phase == VERTEILEN:
            return self._nach_phase1(mitte, [ich] + andere)[0]
        return self.verlust(ABGEBEN, 0, tuple([ich] + andere))[0]

    # --- Nutzen für den eigenen Zug ------------------------------------------------
    def nutzen(self, phase: int, mitte: int, ich: int, andere: tuple[int, ...],
               grenze: int) -> dict[Schluessel, float]:
        """1 − Chance, die Hälfte zu verlieren, für jedes eigene Endergebnis des Durchgangs.
        `andere`: Bricken der anderen Spieler im Durchgang; sie würfeln höchstens `grenze`-mal."""
        andere = list(andere)
        ereig_je_ergebnis = gegner_ereignisse(grenze, len(andere))
        folgen: dict[tuple, float] = {}                     # (Kosten, gibt, bekommt) -> meine Verlustchance
        for ereig in ereig_je_ergebnis.values():
            for e in ereig:
                if e not in folgen:
                    folgen[e] = self._folge(e, phase, mitte, ich, andere)
        return {r: 1.0 - sum(p * folgen[e] for e, p in ereig.items()) for r, ereig in ereig_je_ergebnis.items()}

    def _folge(self, ereignis, phase, mitte, ich, andere) -> float:
        """Meine Verlustchance nach einem Durchgang mit `ereignis`, gemittelt darüber, welcher
        der anderen Spieler gibt bzw. bekommt (bei gleichen Gegnern ist jeder gleich wahrscheinlich)."""
        betrag, geber, empfaenger = ereignis
        k = len(andere)
        if betrag is None:                                  # General
            return 1.0 if empfaenger == ICH else 0.0
        if phase == VERTEILEN:
            t = min(betrag, mitte)
            if empfaenger == ICH:
                return self._ich_verliere(phase, mitte - t, ich + t, andere)
            werte = []
            for e in range(k):
                neu = list(andere)
                neu[e] += t
                werte.append(self._ich_verliere(phase, mitte - t, ich, neu))
            return sum(werte) / k
        werte = []
        if geber == ICH:
            for e in range(k):
                t = min(betrag, ich)
                neu = list(andere)
                neu[e] += t
                werte.append(self._ich_verliere(phase, 0, ich - t, neu))
        elif empfaenger == ICH:
            for g in range(k):
                t = min(betrag, andere[g])
                neu = list(andere)
                neu[g] -= t
                werte.append(self._ich_verliere(phase, 0, ich + t, neu))
        else:
            for g in range(k):
                for e in range(k):
                    if g != e:
                        t = min(betrag, andere[g])
                        neu = list(andere)
                        neu[g] -= t
                        neu[e] += t
                        werte.append(self._ich_verliere(phase, 0, ich, neu))
        return sum(werte) / len(werte)


def _aufteilungen(summe: int, teile: int, hoechstens: int | None = None) -> list[Stand]:
    """Alle Aufteilungen von `summe` in höchstens `teile` positive Summanden, absteigend."""
    hoechstens = summe if hoechstens is None else hoechstens
    if summe == 0:
        return [()]
    if teile == 0:
        return []
    return [(x,) + rest for x in range(min(summe, hoechstens), 0, -1)
            for rest in _aufteilungen(summe - x, teile - 1, x)]


@lru_cache(maxsize=None)
def gegner_ereignisse(grenze: int, k: int) -> dict[Schluessel, dict[tuple, float]]:
    """`ereignisse` gegen `k` Gegner, die höchstens `grenze`-mal würfeln."""
    return ereignisse(gegner_verteilung(grenze, k), k)


@lru_cache(maxsize=None)
def haelftenmodell(n: int) -> Haelftenmodell:
    return Haelftenmodell(n)


@lru_cache(maxsize=512)
def haelften_engine(grenze: int, startspieler: bool, phase: int, mitte: int, ich: int,
                    andere: tuple[int, ...], teilnehmer: int) -> Engine:
    """Engine, die die Chance maximiert, die Hälfte nicht zu verlieren. `andere` sortiert übergeben,
    damit der Cache greift. Als Startspieler hängt die Grenze der anderen vom eigenen Klopfen ab."""
    modell = haelftenmodell(teilnehmer)
    grenzen = (1, 2, 3) if startspieler else (grenze,)
    nutzen = {g: modell.nutzen(phase, mitte, ich, andere, g) for g in grenzen}
    return Engine.mit_nutzen(3 if startspieler else grenze, startspieler, nutzen,
                             ziel="die Hälfte nicht zu verlieren")
