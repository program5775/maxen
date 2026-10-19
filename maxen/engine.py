"""Wahrscheinlichkeiten und Empfehlungen für „Maxen".

Regeln, wie modelliert
----------------------
* Nach jedem Wurf liegen drei Würfel vor dir. Du entscheidest frei, welche du
  liegen lässt. Auch früher herausgelegte Würfel dürfen wieder mitgewürfelt werden.
  Wer alle drei liegen lässt, klopft. Wer würfelt, muss mindestens einen
  Würfel werfen.
* Drehen: zwei 6en -> eine 1 (der dritte Würfel darf liegen bleiben oder
  mitgewürfelt werden), drei 6en -> zwei 1en (ein Würfel frei).
* Wann gedreht werden darf:
    - 3 Würfe erlaubt: nach Wurf 1, 2 und 3. Drehen nach Wurf 3 ergibt einen
      4. Wurf. Nach dem 4. Wurf ist Schluss.
    - 2 Würfe erlaubt: nur nach Wurf 1.
    - 1 Wurf (Schuss): gar nicht.
  Gedreht wird höchstens einmal pro Zug: Wer schon gedreht hat, darf auch bei
  erneuten 6,6 nicht noch einmal drehen.

Alle Wahrscheinlichkeiten werden exakt über alle Würfelausgänge berechnet
(Dynamische Programmierung, keine Simulation).

Zielfunktion
------------
Bewertet wird die Chance, NICHT zu verlieren:
nutzen(r) = 1 - q(r)^gegner, mit q(r) = P(Gegner besser als r) + ½·P(Gleichstand).
Die Gegner spielen ebenfalls optimal; ihre Ergebnisverteilung wird per
Fixpunkt-Iteration bestimmt.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, product

from .regeln import (
    ALLE_WUERFE, GENERAL, KATEGORIE_NAMEN, MAX, PASCH, STRASSE, RANG,
    Schluessel, bewerte, name,
)

Verteilung = dict[Schluessel, float]


@lru_cache(maxsize=None)
def wurf_verteilung(anzahl: int) -> tuple[tuple[tuple[int, ...], float], ...]:
    """Verteilung der sortierten Ergebnisse beim Werfen von `anzahl` Würfeln."""
    d: dict[tuple[int, ...], float] = defaultdict(float)
    for o in product(range(1, 7), repeat=anzahl):
        d[tuple(sorted(o))] += 1 / 6 ** anzahl
    return tuple(d.items())


def einzelwurf_verteilung() -> Verteilung:
    """Verteilung eines einzigen Wurfs mit drei Würfeln (Schuss)."""
    d: Verteilung = defaultdict(float)
    for o, p in wurf_verteilung(3):
        d[bewerte(o)] += p
    return dict(d)


# --- Wann darf was passieren? ----------------------------------------------
def darf_wuerfeln(wurf_nr: int, wuerfe: int) -> bool:
    """Darf nach Wurf `wurf_nr` normal weitergewürfelt werden?"""
    return wurf_nr < wuerfe


def darf_drehen(wurf_nr: int, wuerfe: int, gedreht: bool = False) -> bool:
    """Darf nach Wurf `wurf_nr` gedreht werden? `gedreht`: in diesem Zug schon gedreht."""
    if gedreht:
        return False                 # höchstens einmal pro Zug
    if wuerfe == 3:
        return wurf_nr <= 3          # nach Wurf 3 -> Bonuswurf 4
    if wuerfe == 2:
        return wurf_nr == 1
    return False                     # Schuss


@dataclass(frozen=True)
class Option:
    aktion: str                 # "klopfen", "legen", "drehen"
    neu_fest: tuple[int, ...]   # Würfel, die danach liegen
    text: str

    @property
    def neu_wuerfeln(self) -> int:
        return 3 - len(self.neu_fest)


def optionen(wurf, wuerfeln: bool, drehen: bool) -> list[Option]:
    """Alle Entscheidungen nach einem Wurf.

    wuerfeln: normales Weiterwürfeln erlaubt
    drehen:   Drehen erlaubt
    """
    wurf = tuple(sorted(wurf))
    if len(wurf) != 3:
        raise ValueError("Ein Wurf hat drei Würfel")

    gefunden: dict[tuple[int, ...], Option] = {
        wurf: Option("klopfen", wurf, f"Klopfen ({name(bewerte(wurf))})")
    }

    if wuerfeln:
        for maske in range(7):  # alle Teilmengen außer „alle drei" (= klopfen)
            behalten = tuple(sorted(wurf[i] for i in range(3) if maske >> i & 1))
            if behalten in gefunden:
                continue
            if behalten:
                txt = f"{', '.join(map(str, behalten))} liegen lassen, {3 - len(behalten)} Würfel neu"
            else:
                txt = "Alle 3 neu würfeln"
            gefunden[behalten] = Option("legen", behalten, txt)

    if drehen and wurf.count(6) >= 2:
        rest = wurf[0] if wurf.count(6) == 2 else 6
        # Erst „2 Würfel neu“: Den dritten Würfel liegen zu lassen, ist selten sinnvoll (Reihenfolge der Knöpfe)
        for nf, txt in (
            ((1,), "6,6 zu 1 drehen, 2 Würfel neu"),
            (tuple(sorted((1, rest))), f"6,6 zu 1 drehen, {rest} liegen lassen, 1 Würfel neu"),
        ):
            if nf not in gefunden:
                gefunden[nf] = Option("drehen", nf, txt)
        if wurf.count(6) == 3 and (1, 1) not in gefunden:
            gefunden[(1, 1)] = Option("drehen", (1, 1), "6,6,6 zu 1,1 drehen, 1 Würfel neu")

    return list(gefunden.values())


def wuerfel_aktionen(wurf, option: Option) -> list[str]:
    """Was mit jedem einzelnen Würfel passiert, in der Reihenfolge von `wurf`.

    Werte: "liegen", "neu", "drehen". Beim Drehen wird aus 6,6 eine 1: eine 6
    wird auf die 1 gedreht, die andere neu gewürfelt. Aus 6,6,6 -> 1,1 werden
    zwei 6en gedreht und eine neu gewürfelt.
    """
    rest = list(option.neu_fest)
    aktionen: list[str | None] = [None] * len(wurf)
    if option.aktion == "drehen":
        gedreht = 2 if wurf.count(6) == 3 and option.neu_fest == (1, 1) else 1
        sechsen = [i for i, w in enumerate(wurf) if w == 6]
        for i in sechsen[:gedreht]:
            aktionen[i] = "drehen"
            rest.remove(1)
        aktionen[sechsen[gedreht]] = "neu"
    for i, w in enumerate(wurf):
        if aktionen[i] is None:
            if w in rest:
                rest.remove(w)
                aktionen[i] = "liegen"
            else:
                aktionen[i] = "neu"
    return aktionen


@dataclass
class Bewertung:
    option: Option
    nutzen: float                      # Chance, nicht zu verlieren (bei optimalem Weiterspiel)
    verteilung: Verteilung             # Endergebnis-Verteilung bei optimalem Weiterspiel
    bonus: float = 0.0                 # Chance auf einen Bonuswurf (Wurf 4) bei optimalem Weiterspiel

    def kategorien(self) -> dict[str, float]:
        k = {n: 0.0 for n in KATEGORIE_NAMEN.values()}
        for s, p in self.verteilung.items():
            k[KATEGORIE_NAMEN[s[0]]] += p
        return k

    def mindestens(self, kategorie: int) -> float:
        """P(Ergebnis ist mindestens diese Kategorie) – kumulativ."""
        return sum(p for s, p in self.verteilung.items() if s[0] >= kategorie)

    def erwarteter_rang(self) -> float:
        return sum(p * RANG[s] for s, p in self.verteilung.items())


class Engine:
    """Optimale Strategie für einen Durchgang mit `wuerfe` erlaubten Würfen.

    startspieler=True: Der Startspieler darf bis zu dreimal würfeln und legt
    durch sein Klopfen die Wurfgrenze der anderen fest. Klopft er nach
    Wurf k, wird sein Ergebnis gegen die Gegnerverteilung von
    `Engine(k)` bewertet (nach dem Bonuswurf gilt Grenze 3).
    """

    def __init__(self, wuerfe: int = 3, gegner: int = 1, iterationen: int = 30,
                 startspieler: bool = False):
        if wuerfe not in (1, 2, 3):
            raise ValueError("wuerfe muss 1, 2 oder 3 sein")
        if startspieler and wuerfe != 3:
            raise ValueError("Der Startspieler darf immer bis zu dreimal würfeln (wuerfe=3)")
        self.wuerfe = wuerfe
        self.gegner = gegner
        self.startspieler = startspieler
        if startspieler:
            self._nutzen_je_grenze = {k: Engine(k, gegner, iterationen).nutzen for k in (1, 2, 3)}
            self.nutzen = self._nutzen_je_grenze[3]
            self._cache = {}
            return
        self.gegner_verteilung = einzelwurf_verteilung()
        self._setze_nutzen()
        for _ in range(iterationen):
            neu = self.zustand((), 1)[1]
            diff = max(abs(neu.get(s, 0) - self.gegner_verteilung.get(s, 0))
                       for s in set(neu) | set(self.gegner_verteilung))
            self.gegner_verteilung = neu
            self._setze_nutzen()
            if diff < 1e-12:
                break

    def _setze_nutzen(self) -> None:
        self.nutzen: dict[Schluessel, float] = {}
        for w in ALLE_WUERFE:
            s = bewerte(w)
            besser = sum(p for t, p in self.gegner_verteilung.items() if t > s)
            q = besser + 0.5 * self.gegner_verteilung.get(s, 0.0)
            self.nutzen[s] = 1 - q ** self.gegner
        self._cache: dict = {}

    def endnutzen(self, wurf_nr: int) -> dict[Schluessel, float]:
        """Nutzen je Endergebnis, wenn nach Wurf Nr. `wurf_nr` geklopft wird."""
        if self.startspieler:
            return self._nutzen_je_grenze[min(wurf_nr, 3)]
        return self.nutzen

    # --- Dynamische Programmierung ------------------------------------------
    def zustand(self, fest: tuple[int, ...], wurf_nr: int, gedreht: bool = False) -> tuple[float, Verteilung, float]:
        """Wert, Endverteilung und Chance auf den Bonuswurf, wenn `fest` liegt und gleich
        Wurf Nr. `wurf_nr` folgt. `gedreht`: in diesem Zug wurde schon gedreht."""
        key = (fest, wurf_nr, gedreht)
        if key in self._cache:
            return self._cache[key]
        wert = bonus = 0.0
        vert: Verteilung = defaultdict(float)
        for ergebnis, p in wurf_verteilung(3 - len(fest)):
            beste = self.bewerte_optionen(fest + ergebnis, wurf_nr, gedreht)[0]
            wert += p * beste.nutzen
            bonus += p * beste.bonus
            for s, q in beste.verteilung.items():
                vert[s] += p * q
        self._cache[key] = (wert, dict(vert), 1.0 if wurf_nr == 4 else bonus)
        return self._cache[key]

    def bewerte_optionen(self, wurf, wurf_nr: int, gedreht: bool = False) -> list[Bewertung]:
        """Alle Optionen nach Wurf Nr. `wurf_nr`, beste zuerst."""
        wuerfeln = darf_wuerfeln(wurf_nr, self.wuerfe)
        drehen = wurf_nr <= self.wuerfe and darf_drehen(wurf_nr, self.wuerfe, gedreht)
        endnutzen = self.endnutzen(wurf_nr)
        bew = []
        for o in optionen(wurf, wuerfeln, drehen):
            if len(o.neu_fest) == 3:
                s = bewerte(o.neu_fest)
                bew.append(Bewertung(o, endnutzen[s], {s: 1.0}))
            else:
                bew.append(Bewertung(o, *self.zustand(o.neu_fest, wurf_nr + 1, gedreht or o.aktion == "drehen")))
        # Bei Gleichstand: die Option bevorzugen, die mehr liegen lässt
        bew.sort(key=lambda b: (-b.nutzen, -len(b.option.neu_fest)))
        return bew

    # --- Öffentliche API ----------------------------------------------------
    def empfehlung(self, wurf, wurf_nr: int = 1, gedreht: bool = False) -> "Empfehlung":
        """Empfehlung nach Wurf Nr. `wurf_nr` (1-basiert; 4 = Bonuswurf nach Drehen).
        `gedreht`: in diesem Zug wurde schon gedreht (dann kein zweites Mal)."""
        max_nr = 4 if self.wuerfe == 3 else self.wuerfe
        if not 1 <= wurf_nr <= max_nr:
            raise ValueError(f"wurf_nr muss zwischen 1 und {max_nr} liegen")
        return Empfehlung(self.bewerte_optionen(tuple(wurf), wurf_nr, gedreht))

    def startwert(self) -> Bewertung:
        """Chancen vor dem ersten Wurf."""
        return Bewertung(Option("start", (), "Vor dem ersten Wurf"), *self.zustand((), 1))


@dataclass
class Empfehlung:
    optionen: list[Bewertung]

    @property
    def beste(self) -> Bewertung:
        return self.optionen[0]

    def begruendung(self) -> str:
        b = self.beste
        if b.option.aktion == "klopfen":
            txt = f"{b.option.text}. Chance, nicht zu verlieren: ~{b.nutzen * 100:.0f}%."
        else:
            ziel = next((k for k in (GENERAL, MAX, PASCH, STRASSE) if b.mindestens(k) >= 0.25), STRASSE)
            txt = (f"{b.option.text} – ~{b.mindestens(ziel) * 100:.0f}% Chance auf "
                   f"{KATEGORIE_NAMEN[ziel]} oder besser, "
                   f"~{b.nutzen * 100:.0f}% Chance, nicht zu verlieren.")
            if b.bonus >= 0.05:
                txt += f" Dabei ~{b.bonus * 100:.0f}% Chance auf einen Bonuswurf."
        if len(self.optionen) > 1:
            z = self.optionen[1]
            txt += f" Nächstbeste Option: {z.option.text} ({z.nutzen * 100:.0f}%)."
        return txt
