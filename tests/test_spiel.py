import random

import pytest

from maxen.bots import Anfaenger, Kneipengaenger, Mathematiker
from maxen.engine import Option
from maxen.verlust import haelften_engine
from maxen.regeln import bewerte
from maxen.spiel import (
    ABGEBEN, AM_WUERFELN, BRICKEN, FERTIG, VERDECKT, WUERFELN,
    Durchgang, Haelfte, Runde, Schritt, Sitzung, Spieler, Stechen, Tisch, Zug, bricken,
)


class GezinkterZufall:
    """Liefert die vorgegebenen Augenzahlen der Reihe nach."""

    def __init__(self, augen):
        self.augen = list(augen)

    def randint(self, a, b):
        return self.augen.pop(0)


def tisch(augen=(), n=3, bots=False):
    """`bots`: True = alle Bots, eine Menge = diese Plätze sind Bots, sonst nur Menschen."""
    ist_bot = (lambda i: bots) if isinstance(bots, bool) else (lambda i: i in bots)
    return Tisch([Spieler(f"S{i}", Mathematiker() if ist_bot(i) else None) for i in range(n)], GezinkterZufall(augen))


def waehle(ziel, neu_fest=None, aktion=None) -> Option:
    """Option des Zugs (oder der Sitzung) mit passendem neu_fest bzw. passender Aktion."""
    return next(o for o in ziel.optionen()
                if (neu_fest is None or o.neu_fest == neu_fest) and (aktion is None or o.aktion == aktion))


def texte(t):
    return [e.text for e in t.protokoll]


# --- Bricken -----------------------------------------------------------------
def test_bricken_tabelle():
    assert bricken(bewerte((1, 1, 1))) is None
    assert bricken(bewerte((1, 1, 6))) == 6
    assert bricken(bewerte((1, 1, 2))) == 2
    assert bricken(bewerte((6, 6, 6))) == 3
    assert bricken(bewerte((2, 2, 2))) == 3
    assert bricken(bewerte((6, 5, 4))) == 2
    assert bricken(bewerte((3, 2, 1))) == 2
    assert bricken(bewerte((6, 6, 5))) == 1


# --- Zug -----------------------------------------------------------------------
def test_option_anwenden_inkl_drehen():
    t = tisch([6, 6, 3, 5])
    z = Zug(0, grenze=3, bestimmt_grenze=True)
    assert z.optionen() == [WUERFELN]
    z.ausfuehren(WUERFELN, t)
    assert (z.wurf, z.wurf_nr, z.stand) == ((3, 6, 6), 1, AM_WUERFELN)
    z.ausfuehren(waehle(z, (1, 3)), t)       # 6,6 zu 1 drehen, 3 liegen lassen
    assert (z.wurf, z.wurf_nr) == ((1, 3, 5), 2)
    with pytest.raises(ValueError):
        z.ausfuehren(Option("legen", (6,), "6 liegen lassen"), t)


def test_drehen_nur_zu_erlaubten_zeitpunkten():
    def dreht(grenze, nr, stand):
        z = Zug(0, grenze=grenze, wurf_nr=nr, wurf=(2, 6, 6), stand=stand)
        return any(o.aktion == "drehen" for o in z.optionen())
    assert dreht(3, 1, AM_WUERFELN) and dreht(3, 2, AM_WUERFELN)
    assert dreht(3, 3, VERDECKT)              # beim Aufdecken -> Bonuswurf
    assert not dreht(3, 2, VERDECKT)          # nach Wurf 2 geklopft: kein Drehen beim Aufdecken
    assert not dreht(3, 4, FERTIG)            # nach dem Bonuswurf ist Schluss
    assert dreht(2, 1, AM_WUERFELN)
    assert not dreht(2, 2, VERDECKT)
    assert not dreht(1, 1, VERDECKT)


def test_nur_einmal_drehen_pro_zug():
    t = tisch([6, 6, 2,  6, 6,  6, 6])
    z = Zug(0, grenze=3, bestimmt_grenze=True)
    z.ausfuehren(WUERFELN, t)
    z.ausfuehren(waehle(z, (1,)), t)          # 6,6 zu 1 drehen, 2 Würfel neu
    assert z.gedreht and (z.wurf, z.wurf_nr) == ((1, 6, 6), 2)
    assert all(o.aktion != "drehen" for o in z.optionen())      # wieder 6,6: kein zweites Mal
    z.ausfuehren(waehle(z, (1,)), t)
    assert (z.wurf, z.stand) == ((1, 6, 6), VERDECKT)
    assert [o.aktion for o in z.optionen()] == ["klopfen"]       # auch beim Aufdecken kein Bonuswurf


# --- Durchgang ---------------------------------------------------------------
def test_wurfgrenze_durch_startspieler():
    t = tisch([2, 3, 5,  6, 4, 4,  6, 6, 2,  3,  1, 1, 4])
    d = Durchgang(t, [0, 1, 2])
    d.ausfuehren(WUERFELN)
    d.ausfuehren(waehle(d.am_zug, ()))        # alle neu
    d.ausfuehren(waehle(d.am_zug, aktion="klopfen"))
    assert d.grenze == 2
    assert d.zug(0).aufgedeckt and d.zug(0).stand == FERTIG    # nach Wurf 2 geklopft: offen
    assert d.am_zug.spieler == 1 and d.am_zug.grenze == 2
    d.ausfuehren(WUERFELN)                    # 6,6,2: nach Wurf 1 darf gedreht werden
    assert d.am_zug.aufgedeckt
    d.ausfuehren(waehle(d.am_zug, (1, 2)))    # -> 1,2,3, Zug ist nach Wurf 2 automatisch vorbei
    assert d.zug(1).verlauf == [(2, 6, 6), (1, 2, 3)]
    assert d.zug(1).schritte[1] == Schritt((1, 2), (3,), gedreht=True)
    assert d.zug(1).stand == VERDECKT and not d.zug(1).aufgedeckt   # letzter erlaubter Wurf: verdeckt
    assert d.am_zug.spieler == 2
    d.ausfuehren(WUERFELN)
    d.ausfuehren(waehle(d.am_zug, aktion="klopfen"))
    assert d.fertig and all(z.aufgedeckt for z in d.zuege)
    assert d.ergebnisse == {0: (4, 4, 6), 1: (1, 2, 3), 2: (1, 1, 4)}
    assert "Die anderen dürfen höchstens 2-mal würfeln." in texte(t)
    assert "S0 klopft nach Wurf 2: 6, 4, 4 (644)." in texte(t)
    assert "S1 hat zweimal gewürfelt, das Ergebnis ist verdeckt." in texte(t)
    assert "S1 deckt auf: 3, 2, 1 (Straße 3)." in texte(t)
    assert [e.spieler for e in t.protokoll if e.art == "aufdecken"] == [1]   # nur S1 war verdeckt


def test_schuss():
    t = tisch([6, 6, 6,  1, 2, 4], n=2)
    d = Durchgang(t, [0, 1], schuss=True)
    d.ausfuehren(WUERFELN)
    assert d.am_zug.spieler == 1              # kein Drehen, kein zweiter Wurf
    assert d.zug(0).aufgedeckt and "S0 hat einmal gewürfelt: 6, 6, 6 (6er Pasch)." in texte(t)
    d.ausfuehren(WUERFELN)
    assert d.fertig and d.ergebnisse == {0: (6, 6, 6), 1: (1, 2, 4)}


def test_schuss_alle_gleichzeitig():
    t = tisch([1, 2, 4,  6, 6, 6,  3, 3, 5])
    d = Durchgang(t, [0, 1, 2], schuss=True)
    assert d.startspieler is None and [z.spieler for z in d.offen] == [0, 1, 2]
    d.ausfuehren(WUERFELN, 2)                 # beliebige Reihenfolge
    d.ausfuehren(WUERFELN, 0)
    assert [z.spieler for z in d.offen] == [1]
    with pytest.raises(ValueError):
        d.ausfuehren(WUERFELN, 0)             # hat schon gewürfelt
    d.ausfuehren(WUERFELN, 1)
    assert d.fertig and d.ergebnisse == {0: (6, 6, 6), 1: (3, 3, 5), 2: (1, 2, 4)}


def test_drehen_beim_aufdecken_sofort():
    t = tisch([2, 3, 5,  2, 3, 5,  6, 6, 2,  2, 3, 5,  2, 3, 5,  4, 4, 4,  1], n=2)
    d = Durchgang(t, [0, 1])
    d.ausfuehren(WUERFELN)
    d.ausfuehren(waehle(d.am_zug, ()))
    assert d.zug(0).aufgedeckt                # Wurf 2 ist offen
    d.ausfuehren(waehle(d.am_zug, ()))        # Wurf 3: 6,6,2, im Zug keine Entscheidung mehr
    assert d.grenze == 3 and d.am_zug.spieler == 1 and not d.zug(0).aufgedeckt
    assert d.zug(0).sichtbar == 2 and len(d.zug(0).verlauf) == 3
    assert texte(t)[-2] == "S0 hat dreimal gewürfelt, das Ergebnis ist verdeckt."
    for _ in range(3):
        d.ausfuehren(waehle(d.am_zug, ()))    # S1: dreimal alle neu, zuletzt 4,4,4
    # Aufdecken: Startspieler deckt auf und muss sofort entscheiden, S1 hat noch nicht aufgedeckt
    z = d.am_zug
    assert z.spieler == 0 and z.aufgedeckt and not d.zug(1).aufgedeckt
    assert {o.aktion for o in z.optionen()} == {"klopfen", "drehen"}
    assert texte(t)[-1] == "S0 deckt auf: 6, 6, 2 (662)."
    d.ausfuehren(waehle(z, (1, 2)))           # Bonuswurf: 1 -> Max 2
    assert d.fertig
    assert d.ergebnisse == {0: (1, 1, 2), 1: (4, 4, 4)}
    assert texte(t)[-3:] == [
        "S0 dreht (6,6 zu 1 drehen, 2 liegen lassen, 1 Würfel neu) und würfelt den Bonuswurf verdeckt.",
        "S1 deckt auf: 4, 4, 4 (4er Pasch).",
        "S0 deckt den Bonuswurf auf: 2, 1, 1 (Max 2).",
    ]


def test_kein_drehen_beim_aufdecken_nach_wurf_2():
    t = tisch([2, 3, 5,  6, 6, 2,  3, 3, 3], n=2)
    d = Durchgang(t, [0, 1])
    d.ausfuehren(WUERFELN)
    d.ausfuehren(waehle(d.am_zug, ()))
    d.ausfuehren(waehle(d.am_zug, aktion="klopfen"))   # mit 6,6,2 nach Wurf 2
    d.ausfuehren(WUERFELN)
    d.ausfuehren(waehle(d.am_zug, aktion="klopfen"))
    assert d.fertig and d.ergebnisse[0] == (2, 6, 6)


# --- Hälfte --------------------------------------------------------------------
def test_verteilen_mit_rest_der_mitte():
    """Beispiel des Nutzers: Max 6, Peter 8, Laura 0 Bricken, in der Mitte liegt noch 1."""
    t = tisch()
    h = Haelfte(t, [0, 1, 2], 0, "1. Hälfte")
    h.mitte, h.bricken = 1, {0: 6, 1: 8, 2: 0}
    h.werte_aus({0: (4, 4, 6), 1: (1, 1, 5), 2: (2, 3, 4)})   # Max 5 kostet 5, es liegt nur 1
    assert h.mitte == 0 and h.bricken == {0: 7, 1: 8, 2: 0}
    assert h.phase == ABGEBEN and h.urlaub(2) and h.verlierer is None
    assert h.durchgang.reihenfolge == [0, 1]                  # wer Bricken bekam, beginnt
    a = h.durchgaenge[0].auswertung
    assert (a.empfaenger, a.geber, a.anzahl, a.phase_2, a.verloren) == (0, None, 1, True, False)
    assert a.vorher == {0: 6, 1: 8, 2: 0} and a.nachher == {0: 7, 1: 8, 2: 0}
    assert t.ausgewertet == [h.durchgaenge[0]] and h.durchgang.auswertung is None


def test_verteilen_einer_hat_alle():
    h = Haelfte(tisch(), [0, 1, 2], 0, "1. Hälfte")
    h.mitte, h.bricken = 3, {0: 12, 1: 0, 2: 0}
    h.werte_aus({0: (2, 4, 6), 1: (3, 3, 3), 2: (6, 5, 2)})
    assert h.verlierer == 0 and h.bricken[0] == BRICKEN


def test_abgeben():
    h = Haelfte(tisch(), [0, 1, 2], 0, "1. Hälfte")
    h.mitte, h.phase, h.bricken = 0, ABGEBEN, {0: 5, 1: 6, 2: 4}
    h.werte_aus({0: (3, 3, 3), 1: (1, 2, 4), 2: (2, 5, 6)})   # Pasch: 3 von S0 an S1
    assert h.bricken == {0: 2, 1: 9, 2: 4}
    assert h.durchgang.reihenfolge == [1, 2, 0]
    h.werte_aus({0: (1, 1, 6), 1: (2, 3, 5), 2: (4, 4, 5)})   # Max 6, S0 hat nur noch 2
    assert h.bricken == {0: 0, 1: 11, 2: 4} and h.urlaub(0)
    assert h.durchgang.reihenfolge == [1, 2]
    h.werte_aus({1: (1, 1, 4), 2: (2, 3, 5)})                 # Max 4: S1 gibt 4 an S2
    assert h.bricken == {0: 0, 1: 7, 2: 8}
    h.werte_aus({1: (2, 3, 5), 2: (1, 1, 6)})                 # S2 gibt 6 an S1
    h.werte_aus({1: (2, 3, 5), 2: (1, 1, 2)})                 # S2 gibt die letzten 2 ab
    assert h.bricken == {0: 0, 1: BRICKEN, 2: 0} and h.verlierer == 1
    a = h.durchgang.auswertung
    assert (a.empfaenger, a.geber, a.anzahl, a.verloren) == (1, 2, 2, True)
    # Wer die letzten Bricken abgibt, während der andere alle 15 hat, geht nicht in Urlaub: Die Hälfte ist vorbei
    assert [e.spieler for e in h.tisch.protokoll if e.art == "urlaub"] == [0]


def test_general_beendet_haelfte():
    h = Haelfte(tisch(), [0, 1, 2], 0, "1. Hälfte")
    h.werte_aus({0: (1, 1, 1), 1: (1, 1, 1), 2: (6, 6, 6)})   # zwei Generäle, S2 ist Schlechtester
    assert h.verlierer == 2 and h.mitte == BRICKEN
    h = Haelfte(tisch(), [0, 1, 2], 0, "1. Hälfte")
    h.mitte, h.phase, h.bricken = 0, ABGEBEN, {0: 5, 1: 6, 2: 4}
    h.werte_aus({0: (1, 1, 1), 1: (4, 5, 6), 2: (2, 3, 5)})   # auch in Phase 2
    assert h.verlierer == 2


def test_stechen_nach_augensumme():
    # 6,5,1 und 4,4,4 haben beide 12 -> nur diese beiden werfen neu
    t = tisch([6, 5, 1,  4, 4, 4,  6, 6, 6,  1, 1, 2,  3, 3, 3])
    st = Stechen([0, 1, 2], hoch=False, worum="wer die Bricken bekommt")
    st.wuerfeln(t)
    assert st.kandidaten == [0, 1] and not st.entschieden
    st.wuerfeln(t)
    assert st.entschieden and st.kandidaten == [0]
    # Phase 2: erst unter den Besten, wer abgibt, dann unter den Schlechtesten.
    # Menschen würfeln selbst: Die Auswertung wartet vor jeder Stechrunde.
    t = tisch([2, 3, 5,  4, 5, 6,  1, 2, 3,  6, 6, 6], n=4)
    h = Haelfte(t, [0, 1, 2, 3], 0, "1. Hälfte")
    h.mitte, h.phase, h.bricken = 0, ABGEBEN, {0: 4, 1: 4, 2: 4, 3: 3}
    h.werte_aus({0: (1, 1, 3), 1: (1, 1, 3), 2: (2, 4, 6), 3: (2, 4, 6)})
    assert (h.stechen.worum, h.stechen.kandidaten) == ("wer abgibt", [0, 1])
    assert texte(t)[-1] == "Gleichstand: S0 und S1 stechen, wer abgibt."
    with pytest.raises(ValueError):
        h.ausfuehren(Option("klopfen", (1, 1, 3), "Klopfen"))
    h.ausfuehren(WUERFELN)
    assert (h.stechen.worum, h.stechen.kandidaten) == ("wer die Bricken bekommt", [2, 3])
    h.ausfuehren(WUERFELN)
    assert h.stechen is None and h.bricken == {0: 4, 1: 1, 2: 7, 3: 3}   # S1 (15) gibt an S2 (6)
    a = h.durchgaenge[0].auswertung
    assert [(x.worum, x.runden) for x in a.stechen] == [
        ("wer abgibt", [{0: (2, 3, 5), 1: (4, 5, 6)}]),
        ("wer die Bricken bekommt", [{2: (1, 2, 3), 3: (6, 6, 6)}]),
    ]


def test_stechen_jeder_wuerfelt_selbst():
    """Zwei Menschen und ein Bot stechen: Der Bot würfelt sofort, die Menschen in beliebiger Reihenfolge."""
    t = tisch([6, 6, 6,  1, 2, 3,  1, 2, 3,  4, 4, 4,  1, 1, 1], bots={2})
    h = Haelfte(t, [0, 1, 2], 0, "1. Hälfte")
    h.werte_aus({0: (2, 4, 5), 1: (2, 4, 5), 2: (2, 4, 5)})
    st = h.stechen
    assert st.offen == [0, 1] and st.aktuell == {2: (6, 6, 6)}
    with pytest.raises(ValueError):
        h.ausfuehren(WUERFELN, 2)             # der Bot hat schon gewürfelt
    h.ausfuehren(WUERFELN, 1)
    assert st.offen == [0]
    h.ausfuehren(WUERFELN, 0)                 # 6 und 6: S0 und S1 stechen weiter, der Bot ist raus
    assert st.kandidaten == [0, 1] and st.offen == [0, 1] and st.aktuell == {}
    assert texte(t)[-1] == "Stechen, wer die Bricken bekommt: S0 3, 2, 1 = 6; S1 3, 2, 1 = 6; S2 6, 6, 6 = 18"
    h.ausfuehren(WUERFELN, 1)
    h.ausfuehren(WUERFELN, 0)
    assert h.stechen is None and h.bricken == {0: 1, 1: 0, 2: 0}
    assert h.durchgaenge[0].auswertung.stechen[0].runden == [
        {0: (1, 2, 3), 1: (1, 2, 3), 2: (6, 6, 6)}, {0: (1, 1, 1), 1: (4, 4, 4)}]


def test_stechen_unter_bots_sofort():
    t = tisch([6, 5, 1,  4, 4, 4,  1, 1, 2,  3, 3, 3], bots=True)
    h = Haelfte(t, [0, 1, 2], 0, "1. Hälfte")
    h.werte_aus({0: (2, 4, 5), 1: (2, 4, 5), 2: (6, 6, 6)})
    assert h.stechen is None and h.bricken == {0: 3, 1: 0, 2: 0}
    assert [e.art for e in t.protokoll][-5:] == ["stechen", "stechen", "stechen", "bricken", "durchgang"]


def test_stechen_wenn_alle_gleich():
    """Phase 2, alle gleich: ein gemeinsames Stechen. Höchste Summe gibt ab, niedrigste bekommt;
    nur wer dort gleichauf liegt, sticht noch einmal."""
    def stich(augen, n=3):
        t = tisch(augen, n=n)
        h = Haelfte(t, list(range(n)), 0, "Finale")
        h.mitte, h.phase, h.bricken = 0, ABGEBEN, {i: 5 for i in range(n)}
        h.werte_aus({i: (2, 4, 6) for i in range(n)})   # 1 Bricken
        assert h.stechen.worum == "wer abgibt und wer die Bricken bekommt"
        while h.stechen is not None:
            h.ausfuehren(WUERFELN)
        a = h.durchgaenge[0].auswertung
        return (a.geber, a.empfaenger), [(x.worum, len(x.runden)) for x in a.stechen]

    gemeinsam = "wer abgibt und wer die Bricken bekommt"
    # zu zweit reicht ein Stechen
    assert stich([6, 6, 6,  1, 1, 1], n=2) == ((0, 1), [(gemeinsam, 1)])
    # 15, 10, 8: Sieger und Verlierer klar
    assert stich([5, 5, 5,  4, 3, 3,  2, 3, 3]) == ((0, 2), [(gemeinsam, 1)])
    # 15, 15, 8: S0 und S1 stechen noch einmal, wer abgibt; S2 bekommt
    assert stich([5, 5, 5,  5, 5, 5,  2, 3, 3,  1, 1, 1,  6, 6, 6]) == (
        (1, 2), [(gemeinsam, 1), ("wer abgibt", 1)])
    # 15, 8, 8: S1 und S2 stechen noch einmal, wer die Bricken bekommt
    assert stich([5, 5, 5,  2, 3, 3,  2, 3, 3,  6, 6, 6,  1, 1, 1]) == (
        (0, 2), [(gemeinsam, 1), ("wer die Bricken bekommt", 1)])
    # wieder alle gleich (12, 12, 12): alle stechen noch einmal gemeinsam
    assert stich([4, 4, 4,  6, 5, 1,  3, 4, 5,  5, 5, 5,  4, 3, 3,  2, 3, 3]) == ((0, 2), [(gemeinsam, 2)])


# --- Runde ---------------------------------------------------------------------
GENERAL_FUER = {
    # Ergebnisse, bei denen der Spieler mit dem Schlüssel verliert
    0: {0: (2, 4, 5), 1: (1, 1, 1), 2: (6, 6, 6)},
    1: {0: (1, 1, 1), 1: (2, 4, 5), 2: (6, 6, 6)},
    2: {0: (1, 1, 1), 1: (6, 6, 6), 2: (2, 4, 5)},
}


def test_runde_finale_und_startspieler():
    r = Runde(tisch(), [0, 1, 2], start=0)
    r.haelfte.werte_aus(GENERAL_FUER[1])
    r.naechste_haelfte()
    assert r.haelfte.art == "2. Hälfte" and r.haelfte.durchgang.startspieler == 1
    assert r.haelfte.teilnehmer == [0, 1, 2]
    r.haelfte.werte_aus(GENERAL_FUER[2])
    r.naechste_haelfte()
    assert r.haelfte.art == "Finale" and r.haelfte.teilnehmer == [1, 2]
    assert r.haelfte.durchgang.startspieler == 1               # Verlierer der ersten Hälfte
    r.haelfte.werte_aus({1: (1, 1, 1), 2: (2, 4, 5)})
    r.naechste_haelfte()
    assert r.beendet and r.verlierer == 2 and not r.glatter_gang


def test_glatter_gang():
    r = Runde(tisch(), [0, 1, 2], start=0)
    for _ in range(2):
        r.haelfte.werte_aus(GENERAL_FUER[0])
        r.naechste_haelfte()
    assert r.beendet and r.verlierer == 0 and r.glatter_gang and len(r.haelften) == 2


# --- Sitzung -------------------------------------------------------------------
def spiele_runde(s: Sitzung, rng: random.Random, pruefe=True) -> None:
    """Spielt die laufende Runde zu Ende. Wer von denen, die dran sind, handelt, ist zufällig;
    Menschen wählen zufällig."""
    while not s.runde.beendet:
        h = s.haelfte
        i = rng.choice(s.offen)
        if s.stechen:
            assert s.am_zug is None and s.optionen(i) == [WUERFELN] and not s.spieler[i].bot
            s.ausfuehren(WUERFELN, i)
            continue
        zug = s.durchgang.zug(i)
        if pruefe and zug.wurf is not None:
            assert {b.option for b in s.empfehlung(i).optionen} == set(zug.optionen())
        if s.spieler[i].bot:
            s.bot_schritt(i)
        else:
            s.ausfuehren(rng.choice(s.optionen(i)), i)
        if pruefe:
            assert h.mitte + sum(h.bricken.values()) == BRICKEN


def neue_sitzung(seed, menschen=("Anna",)):
    spieler = [Spieler(n) for n in menschen] + [
        Spieler("Mathematiker", Mathematiker()), Spieler("Kneipengänger", Kneipengaenger()), Spieler("Anfänger", Anfaenger())]
    return Sitzung(spieler, random.Random(seed))


def test_komplette_runde_mit_festem_seed():
    for seed in range(5):
        s = neue_sitzung(seed)
        spiele_runde(s, random.Random(seed))
        r = s.runde
        assert r.beendet and len(r.haelften) == (2 if r.glatter_gang else 3)
        for h in r.haelften:
            assert h.verlierer is not None
            schluss = h.durchgaenge[-1].ergebnisse
            assert h.bricken[h.verlierer] == BRICKEN or max(map(bewerte, schluss.values())) == bewerte((1, 1, 1))
        # gleicher Seed, gleiches Spiel
        s2 = neue_sitzung(seed)
        spiele_runde(s2, random.Random(seed), pruefe=False)
        assert texte(s2) == texte(s)


def test_komplette_runde_mit_zwei_menschen():
    for seed in range(5):
        s = neue_sitzung(seed, menschen=("Anna", "Ben"))
        assert sorted(s.sitzordnung) == [0, 1, 2, 3, 4] and s.durchgang.schuss
        spiele_runde(s, random.Random(seed))
        assert s.runde.beendet and not s.runde.verlassen


def test_schuss_nur_im_allerersten_durchgang():
    s = neue_sitzung(7)
    with pytest.raises(ValueError):
        s.neue_runde()
    for _ in range(2):
        spiele_runde(s, random.Random(7), pruefe=False)
        verlierer = s.runde.verlierer
        s.neue_runde()
        assert s.durchgang.startspieler == verlierer and not s.durchgang.schuss
    alle = [d for r in s.runden for h in r.haelften for d in h.durchgaenge]
    assert alle[0].schuss and not any(d.schuss for d in alle[1:])


def test_bot_engine_parameter():
    """Startspieler-Bot rechnet mit startspieler=True, die anderen mit der Grenze des Durchgangs;
    alle mit dem Spielstand der Hälfte (Phase, Mitte, eigene und andere Bricken, Teilnehmer)."""
    aufrufe = []

    def engine(grenze, startspieler, phase, mitte, ich, andere, teilnehmer):
        aufrufe.append((grenze, startspieler, phase, mitte, ich, andere, teilnehmer))
        return haelften_engine(grenze, startspieler, phase, mitte, ich, andere, teilnehmer)

    s = Sitzung([Spieler(f"Bot {i}", Mathematiker()) for i in range(3)], random.Random(1), engine=engine)
    while s.durchgang.schuss:
        s.bot_schritt()
    assert aufrufe == []                                       # im Schuss gibt es nichts zu entscheiden
    h, d = s.haelfte, s.durchgang
    stand = (h.phase, h.mitte)
    while s.durchgang is d:
        s.bot_schritt()
    assert aufrufe[0][:2] == (3, True) and aufrufe[0][2:4] == stand and aufrufe[0][-1] == 3
    assert all(a[0] == d.grenze for a in aufrufe if not a[1])
    assert all(len(a[5]) == 2 and a[4] + sum(a[5]) == BRICKEN - stand[1] for a in aufrufe)


def test_bots_ziehen_bis_mensch_oder_ende_des_durchgangs():
    s = neue_sitzung(3)
    for _ in range(200):
        d = s.durchgang
        s.bots_ziehen()
        zug = s.am_zug
        # Halt: ein Mensch entscheidet, sticht, oder der Durchgang ist vorbei
        assert (zug is not None and s.spieler[zug.spieler].bot is None) or s.stechen or s.durchgang is not d \
            or s.runde.beendet
        if s.runde.beendet:
            break
        if s.durchgang is d:
            s.ausfuehren(s.optionen()[0])
    assert s.ausgewertet and all(x.auswertung is not None for x in s.ausgewertet)


def test_sitzordnung_zufaellig():
    ordnungen = {tuple(neue_sitzung(seed).sitzordnung) for seed in range(10)}
    assert len(ordnungen) > 1


def test_neue_spieler_ab_naechster_runde_mit_schuss():
    s = neue_sitzung(4)
    spiele_runde(s, random.Random(4), pruefe=False)
    with pytest.raises(ValueError):
        s.beitreten(Spieler("anna "))             # sitzt schon am Tisch
    dora = s.beitreten(Spieler("Dora"))
    assert dora == 4 and dora not in s.runde.teilnehmer
    s.neue_runde()
    assert sorted(s.sitzordnung) == [0, 1, 2, 3, 4] and s.runde.teilnehmer == s.sitzordnung
    assert s.durchgang.schuss and s.durchgang.startspieler is None
    assert "Neue Sitzordnung: " in texte(s)[-3]


def test_verlassen_mitten_in_der_runde():
    s = neue_sitzung(5, menschen=("Anna", "Ben"))
    s.bots_ziehen()
    s.verlassen(1)
    r = s.runde
    assert r.beendet and r.verlierer == 1 and r.verlassen and s.offen == [] and s.am_zug is None
    assert texte(s)[-2:] == ["Ben hat den Tisch verlassen.", "Ben hat die Runde verloren."]
    with pytest.raises(ValueError):
        s.ausfuehren(WUERFELN, 0)
    s.neue_runde()
    assert 1 not in s.sitzordnung and s.durchgang.schuss
    # Wer zurückkommt, bekommt seinen alten Platz im Verzeichnis
    assert s.beitreten(Spieler("Ben")) == 1
    spiele_runde(s, random.Random(5), pruefe=False)
    s.neue_runde()
    assert 1 in s.sitzordnung and s.durchgang.schuss


def test_verlassen_nach_der_runde_und_zu_wenige_spieler():
    s = Sitzung([Spieler("Anna"), Spieler("Mathe", Mathematiker())], random.Random(6))
    spiele_runde(s, random.Random(6), pruefe=False)
    verlierer = s.runde.verlierer
    s.verlassen(1)
    assert s.runde.verlierer == verlierer and not s.runde.verlassen
    with pytest.raises(ValueError):
        s.neue_runde()                            # allein am Tisch


def test_nur_wer_dran_ist_darf_handeln():
    s = neue_sitzung(8, menschen=("Anna", "Ben"))
    s.bots_ziehen()
    assert sorted(s.offen) == [0, 1]              # Schuss: beide Menschen gleichzeitig
    s.ausfuehren(WUERFELN, 1)
    assert s.offen == [0] and s.optionen(1) == []
    with pytest.raises(ValueError):
        s.ausfuehren(WUERFELN, 1)
    with pytest.raises(ValueError):
        s.bot_schritt(0)                          # Anna ist kein Bot
