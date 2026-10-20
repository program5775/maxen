"""Tests für die Chance, die Hälfte zu verlieren (Zielfunktion für Bots und Tipps im Spiel)."""
import pytest

from maxen.regeln import ABGEBEN, BRICKEN, VERTEILEN, bewerte
import numpy as np

from maxen.verlust import (ALLE_SCHLUESSEL, KLASSEN, gegner_verteilung, haelftenmodell, rollen, sicht_vektor,
                          zug_engines)


@pytest.mark.parametrize("n", [2, 3, 5])
def test_genau_einer_verliert_und_am_anfang_alle_gleich(n):
    m = haelftenmodell(n)
    assert m.verlust(VERTEILEN, BRICKEN, (0,) * n) == pytest.approx((1 / n,) * n)
    for phase, mitte, stand in [(VERTEILEN, 7, (5, 3) + (0,) * (n - 2)), (ABGEBEN, 0, (9, 6) + (0,) * (n - 2))]:
        assert sum(m.verlust(phase, mitte, stand)) == pytest.approx(1)


def test_mehr_bricken_mehr_risiko_urlaub_sicher():
    m = haelftenmodell(4)
    v = m.verlust(ABGEBEN, 0, (12, 2, 1, 0))
    assert v[0] > v[1] > v[2] > 0 and v[3] == 0               # Urlauber kann nicht mehr verlieren
    v = m.verlust(VERTEILEN, 3, (6, 4, 2, 0))
    assert v[0] > v[1] > v[2] > v[3] > 0                       # in Phase 1 spielen alle mit
    assert m.verlust(ABGEBEN, 0, (15, 0)) == (1.0, 0.0)


def test_reihenfolge_egal():
    m = haelftenmodell(3)
    assert m.verlust(ABGEBEN, 0, (2, 7, 6)) == pytest.approx(tuple(reversed(m.verlust(ABGEBEN, 0, (6, 7, 2)))))


FREI = ("frei",)


def gegner(*bricken, sicht=FREI):
    return tuple(sorted((b, sicht) for b in bricken))


@pytest.mark.parametrize("sichten", [[FREI], [FREI] * 4, [("fest", bewerte((3, 3, 1))), FREI],
                                     [("verdeckt", 3, True, (1, 1), 3, True), ("fest", bewerte((6, 5, 4))), FREI]])
def test_rollen_summieren_sich(sichten):
    """Für jedes eigene Ergebnis hat genau ein Spieler das beste und ein anderer das schlechteste Ergebnis."""
    w = rollen([sicht_vektor(s, 3, len(sichten)) for s in sichten])
    assert w.sum(axis=(0, 1, 3)) == pytest.approx(np.ones(len(ALLE_SCHLUESSEL)))
    assert np.all(w[np.arange(len(sichten) + 1), np.arange(len(sichten) + 1)] == 0)


def test_rollen_mit_bekanntem_gegner():
    """Gegen ein offenes 6,5,4 (Straße 6, kostet 2): mit 6,6,6 gebe ich 3 ab, mit 2,2,1 bekomme ich 2."""
    w = rollen([sicht_vektor(("fest", bewerte((6, 5, 4))), 3, 1)])
    r = ALLE_SCHLUESSEL.index
    assert w[0, 1, r(bewerte((6, 6, 6))), KLASSEN.index(3)] == pytest.approx(1)
    assert w[1, 0, r(bewerte((1, 2, 2))), KLASSEN.index(2)] == pytest.approx(1)
    assert w[0, 1, r(bewerte((6, 5, 4))), KLASSEN.index(2)] == pytest.approx(0.5)   # gleich: Stechen


def test_mit_general_verliere_ich_nur_gegen_einen_general():
    w = rollen([sicht_vektor(FREI, 3, 1)])
    general = ALLE_SCHLUESSEL.index(bewerte((1, 1, 1)))
    assert w[1, 0, general, KLASSEN.index(None)] == pytest.approx(gegner_verteilung(3, 1)[bewerte((1, 1, 1))] / 2)


def test_peter_dreht_6_6_6():
    """Durchgang vom Nutzer: Peter, Startspieler in Phase 2 mit 7 gegen 8 Bricken, 6,6,6 nach Wurf 2.
    „Nicht verlieren“ empfiehlt Klopfen, die Hälfte spricht fürs Drehen (Chance auf den General)."""
    emp = zug_engines(3, True, ABGEBEN, 0, 7, gegner(8), 2)[0].empfehlung((6, 6, 6), 2)
    assert emp.beste.option.aktion == "drehen" and emp.beste.option.neu_fest == (1, 1)
    assert "die Hälfte nicht zu verlieren" in emp.begruendung()


@pytest.mark.parametrize("wurf", [(2, 6, 6), (1, 3, 6)])
def test_mit_wenigen_bricken_will_man_abgeben(wurf):
    """Vom Nutzer: In Phase 2 mit 2 Bricken nach Wurf 1 nicht mit 6,6,2 oder 6,3,1 klopfen,
    sondern versuchen zu gewinnen und abzugeben."""
    for andere in [(7, 6), (13,)]:
        emp = zug_engines(3, False, ABGEBEN, 0, 2, gegner(*andere), len(andere) + 1)[0].empfehlung(wurf, 1)
        assert emp.beste.option.aktion != "klopfen"


def test_sichtbares_zaehlt():
    """Finale vom Nutzer: Danny hat 6,6 zu 1 gedreht und die 1 liegen lassen, Wurf 3 verdeckt, also
    mindestens Max. Andy hat 2,2,1 nach Wurf 1: Mit Klopfen ist er sicher Letzter. Ohne dieses Wissen
    rechnete die Engine mit 43 % für die Hälfte."""
    danny = ("verdeckt", 3, True, (1, 1), 3, True)
    blind, _ = zug_engines(3, False, VERTEILEN, BRICKEN, 0, gegner(0), 2)
    haelfte, durchgang = zug_engines(3, False, VERTEILEN, BRICKEN, 0, gegner(0, sicht=danny), 2)
    klopfen = {b.option.aktion: b for b in haelfte.empfehlung((1, 2, 2), 1).optionen}["klopfen"]
    assert {b.option.aktion: b for b in durchgang.empfehlung((1, 2, 2), 1).optionen}["klopfen"].nutzen == pytest.approx(0)
    blind_klopfen = {b.option.aktion: b for b in blind.empfehlung((1, 2, 2), 1).optionen}["klopfen"]
    assert klopfen.nutzen < blind_klopfen.nutzen
    assert haelfte.empfehlung((1, 2, 2), 1).beste.option.neu_fest == (1,)
