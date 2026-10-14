"""Spielmodus für „Maxen": Durchgang, Hälfte, Runde und Sitzung als Zustandsmaschine.

Ohne Streamlit. Der Zufall kommt ausschließlich aus dem übergebenen
`random.Random`. Erlaubte Entscheidungen kommen aus `engine.optionen` mit
`darf_wuerfeln`/`darf_drehen`; eine zweite Regelimplementierung gibt es nicht.

Bedienung (UI oder Test):

    s = Sitzung([Spieler("Anna"), Spieler("Ben"), Spieler("Bot 1", Mathematiker())], random.Random(1))
    while not s.runde.beendet:
        s.bots_ziehen()
        for i in s.offen:               # Menschen, die jetzt handeln dürfen
            s.ausfuehren(option, i)     # eine von s.optionen(i)
    s.neue_runde()

Meist ist genau ein Spieler dran. Beim Schuss und beim Stechen würfeln alle
Beteiligten gleichzeitig, `s.offen` enthält dann mehrere Spieler.

Alles, was am Tisch öffentlich passiert, steht in `s.protokoll`. Wurf 1 und 2 sind
offen, Wurf 3 und der Bonuswurf tauchen erst beim Aufdecken auf.

Muss ein Mensch stechen, wartet die Auswertung des Durchgangs auf ihn:
`s.stechen` ist dann gesetzt, `s.am_zug` ist None und `s.optionen(i)` ist [WUERFELN].

Die Spieler einer Sitzung können zwischen den Runden wechseln (`beitreten`,
`verlassen`). Dann wird die Sitzordnung neu ausgelost, und die nächste Runde
beginnt mit einem Schuss. Wer mitten in einer Runde geht, hat sie verloren.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Callable

from .bots import Lage
from .engine import Empfehlung, Engine, Option, darf_drehen, darf_wuerfeln, optionen
from .regeln import GENERAL, MAX, NORMAL, PASCH, STRASSE, Schluessel, Wurf, bewerte, name, wurf_name

if TYPE_CHECKING:
    from .bots import Bot

BRICKEN = 15                         # pro Hälfte
VERTEILEN, ABGEBEN = 1, 2            # Phasen einer Hälfte

# Stand eines Zugs
BEREIT = "bereit"                    # noch nicht gewürfelt
AM_WUERFELN = "am_wuerfeln"          # nach einem Wurf, weitere Würfe möglich
VERDECKT = "verdeckt"                # Zug nach Wurf 3 vorbei, Ergebnis verdeckt bis zum Aufdecken
FERTIG = "fertig"                    # Endergebnis steht fest (nach Wurf 1 oder 2 offen)

# Stand eines Durchgangs
ZUEGE, AUFDECKEN = "zuege", "aufdecken"

WUERFELN = Option("legen", (), "Würfeln")   # der erste Wurf eines Zugs


def bricken(schluessel: Schluessel) -> int | None:
    """Bricken, die das beste Ergebnis eines Durchgangs kostet. None beim General."""
    kat, wert = schluessel
    if kat == GENERAL:
        return None
    if kat == MAX:
        return wert
    return {PASCH: 3, STRASSE: 2, NORMAL: 1}[kat]


def zeige(wurf) -> str:
    return ", ".join(map(str, sorted(wurf, reverse=True)))


@lru_cache(maxsize=None)
def standard_engine(wuerfe: int, gegner: int, startspieler: bool) -> Engine:
    return Engine(wuerfe=wuerfe, gegner=gegner, startspieler=startspieler)


@dataclass
class Spieler:
    name: str
    bot: Bot | None = None           # None = Mensch


@dataclass(frozen=True)
class Ereignis:
    art: str                         # z. B. "zug", "aufdecken", "bricken", "stechen", "verloren"
    text: str
    spieler: int | None = None


class Tisch:
    """Spieler, Zufall und Protokoll; wird an Durchgang, Hälfte und Runde weitergereicht."""

    def __init__(self, spieler: list[Spieler], rng: random.Random):
        self.spieler = spieler
        self.rng = rng
        self.protokoll: list[Ereignis] = []
        self.ausgewertet: list[Durchgang] = []   # alle ausgewerteten Durchgänge, der letzte zuletzt

    def name(self, s: int) -> str:
        return self.spieler[s].name

    def melde(self, art: str, text: str, spieler: int | None = None) -> None:
        self.protokoll.append(Ereignis(art, text, spieler))

    def wuerfle(self, anzahl: int) -> tuple[int, ...]:
        return tuple(sorted(self.rng.randint(1, 6) for _ in range(anzahl)))


def aufzaehlung(namen) -> str:
    namen = list(namen)
    return " und ".join([", ".join(namen[:-1]), namen[-1]] if len(namen) > 1 else namen)


@dataclass
class Stechen:
    """Stechen nach Augensumme. hoch=True: die höchste Summe gewinnt, sonst verliert die niedrigste.
    In jeder Würfelrunde würfelt jeder Kandidat selbst, in beliebiger Reihenfolge. Haben alle
    gewürfelt, ist die Runde abgeschlossen; bei gleicher Summe werfen nur die Gleichstehenden neu."""
    kandidaten: list[int]
    hoch: bool
    worum: str                       # z. B. "wer die Bricken bekommt"
    runden: list[dict[int, Wurf]] = field(default_factory=list)   # abgeschlossene Würfelrunden
    aktuell: dict[int, Wurf] = field(default_factory=dict)        # laufende Würfelrunde

    @property
    def entschieden(self) -> bool:
        return len(self.kandidaten) == 1

    @property
    def offen(self) -> list[int]:
        """Kandidaten, die in der laufenden Würfelrunde noch würfeln müssen."""
        return [] if self.entschieden else [s for s in self.kandidaten if s not in self.aktuell]

    def wuerfeln(self, tisch: Tisch, spieler: int | None = None) -> None:
        """`spieler` würfelt; ohne Angabe alle, die noch würfeln müssen."""
        for s in self.offen if spieler is None else [spieler]:
            if s not in self.offen:
                raise ValueError(f"{tisch.name(s)} muss nicht stechen")
            self.aktuell[s] = tisch.wuerfle(3)
        if self.offen:
            return
        wuerfe = {s: self.aktuell[s] for s in self.kandidaten}
        self.runden.append(wuerfe)
        self.aktuell = {}
        summen = {s: sum(w) for s, w in wuerfe.items()}
        ziel = max(summen.values()) if self.hoch else min(summen.values())
        tisch.melde("stechen", f"Stechen, {self.worum}: " + "; ".join(
            f"{tisch.name(s)} {zeige(w)} = {summen[s]}" for s, w in wuerfe.items()))
        self.kandidaten = [s for s in self.kandidaten if summen[s] == ziel]


@dataclass(frozen=True)
class Schritt:
    """Ein Wurf im Zug: liegen gelassene (beim Drehen inkl. der gedrehten 1en) und neu gewürfelte Würfel.
    Was liegen bleibt und wie viele Würfel neu geworfen werden, sehen alle, auch bei verdeckten Würfen."""
    fest: tuple[int, ...]
    neu: tuple[int, ...]
    gedreht: bool = False

    @property
    def wurf(self) -> Wurf:
        return tuple(sorted(self.fest + self.neu))


@dataclass
class Auswertung:
    """Ergebnis eines Durchgangs, für die Anzeige danach."""
    haelfte: Haelfte
    ergebnisse: dict[int, Wurf]
    bestes: Schluessel
    empfaenger: int                  # bekommt Bricken; beim General: hat die Hälfte verloren
    vorher: dict[int, int]           # Bricken je Spieler vor und nach dem Durchgang
    nachher: dict[int, int]
    stechen: list[Stechen]           # nur die, bei denen wirklich gewürfelt wurde
    geber: int | None = None         # Phase 2: gibt ab
    anzahl: int | None = None        # bewegte Bricken; None beim General
    phase_2: bool = False            # mit diesem Durchgang ist die Mitte leer geworden
    verloren: bool = False           # mit diesem Durchgang ist die Hälfte verloren


@dataclass
class Zug:
    """Der Zug eines Spielers in einem Durchgang."""
    spieler: int
    grenze: int | None               # erlaubte Würfe; bei den anderen erst bekannt, wenn der Startspieler fertig ist
    bestimmt_grenze: bool = False    # Startspieler, der durch sein Stehenbleiben die Grenze festlegt
    wurf_nr: int = 0                 # 4 = Bonuswurf nach Drehen beim Aufdecken
    wurf: Wurf | None = None
    stand: str = BEREIT
    aufgedeckt: bool = False         # aktueller Wurf ist für alle sichtbar (Wurf 1 und 2 immer)
    schritte: list[Schritt] = field(default_factory=list)   # alle Würfe des Zugs

    @property
    def verlauf(self) -> list[Wurf]:
        return [sch.wurf for sch in self.schritte]

    @property
    def sichtbar(self) -> int:
        """Anzahl der Würfe, deren Augen alle sehen: alle außer einem noch verdeckten letzten."""
        return len(self.schritte) - (0 if self.aufgedeckt else 1)

    def optionen(self) -> list[Option]:
        if self.stand == BEREIT:
            return [WUERFELN]
        if self.stand == AM_WUERFELN:
            return optionen(self.wurf, darf_wuerfeln(self.wurf_nr, self.grenze),
                            darf_drehen(self.wurf_nr, self.grenze))
        if self.stand == VERDECKT:
            # Beim Aufdecken darf nur nach Wurf 3 gedreht werden
            return optionen(self.wurf, False, self.wurf_nr == 3 and darf_drehen(3, self.grenze))
        return []

    def ausfuehren(self, option: Option, tisch: Tisch) -> None:
        """Übernimmt `option.neu_fest` und würfelt `option.neu_wuerfeln` Würfel neu."""
        if option not in self.optionen():
            raise ValueError(f"Nicht erlaubt: {option.text}")
        if option.aktion == "stehen":        # im Zug nur nach Wurf 1 oder 2 möglich, also offen
            self.stand = FERTIG
            return
        schritt = Schritt(option.neu_fest, tisch.wuerfle(option.neu_wuerfeln), option.aktion == "drehen")
        self.schritte.append(schritt)
        self.wurf = schritt.wurf
        self.wurf_nr += 1
        self.aufgedeckt = self.wurf_nr <= 2  # Wurf 3 und der Bonuswurf bleiben verdeckt
        if self.stand == VERDECKT:           # Bonuswurf nach dem Aufdecken
            self.stand = FERTIG
        elif self.wurf_nr < self.grenze:
            self.stand = AM_WUERFELN
        else:
            self.stand = VERDECKT if self.wurf_nr == 3 else FERTIG


class Durchgang:
    """Jeder Spieler in `reihenfolge` (Startspieler zuerst) ist einmal dran, dann wird aufgedeckt.
    Beim Schuss würfeln alle gleichzeitig; einen Startspieler gibt es dann nicht."""

    def __init__(self, tisch: Tisch, reihenfolge: list[int], schuss: bool = False, nummer: int = 1):
        self.tisch = tisch
        self.reihenfolge = list(reihenfolge)
        self.schuss = schuss
        self.nummer = nummer                     # in der Hälfte, 1-basiert
        self.auswertung: Auswertung | None = None
        self.grenze: int | None = 1 if schuss else None
        self.zuege = [
            Zug(s, grenze=1 if schuss else (3 if i == 0 else None), bestimmt_grenze=i == 0 and not schuss)
            for i, s in enumerate(self.reihenfolge)
        ]
        self.stand = ZUEGE
        self._index = 0
        self._weiter()

    @property
    def startspieler(self) -> int | None:
        return None if self.schuss else self.reihenfolge[0]

    @property
    def gegner(self) -> int:
        return len(self.reihenfolge) - 1

    @property
    def fertig(self) -> bool:
        return self.stand == FERTIG

    @property
    def offen(self) -> list[Zug]:
        """Die Züge, die eine Entscheidung brauchen (im eigenen Zug oder beim Aufdecken).
        Genau einer, nur beim Schuss alle, die noch nicht gewürfelt haben."""
        if self.fertig:
            return []
        if self.schuss:
            return [z for z in self.zuege if z.stand == BEREIT]
        return [self.zuege[self._index]]

    @property
    def am_zug(self) -> Zug | None:
        """Der erste offene Zug."""
        return next(iter(self.offen), None)

    def zug(self, spieler: int) -> Zug:
        return next(z for z in self.zuege if z.spieler == spieler)

    @property
    def ergebnisse(self) -> dict[int, Wurf]:
        if not self.fertig:
            raise ValueError("Der Durchgang läuft noch")
        return {z.spieler: z.wurf for z in self.zuege}

    def ausfuehren(self, option: Option, spieler: int | None = None) -> None:
        """Entscheidung von `spieler`; ohne Angabe für den ersten offenen Zug."""
        zug = self.am_zug if spieler is None else next((z for z in self.offen if z.spieler == spieler), None)
        if zug is None:
            raise ValueError("Der Durchgang ist beendet" if self.fertig else f"{self.tisch.name(spieler)} ist nicht dran")
        vorher, nr, beim_aufdecken = zug.wurf, zug.wurf_nr, self.stand == AUFDECKEN
        zug.ausfuehren(option, self.tisch)
        n, t = self.tisch.name(zug.spieler), self.tisch
        if beim_aufdecken:
            if option.aktion == "drehen":
                t.melde("aufdecken", f"{n} dreht ({option.text}) und würfelt den Bonuswurf verdeckt.", zug.spieler)
            else:
                t.melde("aufdecken", f"{n} dreht nicht.", zug.spieler)
        elif option.aktion == "stehen":
            t.melde("zug", f"{n} bleibt nach Wurf {nr} stehen: {zeige(zug.wurf)} ({wurf_name(zug.wurf)}).",
                    zug.spieler)
        else:
            if vorher is not None:
                t.melde("zug", f"{n}: {zeige(vorher)} – {option.text}.", zug.spieler)
            if zug.stand == VERDECKT:
                t.melde("zug", f"{n} hat dreimal gewürfelt, das Ergebnis ist verdeckt.", zug.spieler)
            elif zug.stand == FERTIG:
                woerter = {1: "einmal", 2: "zweimal"}
                t.melde("zug", f"{n} hat {woerter[zug.wurf_nr]} gewürfelt: {zeige(zug.wurf)} "
                               f"({wurf_name(zug.wurf)}).", zug.spieler)
        self._weiter()

    def _weiter(self) -> None:
        """Läuft bis zur nächsten Entscheidung oder bis zum Ende des Durchgangs."""
        t = self.tisch
        while not self.fertig:
            zug = self.zuege[self._index]
            if self.stand == ZUEGE:
                if zug.stand not in (VERDECKT, FERTIG):
                    return
                if self.grenze is None:      # der Startspieler ist fertig
                    self.grenze = zug.wurf_nr
                    for z in self.zuege[1:]:
                        z.grenze = self.grenze
                    if self.gegner:
                        t.melde("grenze", "Die anderen haben nur einen Schuss." if self.grenze == 1 else
                                f"Die anderen dürfen höchstens {self.grenze}-mal würfeln.")
                self._index += 1
                if self._index == len(self.zuege):
                    self.stand, self._index = AUFDECKEN, 0
            else:
                if zug.stand == VERDECKT and not zug.aufgedeckt:
                    zug.aufgedeckt = True
                    t.melde("aufdecken", f"{t.name(zug.spieler)} deckt auf: {zeige(zug.wurf)} "
                                         f"({wurf_name(zug.wurf)}).", zug.spieler)
                if zug.stand == VERDECKT:
                    if len(zug.optionen()) > 1:
                        return               # Drehen? Sofort entscheiden, bevor die nächsten aufdecken
                    zug.stand = FERTIG
                self._index += 1
                if self._index == len(self.zuege):
                    for z in self.zuege:
                        if z.wurf_nr == 4:
                            z.aufgedeckt = True
                            t.melde("aufdecken", f"{t.name(z.spieler)} deckt den Bonuswurf auf: "
                                                 f"{zeige(z.wurf)} ({wurf_name(z.wurf)}).", z.spieler)
                    self.stand = FERTIG


class Haelfte:
    """Eine Hälfte mit 15 Bricken: Phase 1 (Verteilen) und Phase 2 (Abgeben)."""

    def __init__(self, tisch: Tisch, teilnehmer, start: int | None, art: str, schuss: bool = False):
        self.tisch = tisch
        self.teilnehmer = list(teilnehmer)       # in Sitzordnung (Uhrzeigersinn)
        self.art = art                           # "1. Hälfte", "2. Hälfte", "Finale"
        self.mitte = BRICKEN
        self.bricken = {s: 0 for s in self.teilnehmer}
        self.phase = VERTEILEN
        self.verlierer: int | None = None
        self.durchgaenge: list[Durchgang] = []
        self.stechen: Stechen | None = None      # wartet darauf, dass ein Mensch würfelt
        self._ergebnisse: dict[int, Wurf] = {}
        self._gestochen: dict[str, Stechen] = {}  # worum -> Stechen, für die laufende Auswertung
        self._vorher: dict[int, int] = {}
        tisch.melde("haelfte", f"{art}: " + ", ".join(tisch.name(s) for s in self.teilnehmer) + ".")
        self._neuer_durchgang(start, schuss)

    @property
    def durchgang(self) -> Durchgang:
        return self.durchgaenge[-1]

    def urlaub(self, s: int) -> bool:
        return self.phase == ABGEBEN and self.bricken[s] == 0

    def aktive(self) -> list[int]:
        return [s for s in self.teilnehmer if not self.urlaub(s)]

    def _neuer_durchgang(self, start: int | None, schuss: bool = False) -> None:
        """Beim Schuss spielt `start` keine Rolle, alle würfeln gleichzeitig."""
        aktive = self.aktive()
        i = 0 if start is None else aktive.index(start)
        nr = len(self.durchgaenge) + 1
        if schuss:
            self.tisch.melde("durchgang", f"Durchgang {nr}: Schuss für alle, alle würfeln gleichzeitig.")
        else:
            self.tisch.melde("durchgang", f"Durchgang {nr}: {self.tisch.name(start)} beginnt.", start)
        self.durchgaenge.append(Durchgang(self.tisch, aktive[i:] + aktive[:i], schuss, len(self.durchgaenge) + 1))

    def ausfuehren(self, option: Option, spieler: int | None = None) -> None:
        if self.stechen is not None:
            if option != WUERFELN:
                raise ValueError("Beim Stechen wird nur gewürfelt")
            self.stechen.wuerfeln(self.tisch, spieler)
            self.werte_aus()
            return
        self.durchgang.ausfuehren(option, spieler)
        if self.durchgang.fertig:
            self.werte_aus(self.durchgang.ergebnisse)

    def _steche(self, kandidaten, hoch: bool, worum: str) -> int | None:
        """Ergebnis des Stechens; None, solange ein Mensch noch würfeln muss.
        Bots würfeln sofort, ohne Menschen unter den Gleichstehenden wird gleich weitergestochen."""
        if worum not in self._gestochen:
            if self.stechen is None:
                self.stechen = Stechen(list(kandidaten), hoch, worum)
                if not self.stechen.entschieden:
                    self.tisch.melde("stechen", "Gleichstand: " + aufzaehlung(
                        self.tisch.name(s) for s in kandidaten) + f" stechen, {worum}.")
            while not self.stechen.entschieden:
                bots = [s for s in self.stechen.offen if self.tisch.spieler[s].bot]
                if not bots:
                    return None              # nur noch Menschen müssen würfeln
                for s in bots:
                    self.stechen.wuerfeln(self.tisch, s)
            self._gestochen[worum] = self.stechen
            self.stechen = None
        return self._gestochen[worum].kandidaten[0]

    def _ausgewertet(self, bestes: Schluessel, empfaenger: int, **kw) -> None:
        d = self.durchgang
        d.auswertung = Auswertung(self, self._ergebnisse, bestes, empfaenger, self._vorher,
                                  dict(self.bricken),
                                  [st for st in self._gestochen.values() if st.runden], **kw)
        self.tisch.ausgewertet.append(d)

    def werte_aus(self, ergebnisse: dict[int, Wurf] | None = None) -> None:
        """Bricken verteilen oder abgeben, Stechen bei Gleichstand, nächsten Durchgang starten.
        Ohne `ergebnisse` geht eine Auswertung weiter, die aufs Stechen gewartet hat."""
        t = self.tisch
        if ergebnisse is not None:
            self._ergebnisse, self._gestochen, self._vorher = ergebnisse, {}, dict(self.bricken)
        schl = {s: bewerte(w) for s, w in self._ergebnisse.items()}
        hoch, tief = max(schl.values()), min(schl.values())
        beste = [s for s in schl if schl[s] == hoch]
        schlechteste = [s for s in schl if schl[s] == tief]
        anzahl = bricken(hoch)

        if anzahl is None:
            verlierer = self._steche(schlechteste, hoch=False, worum="wer die Hälfte verliert")
            if verlierer is None:
                return
            t.melde("bricken", f"General! {t.name(verlierer)} hat das schlechteste Ergebnis.", verlierer)
            self._ausgewertet(hoch, verlierer, verloren=True)
            self._verloren(verlierer)
            return

        if self.phase == VERTEILEN:
            empfaenger = self._steche(schlechteste, hoch=False, worum="wer die Bricken bekommt")
            if empfaenger is None:
                return
            n = min(anzahl, self.mitte)
            self.mitte -= n
            self.bricken[empfaenger] += n
            t.melde("bricken", f"Bestes Ergebnis: {name(hoch)}. {t.name(empfaenger)} bekommt {n} Bricken "
                               f"aus der Mitte, dort liegen noch {self.mitte}.", empfaenger)
            if self.mitte == 0 and self.bricken[empfaenger] == BRICKEN:
                self._ausgewertet(hoch, empfaenger, anzahl=n, verloren=True)
                self._verloren(empfaenger)
                return
            self._ausgewertet(hoch, empfaenger, anzahl=n, phase_2=self.mitte == 0)
            if self.mitte == 0:
                self.phase = ABGEBEN
                urlauber = [t.name(s) for s in self.teilnehmer if self.urlaub(s)]
                t.melde("phase", "Die Mitte ist leer. Phase 2: Der Beste gibt Bricken an den Schlechtesten ab."
                        + (f" Urlaub: {', '.join(urlauber)}." if urlauber else ""))
        else:
            geber = self._steche(beste, hoch=True, worum="wer abgibt")
            if geber is None:
                return
            empfaenger = self._steche([s for s in schlechteste if s != geber], hoch=False,
                                      worum="wer die Bricken bekommt")
            if empfaenger is None:
                return
            n = min(anzahl, self.bricken[geber])
            self.bricken[geber] -= n
            self.bricken[empfaenger] += n
            t.melde("bricken", f"Bestes Ergebnis: {name(hoch)}. {t.name(geber)} gibt {n} Bricken "
                               f"an {t.name(empfaenger)} ab.", empfaenger)
            verloren = self.bricken[empfaenger] == BRICKEN
            if self.bricken[geber] == 0 and not verloren:   # sonst ist die Hälfte vorbei
                t.melde("urlaub", f"{t.name(geber)} hat keine Bricken mehr und hat Urlaub.", geber)
            self._ausgewertet(hoch, empfaenger, geber=geber, anzahl=n, verloren=verloren)
            if verloren:
                self._verloren(empfaenger)
                return
        self._neuer_durchgang(empfaenger)

    def _verloren(self, s: int) -> None:
        self.verlierer = s
        artikel = "das" if self.art == "Finale" else "die"
        self.tisch.melde("verloren", f"{self.tisch.name(s)} hat {artikel} {self.art} verloren.", s)


class Runde:
    """Zwei Hälften; bei verschiedenen Verlierern ein Finale der beiden."""

    def __init__(self, tisch: Tisch, teilnehmer, start: int | None, schuss: bool = False):
        self.tisch = tisch
        self.teilnehmer = list(teilnehmer)       # in Sitzordnung
        self.haelften = [Haelfte(tisch, self.teilnehmer, start, "1. Hälfte", schuss)]
        self.verlierer: int | None = None
        self.glatter_gang = False
        self.verlassen = False                   # beendet, weil der Verlierer den Tisch verlassen hat

    @property
    def haelfte(self) -> Haelfte:
        return self.haelften[-1]

    @property
    def beendet(self) -> bool:
        return self.verlierer is not None

    def ausfuehren(self, option: Option, spieler: int | None = None) -> None:
        self.haelfte.ausfuehren(option, spieler)
        if self.haelfte.verlierer is not None:
            self.naechste_haelfte()

    def naechste_haelfte(self) -> None:
        """Nach einer verlorenen Hälfte: zweite Hälfte, Finale oder Ende der Runde."""
        v = [h.verlierer for h in self.haelften]
        if len(v) == 1:
            self.haelften.append(Haelfte(self.tisch, self.teilnehmer, v[0], "2. Hälfte"))
        elif len(v) == 2 and v[0] == v[1]:
            self.glatter_gang = True
            self._verloren(v[0], " mit einem glatten Gang")
        elif len(v) == 2:
            self.haelften.append(Haelfte(self.tisch, v, v[0], "Finale"))
        else:
            self._verloren(v[2], " im Finale")

    def abbrechen(self, s: int) -> None:
        """`s` verlässt mitten in der Runde den Tisch und hat sie damit verloren."""
        self.verlassen = True
        self.tisch.melde("verlassen", f"{self.tisch.name(s)} hat den Tisch verlassen.", s)
        self._verloren(s, "")

    def _verloren(self, s: int, wie: str) -> None:
        self.verlierer = s
        self.tisch.melde("verloren", f"{self.tisch.name(s)} hat die Runde{wie} verloren.", s)


class Sitzung(Tisch):
    """Mehrere Runden am selben Tisch, auch mit wechselnden Spielern.

    `spieler` ist ein Verzeichnis, das nur wächst: Der Index bleibt die Identität eines Spielers,
    auch wenn er geht. Wer in der laufenden Runde mitspielt und in welcher Reihenfolge,
    steht in `sitzordnung`."""

    def __init__(self, spieler: list[Spieler], rng: random.Random,
                 engine: Callable[[int, int, bool], Engine] = standard_engine):
        super().__init__(list(spieler), rng)
        self.engine = engine
        self.runden: list[Runde] = []
        self.sitzordnung: list[int] = []
        self.gegangen: set[int] = set()
        self.neue_runde()

    @property
    def runde(self) -> Runde:
        return self.runden[-1]

    @property
    def haelfte(self) -> Haelfte:
        return self.runde.haelfte

    @property
    def durchgang(self) -> Durchgang:
        return self.haelfte.durchgang

    @property
    def am_tisch(self) -> list[int]:
        """Wer an der nächsten Runde teilnimmt (Neue eingeschlossen, Gegangene nicht)."""
        return [i for i in range(len(self.spieler)) if i not in self.gegangen]

    def beitreten(self, spieler: Spieler) -> int:
        """Nimmt `spieler` ab der nächsten Runde auf. Wer mit demselben Namen (Groß-/Kleinschreibung
        egal) schon einmal am Tisch war, bekommt seinen alten Index zurück."""
        schluessel = spieler.name.strip().casefold()
        for i, sp in enumerate(self.spieler):
            if sp.name.strip().casefold() == schluessel:
                if i not in self.gegangen:
                    raise ValueError(f"{sp.name} sitzt schon am Tisch")
                self.gegangen.discard(i)
                self.spieler[i] = spieler
                return i
        self.spieler.append(spieler)
        return len(self.spieler) - 1

    def verlassen(self, s: int) -> None:
        """`s` geht. Mitten in einer Runde, an der er teilnimmt, hat er sie damit verloren."""
        if s in self.gegangen:
            return
        self.gegangen.add(s)
        if not self.runde.beendet and s in self.runde.teilnehmer:
            self.runde.abbrechen(s)

    def neue_runde(self) -> Runde:
        """Bei denselben Spielern beginnt der Verlierer der letzten Runde. Hat sich die Zusammensetzung
        geändert (und vor der allerersten Runde), wird die Sitzordnung neu ausgelost, und der erste
        Durchgang ist ein Schuss für alle."""
        if self.runden and not self.runde.beendet:
            raise ValueError("Die laufende Runde ist noch nicht beendet")
        teilnehmer = self.am_tisch
        if len(teilnehmer) < 2:
            raise ValueError("Mindestens zwei Spieler")
        self.melde("runde", f"Runde {len(self.runden) + 1} beginnt.")
        if set(teilnehmer) == set(self.sitzordnung):
            start, schuss = self.runde.verlierer, False
        else:
            self.rng.shuffle(teilnehmer)
            self.sitzordnung, start, schuss = teilnehmer, None, True
            self.melde("sitzordnung", "Neue Sitzordnung: " + ", ".join(self.name(i) for i in teilnehmer) + ".")
        self.runden.append(Runde(self, self.sitzordnung, start, schuss))
        return self.runde

    @property
    def stechen(self) -> Stechen | None:
        """Stechen, bei dem ein Mensch würfeln muss (mit `ausfuehren(WUERFELN, spieler)`)."""
        return self.haelfte.stechen

    @property
    def offen(self) -> list[int]:
        """Wer jetzt handeln darf: beim Stechen die Menschen, die noch würfeln müssen, sonst die
        offenen Züge des Durchgangs (beim Schuss mehrere)."""
        if self.runde.beendet:
            return []
        if self.stechen:
            return self.stechen.offen
        return [z.spieler for z in self.durchgang.offen]

    @property
    def am_zug(self) -> Zug | None:
        """Der erste offene Zug im Durchgang; None beim Stechen und wenn die Runde beendet ist."""
        return None if self.runde.beendet or self.stechen else self.durchgang.am_zug

    def _wer(self, spieler: int | None) -> int:
        offen = self.offen
        if spieler is None:
            if not offen:
                raise ValueError("Niemand ist dran")
            return offen[0]
        if spieler not in offen:
            raise ValueError(f"{self.name(spieler)} ist nicht dran")
        return spieler

    def optionen(self, spieler: int | None = None) -> list[Option]:
        """Optionen von `spieler` (ohne Angabe: des ersten, der dran ist); leer, wenn er nicht dran ist."""
        offen = self.offen
        if not offen or (spieler is not None and spieler not in offen):
            return []
        if self.stechen:
            return [WUERFELN]
        return self.durchgang.zug(self._wer(spieler)).optionen()

    def ausfuehren(self, option: Option, spieler: int | None = None) -> None:
        if self.runde.beendet:
            raise ValueError("Die Runde ist beendet")
        self.runde.ausfuehren(option, self._wer(spieler))

    def empfehlung(self, spieler: int | None = None) -> Empfehlung:
        """Engine-Empfehlung für den Zug von `spieler` (für Bots und Tipps), erst nach dem ersten Wurf."""
        s = self._wer(spieler)
        zug = None if self.stechen else self.durchgang.zug(s)
        if zug is None or zug.wurf is None:
            raise ValueError("Keine Entscheidung nach einem Wurf offen")
        e = self.engine(zug.grenze, self.durchgang.gegner, zug.bestimmt_grenze)
        return e.empfehlung(zug.wurf, zug.wurf_nr)

    def bots_ziehen(self) -> None:
        """Bots ziehen, bis nur noch Menschen entscheiden oder stechen müssen oder der Durchgang endet."""
        d = self.durchgang
        while self.durchgang is d and (bots := [i for i in self.offen if self.spieler[i].bot]):
            self.bot_schritt(bots[0])

    def bot_schritt(self, spieler: int | None = None) -> None:
        """Der Bot `spieler` (ohne Angabe: der erste, der dran ist) trifft seine nächste echte
        Entscheidung. Erzwungene Schritte (erster Wurf, nur eine Option) laufen ohne Bot mit."""
        s = self._wer(spieler)
        bot = self.spieler[s].bot
        if bot is None or self.stechen:
            raise ValueError("Kein Bot am Zug")
        d = self.durchgang
        while s in (z.spieler for z in d.offen):
            opts = self.optionen(s)
            if len(opts) == 1:
                self.ausfuehren(opts[0], s)
            else:
                zug = d.zug(s)
                h = self.haelfte
                lage = Lage(zug.wurf, zug.wurf_nr, zug.bestimmt_grenze, h.bricken[s], h.phase, h.mitte)
                self.ausfuehren(bot.waehle(self.empfehlung(s), self.rng, lage), s)
                return
