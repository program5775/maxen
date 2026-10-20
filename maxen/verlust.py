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

Für den eigenen Zug rechnet `nutzen` genauer, mit dem, was am Tisch zu sehen ist (`zug_engines`):
* Wer schon offen fertig ist, hat ein bekanntes Ergebnis.
* Bei einem verdeckten letzten Wurf sieht man, was liegt und wie viele Würfel geworfen wurden; das
  Ergebnis folgt aus der Engine („nicht verlieren“) für diesen Zustand, inkl. Drehen zum Bonuswurf.
* Wer noch nicht dran war, würfelt wie ein typischer Spieler mit der aktuellen Wurfgrenze.
Für jedes eigene Ergebnis wird exakt bestimmt, mit welcher Wahrscheinlichkeit welcher Spieler das
beste Ergebnis hat (gibt ab), welcher das schlechteste (bekommt) und was das beste Ergebnis kostet
(`rollen`). Daraus folgen zwei Chancen: die Hälfte nicht zu verlieren und im Durchgang nicht Letzter
zu sein (für die Anzeige und für die Bots, die unter fast gleich guten Optionen nach dem Durchgang wählen).
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

import numpy as np

from .engine import Engine, Verteilung
from .regeln import ABGEBEN, ALLE_WUERFE, BRICKEN, VERTEILEN, Schluessel, bewerte
from .regeln import bricken as kosten

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


# --- Wer gibt ab, wer bekommt: einzelne Gegner mit eigener Verteilung ------------------
K = len(ALLE_SCHLUESSEL)
_INDEX = {s: i for i, s in enumerate(ALLE_SCHLUESSEL)}
KLASSEN: list[int | None] = sorted({kosten(s) for s in ALLE_SCHLUESSEL} - {None}) + [None]
_KLASSE = np.zeros((K, len(KLASSEN)))              # Ergebnis -> Kostenklasse (None = General)
for _i, _s in enumerate(ALLE_SCHLUESSEL):
    _KLASSE[_i, KLASSEN.index(kosten(_s))] = 1.0
_UNTER = np.tril(np.ones((K, K)), -1)               # [h, l] = 1 für l < h
_DIAG = np.arange(K)


def als_vektor(verteilung: Verteilung) -> np.ndarray:
    v = np.zeros(K)
    for s, p in verteilung.items():
        v[_INDEX[s]] += p
    return v


def _polynom(vektoren) -> dict[tuple[int, int], np.ndarray]:
    """Produkt über die Spieler von (zwischen + oben·x + unten·y) für jedes Paar (h, l): Der Koeffizient
    von x^a·y^b ist die Wahrscheinlichkeit, dass genau a von ihnen das Ergebnis h haben, b das
    Ergebnis l und alle übrigen dazwischen liegen."""
    c = {(0, 0): np.ones((K, K))}
    for p in vektoren:
        cdf = np.cumsum(p)
        zwischen = (cdf - p)[:, None] - cdf[None, :]        # P(l < X < h), nur für l < h sinnvoll
        oben, unten = p[:, None], p[None, :]
        neu: dict[tuple[int, int], np.ndarray] = {}
        for (a, b), w in c.items():
            for schluessel, faktor in (((a, b), zwischen), ((a + 1, b), oben), ((a, b + 1), unten)):
                neu[schluessel] = neu.get(schluessel, 0) + w * faktor
        c = neu
    return c


def _summe(c, oben: int = 0, unten: int = 0) -> np.ndarray:
    """Σ c[a, b] / ((a+1+oben)·(b+1+unten)): faires Stechen unter den Gleichstehenden oben und unten,
    mit `oben`/`unten` weiteren Spielern, die dort mitstechen."""
    return sum(w / ((a + 1 + oben) * (b + 1 + unten)) for (a, b), w in c.items())


def rollen(gegner: list[np.ndarray]) -> np.ndarray:
    """W[g, e, r, a]: Bei eigenem Ergebnis r (Index in ALLE_SCHLUESSEL) hat Spieler g das beste
    Ergebnis (gibt ab), Spieler e das schlechteste (bekommt) und das beste Ergebnis die Kostenklasse
    KLASSEN[a]. Spieler 0 bin ich, 1..k die Gegner mit ihren Ergebnisverteilungen. Gleichstand: faires
    Stechen; sind alle gleich, entscheidet ein gemeinsames Stechen beides (g ≠ e).
    Beim General ist e der Verlierer der Hälfte (g zählt dann nicht)."""
    k, n = len(gegner), len(gegner) + 1
    polynome: dict[frozenset, dict] = {}

    def ohne(*spieler) -> dict:
        schluessel = frozenset(spieler)
        if schluessel not in polynome:
            polynome[schluessel] = _polynom([gegner[i - 1] for i in range(1, n) if i not in schluessel])
        return polynome[schluessel]

    w = np.zeros((n, n, K, K))                          # [g, e, r, h]
    for g in range(n):
        for e in range(n):
            if g == e:
                continue
            if g == 0:                                  # ich oben (h = r), e unten (l < r)
                pe = gegner[e - 1]
                w[0, e, _DIAG, _DIAG] += (_summe(ohne(e)) * _UNTER * pe[None, :]).sum(axis=1)
            elif e == 0:                                # ich unten (l = r), g oben (h > r)
                pg = gegner[g - 1]
                w[g, 0] += (_summe(ohne(g)) * _UNTER * pg[:, None]).T
            else:
                pg, pe = gegner[g - 1], gegner[e - 1]
                c = ohne(g, e)
                paar = _UNTER * pg[:, None] * pe[None, :]                  # [h, l], g auf h, e auf l
                t = _summe(c) * paar
                w[g, e] += ((np.cumsum(t, axis=1) - t) * _UNTER).T        # ich dazwischen: l < r < h
                w[g, e, _DIAG, _DIAG] += (_summe(c, oben=1) * paar).sum(axis=1)   # ich gleichauf oben
                w[g, e] += (_summe(c, unten=1) * paar).T                  # ich gleichauf unten
    alle_gleich = np.prod(gegner, axis=0) / (n * (n - 1)) if k else np.zeros(K)
    for g in range(n):
        for e in range(n):
            if g != e:
                w[g, e, _DIAG, _DIAG] += alle_gleich
    return w @ _KLASSE


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

    # --- Nutzen für den eigenen Zug ------------------------------------------------
    def nutzen(self, phase: int, mitte: int, ich: int, andere: list[int],
               w: np.ndarray) -> tuple[dict[Schluessel, float], dict[Schluessel, float]]:
        """Für jedes eigene Endergebnis: (1 − Chance, die Hälfte zu verlieren, 1 − Chance, im Durchgang
        Letzter zu sein). `andere`: Bricken der Gegner im Durchgang, `w` aus `rollen` in derselben Reihenfolge."""
        n = len(andere) + 1
        folge = np.zeros((n, n, len(KLASSEN)))
        for g in range(n):
            for e in range(n):
                if g != e:
                    for a, betrag in enumerate(KLASSEN):
                        folge[g, e, a] = self._folge(phase, mitte, [ich] + list(andere), g, e, betrag)
        verlust = np.einsum("gera,gea->r", w, folge)
        letzter = w[:, 0].sum(axis=(0, 2))
        return ({s: 1.0 - float(verlust[i]) for i, s in enumerate(ALLE_SCHLUESSEL)},
                {s: 1.0 - float(letzter[i]) for i, s in enumerate(ALLE_SCHLUESSEL)})

    def _folge(self, phase: int, mitte: int, bricken: list[int], g: int, e: int, betrag: int | None) -> float:
        """Meine Verlustchance (Spieler 0), wenn g das beste und e das schlechteste Ergebnis hat."""
        if betrag is None:                                  # General: der Schlechteste verliert die Hälfte
            return 1.0 if e == 0 else 0.0
        neu = list(bricken)
        if phase == VERTEILEN:
            t = min(betrag, mitte)
            neu[e] += t
            return self._nach_phase1(mitte - t, neu)[0]
        t = min(betrag, neu[g])
        neu[g] -= t
        neu[e] += t
        return self.verlust(ABGEBEN, 0, tuple(neu))[0]


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
def haelftenmodell(n: int) -> Haelftenmodell:
    return Haelftenmodell(n)


@lru_cache(maxsize=None)
def durchgang_engine(grenze: int, gegner: int, startspieler: bool) -> Engine:
    """Engine für „im Durchgang nicht Letzter sein“; damit wird geschätzt, wie ein Gegner weiterspielt."""
    return Engine(wuerfe=grenze, gegner=gegner, startspieler=startspieler)


@lru_cache(maxsize=4096)
def sicht_vektor(sicht: tuple, grenze: int, k: int) -> np.ndarray:
    """Ergebnisverteilung eines Gegners nach dem, was man von ihm sieht (`k` Gegner je Spieler):
    ("frei",): noch nicht dran, würfelt höchstens `grenze`-mal;
    ("fest", schluessel): offen fertig;
    ("verdeckt", grenze, startspieler, fest, wurf_nr, gedreht): letzter Wurf verdeckt, `fest` lag davor;
    ("entscheidet", grenze, startspieler, wurf, gedreht): aufgedeckt nach Wurf 3, dreht vielleicht noch."""
    art = sicht[0]
    if art == "frei":
        return als_vektor(gegner_verteilung(grenze, k))
    if art == "fest":
        return als_vektor({sicht[1]: 1.0})
    e = durchgang_engine(sicht[1], k, sicht[2])
    if art == "verdeckt":
        return als_vektor(e.zustand(sicht[3], sicht[4], sicht[5])[1])
    return als_vektor(e.bewerte_optionen(sicht[3], 3, sicht[4])[0].verteilung)


@lru_cache(maxsize=512)
def zug_engines(grenze: int, startspieler: bool, phase: int, mitte: int, ich: int,
                gegner: tuple[tuple[int, tuple], ...], teilnehmer: int) -> tuple[Engine, Engine]:
    """Engines für den eigenen Zug: (die Hälfte nicht verlieren, im Durchgang nicht Letzter sein).
    `gegner`: je Gegner im Durchgang (Bricken, Sicht wie bei `sicht_vektor`); sortiert übergeben,
    damit der Cache greift. Als Startspieler hängt die Grenze der anderen vom eigenen Klopfen ab."""
    modell = haelftenmodell(teilnehmer)
    andere = [b for b, _ in gegner]
    haelfte, durchgang = {}, {}
    for g in ((1, 2, 3) if startspieler else (grenze,)):
        w = rollen([sicht_vektor(sicht, g, len(gegner)) for _, sicht in gegner])
        haelfte[g], durchgang[g] = modell.nutzen(phase, mitte, ich, andere, w)
    wuerfe = 3 if startspieler else grenze
    return (Engine.mit_nutzen(wuerfe, startspieler, haelfte, ziel="die Hälfte nicht zu verlieren"),
            Engine.mit_nutzen(wuerfe, startspieler, durchgang, ziel="im Durchgang nicht Letzter zu sein"))
