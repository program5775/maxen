"""Tests für die Chance, die Hälfte zu verlieren (Zielfunktion für Bots und Tipps im Spiel)."""
import pytest

from maxen.regeln import ABGEBEN, BRICKEN, VERTEILEN, bewerte
from maxen.verlust import ANDERE, ICH, gegner_ereignisse, gegner_verteilung, haelften_engine, haelftenmodell


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


@pytest.mark.parametrize("grenze, k", [(1, 1), (2, 2), (3, 4)])
def test_ereignisse_summieren_sich(grenze, k):
    """Für jedes eigene Ergebnis: Wahrscheinlichkeiten summieren sich zu 1; mit General bin ich nie Geber."""
    for r, ereig in gegner_ereignisse(grenze, k).items():
        assert sum(ereig.values()) == pytest.approx(1)
        assert all(g is None for (a, g, e) in ereig if a is None)
    # Mit General verliere ich die Hälfte nur, wenn der andere auch einen hat und ich das Stechen verliere
    general = gegner_ereignisse(3, 1)[bewerte((1, 1, 1))]
    assert general[None, None, ICH] == pytest.approx(gegner_verteilung(3, 1)[bewerte((1, 1, 1))] / 2)
    assert general[None, None, ICH] + general[None, None, ANDERE] == pytest.approx(1)


def test_peter_dreht_6_6_6():
    """Durchgang vom Nutzer: Peter, Startspieler in Phase 2 mit 7 gegen 8 Bricken, 6,6,6 nach Wurf 2.
    „Nicht verlieren“ empfiehlt Klopfen, die Hälfte spricht fürs Drehen (Chance auf den General)."""
    emp = haelften_engine(3, True, ABGEBEN, 0, 7, (8,), 2).empfehlung((6, 6, 6), 2)
    assert emp.beste.option.aktion == "drehen" and emp.beste.option.neu_fest == (1, 1)
    assert "die Hälfte nicht zu verlieren" in emp.begruendung()


@pytest.mark.parametrize("wurf", [(2, 6, 6), (1, 3, 6)])
def test_mit_wenigen_bricken_will_man_abgeben(wurf):
    """Vom Nutzer: In Phase 2 mit 2 Bricken nach Wurf 1 nicht mit 6,6,2 oder 6,3,1 klopfen,
    sondern versuchen zu gewinnen und abzugeben."""
    for andere in [(7, 6), (13,)]:
        emp = haelften_engine(3, False, ABGEBEN, 0, 2, andere, 3).empfehlung(wurf, 1)
        assert emp.beste.option.aktion != "klopfen"
