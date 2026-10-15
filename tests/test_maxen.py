from itertools import product

import pytest

from maxen import Engine, bewerte, einzelwurf_verteilung, name, optionen, rang, wuerfel_aktionen
from maxen.regeln import ALLE_WUERFE


def test_rangfolge_laut_tabelle():
    erwartet = [
        ((1, 1, 1), 1, "General"),
        ((1, 1, 6), 2, "Max 6"),
        ((1, 1, 2), 6, "Max 2"),
        ((6, 6, 6), 7, "6er Pasch"),
        ((2, 2, 2), 11, "2er Pasch"),  # Konzept-Tabelle zählt hier eins zu viel
        ((6, 5, 4), 12, "Straße 6"),
        ((3, 2, 1), 15, "Straße 3"),
    ]
    for wurf, r, n in erwartet:
        assert rang(wurf) == r
        assert name(bewerte(wurf)) == n
    assert rang((6, 6, 5)) == 16  # bester regulärer Wurf


def test_regulaere_wuerfe():
    assert bewerte((5, 6, 5)) > bewerte((6, 4, 4))   # 655 > 644
    assert name(bewerte((2, 6, 4))) == "642"
    assert bewerte((6, 6, 5)) < bewerte((3, 2, 1))   # Straße schlägt jeden normalen Wurf


def test_reihenfolge_egal():
    assert bewerte((6, 1, 1)) == bewerte((1, 6, 1))


def test_einzelwurf_summe():
    assert sum(einzelwurf_verteilung().values()) == pytest.approx(1)
    assert einzelwurf_verteilung()[bewerte((1, 1, 1))] == pytest.approx(1 / 216)
    assert len(ALLE_WUERFE) == 56


def test_dreh_optionen():
    nf = {o.neu_fest for o in optionen((6, 6, 3), True, True)}
    assert (1, 3) in nf and (1,) in nf                  # 3 liegen lassen oder mitwürfeln
    assert (1, 1) in {o.neu_fest for o in optionen((6, 6, 6), True, True)}
    assert all(o.aktion != "drehen" for o in optionen((6, 6, 6), True, False))


def test_dreh_zeitpunkte():
    def dreht(wuerfe, nr):
        return any(b.option.aktion == "drehen"
                   for b in Engine(wuerfe=wuerfe).empfehlung((6, 6, 2), wurf_nr=nr).optionen)
    assert dreht(3, 1) and dreht(3, 2) and dreht(3, 3)  # nach Wurf 3 -> Bonuswurf
    assert not dreht(3, 4)                               # nach dem Bonuswurf ist Schluss
    assert dreht(2, 1) and not dreht(2, 2)
    assert not dreht(1, 1)


def test_nur_einmal_drehen_pro_zug():
    """Wer schon gedreht hat, darf auch bei erneuten 6,6 nicht noch einmal drehen."""
    e = Engine(wuerfe=3)
    for nr in (2, 3):
        assert not any(b.option.aktion == "drehen"
                       for b in e.empfehlung((1, 6, 6), wurf_nr=nr, gedreht=True).optionen)
    assert any(b.option.aktion == "drehen" for b in e.empfehlung((1, 6, 6), wurf_nr=2).optionen)
    # Die DP berücksichtigt das: Nach dem Drehen ist das Weiterspiel weniger wert als ohne Drehen
    assert e.zustand((1,), 2, gedreht=True)[0] < e.zustand((1,), 2)[0]


def test_bonuswurf_nach_drittem_wurf():
    """6,6,6 nach Wurf 3: zu 1,1 drehen ergibt sicher ein Max."""
    b = Engine(wuerfe=3).empfehlung((6, 6, 6), wurf_nr=3).beste
    assert b.option.neu_fest == (1, 1)
    assert b.mindestens(3) == pytest.approx(1)


def test_wieder_aufnehmen():
    """Nach Wurf 2 darf alles neu gewürfelt werden, auch früher Herausgelegtes."""
    nf = {b.option.neu_fest for b in Engine(wuerfe=3).empfehlung((1, 4, 6), wurf_nr=2).optionen}
    assert () in nf and (4,) in nf


def test_strassen_beispiel():
    """2,3,5 auf Straße: 2,3 behalten (1 oder 4 trifft) ist besser als 3,5 (nur 4)."""
    e = Engine(wuerfe=2)
    bew = {b.option.neu_fest: b for b in e.empfehlung((2, 3, 5), wurf_nr=1).optionen}
    assert bew[(2, 3)].mindestens(1) == pytest.approx(2 / 6)
    assert bew[(3, 5)].mindestens(1) == pytest.approx(1 / 6)
    assert bew[(2, 3)].nutzen > bew[(3, 5)].nutzen


def test_wahrscheinlichkeiten_summieren_sich():
    e = Engine(wuerfe=3)
    for b in e.empfehlung((6, 6, 2)).optionen:
        assert sum(b.verteilung.values()) == pytest.approx(1)
    assert sum(e.startwert().verteilung.values()) == pytest.approx(1)


def test_mehr_wuerfe_sind_besser():
    p = [Engine(wuerfe=n).startwert().mindestens(3) for n in (1, 2, 3)]
    assert p[0] < p[1] < p[2]


def test_wuerfel_aktionen():
    """Pro Würfel: liegen lassen, neu würfeln oder auf 1 drehen – passend zu neu_fest."""
    def aktionen(wurf, neu_fest):
        o = next(o for o in optionen(wurf, True, True) if o.neu_fest == neu_fest)
        return wuerfel_aktionen(wurf, o)
    assert aktionen((6, 4, 2), (6,)) == ["liegen", "neu", "neu"]
    assert aktionen((6, 6, 3), (1, 3)) == ["drehen", "neu", "liegen"]
    assert aktionen((6, 6, 6), (1, 1)) == ["drehen", "drehen", "neu"]
    assert aktionen((6, 6, 6), (1, 6)) == ["drehen", "neu", "liegen"]
    assert aktionen((1, 6, 6), (1, 1)) == ["liegen", "drehen", "neu"]
    # Für alle Würfe: liegen gelassene + gedrehte Würfel ergeben genau neu_fest
    for wurf in product(range(1, 7), repeat=3):
        for o in optionen(wurf, True, True):
            a = wuerfel_aktionen(wurf, o)
            fest = [w for w, x in zip(wurf, a) if x == "liegen"] + [1] * a.count("drehen")
            assert sorted(fest) == list(o.neu_fest)
            assert a.count("neu") == o.neu_wuerfeln


def test_startspieler_legt_grenze_fest():
    """Klopft der Startspieler nach Wurf k, zählt die Gegnerverteilung bei Grenze k
    (nach dem Bonuswurf gilt Grenze 3)."""
    s = Engine(3, gegner=2, startspieler=True)
    for nr, k in ((1, 1), (2, 2), (3, 3), (4, 3)):
        klopfen = next(b for b in s.empfehlung((4, 4, 6), nr).optionen if b.option.aktion == "klopfen")
        assert klopfen.nutzen == pytest.approx(Engine(k, gegner=2).nutzen[bewerte((4, 4, 6))])


def test_startspieler_beispiel_644():
    """Beispiel des Nutzers: Max klopft als Startspieler nach Wurf 2 mit 6,4,4,
    ein normaler Spieler würde weiterwürfeln."""
    assert Engine(3, gegner=2, startspieler=True).empfehlung((6, 4, 4), 2).beste.option.aktion == "klopfen"
    assert Engine(3, gegner=2).empfehlung((6, 4, 4), 2).beste.option.aktion != "klopfen"


def test_startspieler_im_vorteil():
    for g in (1, 2, 3):
        assert Engine(3, g, startspieler=True).startwert().nutzen > Engine(3, g).startwert().nutzen
    with pytest.raises(ValueError):
        Engine(2, startspieler=True)
