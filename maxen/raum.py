"""Räume für Maxen mit mehreren Menschen: Warteraum, Spiel, Bestätigungen und Zeitlimits.

Ohne Streamlit. Alle Handys eines Raums greifen auf dasselbe `Raum`-Objekt zu (in der App
über `st.cache_resource`), deshalb laufen alle öffentlichen Methoden unter einem Lock.

Menschen werden über ihren Namen erkannt (Groß-/Kleinschreibung egal). Name und Raum-ID
genügen, um nach einem Neuladen wieder auf seinen Platz zu kommen.

Gegen veraltete Klicks (Doppeltipp, Knopf aus einem alten Zustand) trägt jeder Klick die
`marke(name)` des Zustands, in dem sein Knopf gezeichnet wurde. Sie ändert sich mit jeder
eigenen Aktion und bei jedem Wechsel zwischen Spiel und Pause, nicht aber durch Aktionen der
anderen. So können beim Schuss und beim Stechen alle gleichzeitig würfeln.

`version` zählt jede Änderung. Die UI fragt regelmäßig `tick()` ab (prüft dabei die Zeitlimits)
und zeichnet neu, sobald sich die Version geändert hat. Beim Zeichnen hält sie `raum.lock`,
damit sie keinen halb geänderten Zustand sieht.

Aktionen geben zurück, ob sie gewirkt haben. Veraltete oder unerlaubte Klicks bewirken nichts.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Callable

from .bots import STUFEN, bot_namen
from .engine import Empfehlung, Engine, Option
from .spiel import Sitzung, Spieler
from .verlust import haelften_engine

WARTEN, SPIEL = "warten", "spiel"
PAUSE_DURCHGANG = 15                 # Sekunden, nur mit mindestens zwei Menschen im Raum
PAUSE_RUNDE = 120
ABLAUF = 6 * 3600                    # Räume ohne Aktivität verschwinden
MAX_BOTS = 5

Marke = tuple[int, int]


def raum_id(text: str) -> str:
    """Raum-ID ohne Leerzeichen und ohne Groß-/Kleinschreibung."""
    return "".join(text.split()).casefold()


def schluessel(name: str) -> str:
    return name.strip().casefold()


@dataclass
class Pause:
    """Nach der Auswertung eines Durchgangs oder am Ende einer Runde. Es geht weiter, wenn alle
    Menschen am Tisch bestätigt haben oder das Zeitlimit abgelaufen ist (None = kein Limit)."""
    runde: bool                      # Ende einer Runde
    seit: float
    zeitlimit: float | None
    warten_auf: set[int]             # Sitzungs-Indizes der Menschen, die noch nicht bestätigt haben


def gesperrt(methode):
    @wraps(methode)
    def mit_lock(self, *args, **kwargs):
        with self._lock:
            return methode(self, *args, **kwargs)
    return mit_lock


class Raum:
    """Ein Tisch: Menschen (in Beitrittsreihenfolge), Einstellungen des Erstellers und, sobald
    gestartet, eine `Sitzung`. Wer während eines Spiels beitritt, schaut bis zum Ende der Runde zu."""

    def __init__(self, id: str, ersteller: str, rng: random.Random | None = None,
                 engine: Callable[..., Engine] = haelften_engine,
                 uhr: Callable[[], float] = time.monotonic):
        self._lock = self.lock = threading.RLock()
        self.id = id
        self.rng = rng if rng is not None else random.Random()
        self.engine = engine
        self.uhr = uhr
        self.menschen: list[str] = []
        self.ersteller = ""
        self.bots = 0
        self.stufe = "Kneipengänger"
        self.tipps = False
        self.sitzung: Sitzung | None = None
        self.pause: Pause | None = None
        self.version = 0
        self.aktiv = uhr()
        self._index: dict[str, int] = {}     # Menschen am Tisch: Schlüssel des Namens -> Index in der Sitzung
        self._gesehen = 0                    # ausgewertete Durchgänge, deren Pause vorbei ist
        self._epoche = 0                     # Wechsel zwischen Warteraum, Spiel und Pause
        self._zaehler: dict[str, int] = {}   # eigene Aktionen je Mensch
        self.beitreten(ersteller)

    # --- Abfragen ------------------------------------------------------------------
    @property
    def status(self) -> str:
        return WARTEN if self.sitzung is None else SPIEL

    @property
    def leer(self) -> bool:
        return not self.menschen

    @property
    def zuschauer(self) -> list[str]:
        """Menschen, die während des Spiels beigetreten sind und ab der nächsten Runde mitspielen."""
        if self.sitzung is None:
            return []
        return [n for n in self.menschen if schluessel(n) not in self._index]

    @property
    def ausgewertet(self):
        """Der Durchgang, dessen Auswertung die Pause zeigt; None ohne Pause oder wenn die Runde
        ohne neue Auswertung endete (jemand hat den Tisch verlassen)."""
        s = self.sitzung
        if self.pause is None or len(s.ausgewertet) <= self._gesehen:
            return None
        return s.ausgewertet[-1]

    @gesperrt
    def ist_da(self, name: str) -> bool:
        """`name` ist im Raum (nicht gegangen und nicht entfernt)."""
        return any(schluessel(n) == schluessel(name) for n in self.menschen)

    def index(self, name: str) -> int | None:
        """Platz von `name` in der Sitzung; None im Warteraum und für Zuschauer."""
        return self._index.get(schluessel(name))

    @gesperrt
    def marke(self, name: str) -> Marke:
        return self._epoche, self._zaehler.get(schluessel(name), 0)

    @gesperrt
    def optionen(self, name: str) -> list[Option]:
        i = self.index(name)
        if i is None or self.pause is not None:
            return []
        return self.sitzung.optionen(i)

    @gesperrt
    def empfehlung(self, name: str) -> Empfehlung:
        return self.sitzung.empfehlung(self.index(name))

    @gesperrt
    def restzeit(self) -> float | None:
        """Sekunden bis zum Ende der Pause; None ohne Pause oder ohne Zeitlimit."""
        p = self.pause
        if p is None or p.zeitlimit is None:
            return None
        return max(0.0, p.zeitlimit - (self.uhr() - p.seit))

    @gesperrt
    def tick(self) -> int:
        """Prüft das Zeitlimit der Pause und gibt die aktuelle Version zurück."""
        p = self.pause
        if p is not None and p.zeitlimit is not None and self.uhr() - p.seit >= p.zeitlimit:
            self._pause_ende()
            self._geaendert()
        return self.version

    # --- Warteraum -----------------------------------------------------------------
    @gesperrt
    def beitreten(self, name: str) -> str:
        """Tritt bei oder kehrt mit demselben Namen zurück. Gibt den Namen zurück, wie er im Raum steht."""
        name = name.strip()
        if not name:
            raise ValueError("Bitte einen Namen eingeben")
        k = schluessel(name)
        for n in self.menschen:
            if schluessel(n) == k:
                return n
        if self.sitzung and any(sp.bot and schluessel(sp.name) == k for sp in self.sitzung.spieler):
            raise ValueError(f"{name} spielt hier schon als Computergegner mit")
        self.menschen.append(name)
        if not self.ersteller:
            self.ersteller = name
        self._geaendert()
        return name

    @gesperrt
    def einstellen(self, von: str, bots: int | None = None, stufe: str | None = None,
                   tipps: bool | None = None) -> bool:
        """Nur der Ersteller. Bots und Stärke nur im Warteraum, Tipps jederzeit."""
        if not self._ist_ersteller(von):
            return False
        if (bots is not None or stufe is not None) and self.sitzung is not None:
            return False
        if bots is not None:
            if not 0 <= bots <= MAX_BOTS:
                raise ValueError(f"Höchstens {MAX_BOTS} Computergegner")
            self.bots = bots
        if stufe is not None:
            if stufe not in STUFEN:
                raise ValueError(f"Unbekannte Stärke: {stufe}")
            self.stufe = stufe
        if tipps is not None:
            self.tipps = tipps
        self._geaendert()
        return True

    @gesperrt
    def starten(self, von: str, marke: Marke) -> bool:
        if not self._ist_ersteller(von) or marke != self.marke(von) or self.sitzung is not None:
            return False
        if len(self.menschen) + self.bots < 2:
            raise ValueError("Mindestens zwei Spieler")
        spieler = [Spieler(n) for n in self.menschen]
        spieler += [Spieler(n, STUFEN[self.stufe]()) for n in bot_namen(self.bots, self.rng, self.menschen)]
        self.sitzung = Sitzung(spieler, self.rng, engine=self.engine)
        self._index = {schluessel(n): i for i, n in enumerate(self.menschen)}
        self._gesehen, self.pause = 0, None
        self._epoche += 1
        self._weiter()
        self._geaendert()
        return True

    @gesperrt
    def beenden(self, von: str, marke: Marke) -> bool:
        """Der Ersteller beendet das Spiel. Alle, auch die Zuschauer, sind wieder im Warteraum."""
        if not self._ist_ersteller(von) or marke != self.marke(von) or self.sitzung is None:
            return False
        self._zum_warteraum()
        self._geaendert()
        return True

    @gesperrt
    def entfernen(self, von: str, marke: Marke, name: str) -> bool:
        """Der Ersteller entfernt einen anderen Menschen; im Spiel wirkt das wie Verlassen."""
        if not self._ist_ersteller(von) or marke != self.marke(von) or schluessel(name) == schluessel(von):
            return False
        return self.verlassen(name)

    @gesperrt
    def verlassen(self, name: str) -> bool:
        """`name` geht. Mitten in einer Runde hat er sie damit verloren. Der Ersteller gibt seine
        Rolle an den nächsten Menschen ab."""
        k = schluessel(name)
        n = next((m for m in self.menschen if schluessel(m) == k), None)
        if n is None:
            return False
        self.menschen.remove(n)
        if self.ersteller == n:
            self.ersteller = self.menschen[0] if self.menschen else ""
        i = self._index.pop(k, None)
        if not self.menschen:
            self.sitzung, self.pause = None, None
        elif i is not None:
            s = self.sitzung
            lief = not s.runde.beendet
            s.verlassen(i)
            if lief and s.runde.beendet and self.pause is not None and not self.pause.runde:
                self.pause = None            # statt der Auswertung des Durchgangs: Ende der Runde
            if self.pause is None:
                self._weiter()
            else:
                self.pause.warten_auf.discard(i)
                if not self.pause.warten_auf:
                    self._pause_ende()
        self._geaendert()
        return True

    # --- Spiel ---------------------------------------------------------------------
    @gesperrt
    def ausfuehren(self, name: str, marke: Marke, option: Option) -> bool:
        i = self.index(name)
        if i is None or self.pause is not None or marke != self.marke(name):
            return False
        try:
            self.sitzung.ausfuehren(option, i)
        except ValueError:
            return False
        self._gemacht(name)
        self._weiter()
        self._geaendert()
        return True

    @gesperrt
    def bestaetigen(self, name: str, marke: Marke) -> bool:
        """Bestätigt die Auswertung bzw. das Ende der Runde."""
        i = self.index(name)
        if self.pause is None or i not in self.pause.warten_auf or marke != self.marke(name):
            return False
        self.pause.warten_auf.discard(i)
        self._gemacht(name)
        if not self.pause.warten_auf:
            self._pause_ende()
        self._geaendert()
        return True

    # --- intern --------------------------------------------------------------------
    def _ist_ersteller(self, name: str) -> bool:
        return bool(self.ersteller) and schluessel(name) == schluessel(self.ersteller)

    def _geaendert(self) -> None:
        self.version += 1
        self.aktiv = self.uhr()

    def _gemacht(self, name: str) -> None:
        k = schluessel(name)
        self._zaehler[k] = self._zaehler.get(k, 0) + 1

    def _weiter(self) -> None:
        """Bots ziehen lassen, bis ein Mensch handeln muss. Nach einer Auswertung und am Ende
        einer Runde beginnt eine Pause."""
        s = self.sitzung
        while self.pause is None:
            if len(s.ausgewertet) > self._gesehen or s.runde.beendet:
                self._neue_pause()
                return
            if not any(s.spieler[i].bot for i in s.offen):
                return
            s.bots_ziehen()

    def _neue_pause(self) -> None:
        s = self.sitzung
        runde = s.runde.beendet
        limit = (PAUSE_RUNDE if runde else PAUSE_DURCHGANG) if len(self.menschen) >= 2 else None
        am_tisch = {i for i in s.sitzordnung if s.spieler[i].bot is None and i not in s.gegangen}
        if not runde:
            # Wer im Durchgang nicht gespielt hat (Urlaub, nicht im Finale), muss nicht bestätigen,
            # es sei denn, es hat gar kein Mensch gespielt: dann wartet das Spiel auf alle.
            am_tisch = am_tisch & set(s.ausgewertet[-1].reihenfolge) or am_tisch
        self.pause = Pause(runde, self.uhr(), limit, am_tisch)
        self._epoche += 1
        if not am_tisch:
            self._pause_ende()

    def _pause_ende(self) -> None:
        """Weiter zum nächsten Durchgang. Am Ende einer Runde steigen die Zuschauer ein,
        und die nächste Runde beginnt."""
        s = self.sitzung
        self.pause = None
        self._gesehen = len(s.ausgewertet)
        self._epoche += 1
        if s.runde.beendet:
            for n in self.zuschauer:
                self._index[schluessel(n)] = s.beitreten(Spieler(n))
            if len(s.am_tisch) < 2 or not self._index:
                self._zum_warteraum()
                return
            s.neue_runde()
        self._weiter()

    def _zum_warteraum(self) -> None:
        self.sitzung, self.pause = None, None
        self._index, self._gesehen = {}, 0
        self._epoche += 1


class Raeume:
    """Alle Räume des Prozesses. Ein Raum entsteht, wenn jemand eine neue Raum-ID betritt,
    und verschwindet, wenn der letzte Mensch geht oder nach `ablauf` Sekunden ohne Änderung."""

    def __init__(self, rng_fabrik: Callable[[], random.Random] = random.Random,
                 engine: Callable[..., Engine] = haelften_engine,
                 uhr: Callable[[], float] = time.monotonic, ablauf: float = ABLAUF):
        self.rng_fabrik = rng_fabrik
        self.engine = engine
        self.uhr = uhr
        self.ablauf = ablauf
        self._raeume: dict[str, Raum] = {}
        self._lock = threading.Lock()

    def betreten(self, raum: str, name: str, rng: random.Random | None = None) -> tuple[Raum, str]:
        """Tritt dem Raum bei oder erstellt ihn (mit `rng`, sonst aus `rng_fabrik`).
        Gibt den Raum und den Namen zurück, wie er dort steht."""
        rid = raum_id(raum)
        if not rid:
            raise ValueError("Bitte eine Raum-ID eingeben")
        with self._lock:
            self._aufraeumen()
            r = self._raeume.get(rid)
            if r is None:
                r = Raum(rid, name, rng or self.rng_fabrik(), self.engine, self.uhr)
                self._raeume[rid] = r
                return r, r.ersteller
            return r, r.beitreten(name)

    def raum(self, raum: str) -> Raum | None:
        with self._lock:
            return self._raeume.get(raum_id(raum))

    def liste(self) -> list[Raum]:
        """Alle aktiven Räume, zuletzt geänderte zuerst (für die Auswahl beim Einstieg)."""
        with self._lock:
            self._aufraeumen()
            return sorted(self._raeume.values(), key=lambda r: r.aktiv, reverse=True)

    def verlassen(self, raum: str, name: str) -> None:
        with self._lock:
            r = self._raeume.get(raum_id(raum))
            if r is None:
                return
            r.verlassen(name)
            if r.leer:
                del self._raeume[r.id]

    def _aufraeumen(self) -> None:
        jetzt = self.uhr()
        for rid in [rid for rid, r in self._raeume.items() if r.leer or jetzt - r.aktiv > self.ablauf]:
            del self._raeume[rid]
