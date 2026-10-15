import random

import pytest

from maxen import Engine
from maxen.bots import NAMEN, Anfaenger, Lage, Mathematiker, Stammspieler, bot_namen, faustregel
from maxen.regeln import ALLE_WUERFE


SPIELSTAENDE = ((1, 15, 0), (1, 2, 5), (2, 0, 2), (2, 0, 8))   # (Phase, Mitte, eigene Bricken)


def alle_empfehlungen():
    """Empfehlungen mit Lage für jeden Wurf, jede Wurfgrenze, jede Wurfnummer und mehrere Spielstände."""
    for e in (Engine(1), Engine(2), Engine(3), Engine(3, startspieler=True)):
        for nr in range(1, (4 if e.wuerfe == 3 else e.wuerfe) + 1):
            for wurf in ALLE_WUERFE:
                emp = e.empfehlung(wurf, nr)
                for phase, mitte, bricken in SPIELSTAENDE:
                    yield emp, Lage(tuple(sorted(wurf)), nr, e.startspieler, bricken, phase, mitte)


def regel_beste(emp, lage):
    """Beste Option unter den Faustregeln (oder die beste überhaupt, wenn sie keine erlauben)."""
    return next((b for b in emp.optionen if faustregel(b.option, lage)), emp.beste)


def waehlt(bot, wurf, nr, gegner=3, startspieler=False, bricken=0, mal=200, seed=1, phase=1, mitte=15):
    e = Engine(3, gegner, startspieler=startspieler)
    emp, lage = e.empfehlung(wurf, nr), Lage(wurf, nr, startspieler, bricken, phase, mitte)
    rng = random.Random(seed)
    return [bot.waehle(emp, rng, lage) for _ in range(mal)]


def test_mathematiker_waehlt_immer_beste():
    rng = random.Random(1)
    assert all(Mathematiker().waehle(emp, rng, lage) == emp.beste.option for emp, lage in alle_empfehlungen())


def test_bots_waehlen_nur_erlaubte_optionen():
    rng = random.Random(1)
    for bot in (Mathematiker(), Stammspieler(), Anfaenger()):
        for emp, lage in alle_empfehlungen():
            assert bot.waehle(emp, rng, lage) in [b.option for b in emp.optionen]


@pytest.mark.parametrize("startspieler", [False, True])
@pytest.mark.parametrize("gegner", [1, 3])
def test_stammspieler_legt_6_und_1_heraus(gegner, startspieler):
    """6,3,1 nach Wurf 1: 6 und 1 liegen lassen, nie nur die 1, und als Startspieler nicht schießen."""
    bot = Stammspieler()
    assert {o.neu_fest for o in waehlt(bot, (1, 3, 6), 1, gegner, startspieler)} == {(1, 6)}
    # 1,3,4 nach Wurf 2: die 1 bleibt liegen
    assert all(1 in o.neu_fest for o in waehlt(bot, (1, 3, 4), 2, gegner, startspieler))


@pytest.mark.parametrize("wurf", [(2, 6, 6), (1, 4, 6), (1, 6, 6)])
def test_stammspieler_schiesst_nicht_mit_6_6_oder_6_1(wurf):
    for gegner in range(1, 6):
        for bricken in (0, 2, 8):
            optionen = waehlt(Stammspieler(), wurf, 1, gegner, startspieler=True, bricken=bricken, mal=50)
            assert all(o.aktion != "klopfen" for o in optionen)


@pytest.mark.parametrize("phase, mitte, bricken, wurf, nr, vorhaben", [
    # Phase 1, Anfang der Hälfte: mit Max 5 und Max 6 klopfen, Max 2 nie
    (1, 15, 0, (1, 1, 6), 1, "klopfen"), (1, 7, 4, (1, 1, 5), 2, "klopfen"), (1, 15, 0, (1, 1, 2), 1, "max"),
    # Phase 1, Ende der Hälfte: mit jedem Max auf den General
    (1, 3, 0, (1, 1, 6), 1, "max"), (1, 2, 5, (1, 1, 3), 1, "max"), (1, 1, 0, (1, 1, 5), 2, "max"),
    # Phase 2, viele eigene Bricken: nach Wurf 1 ab Straße klopfen
    (2, 0, 8, (1, 1, 2), 1, "klopfen"), (2, 0, 7, (1, 2, 3), 1, "klopfen"), (2, 0, 9, (3, 3, 3), 1, "klopfen"),
    # Phase 2, wenige eigene Bricken: Max muss für alle reichen; Straße und Pasch nach Wurf 1 klopfen
    (2, 0, 2, (1, 1, 2), 1, "klopfen"), (2, 0, 4, (1, 1, 3), 1, "max"), (2, 0, 4, (1, 1, 4), 2, "klopfen"),
    (2, 0, 6, (1, 1, 5), 2, "max"), (2, 0, 3, (2, 3, 4), 1, "klopfen"), (2, 0, 5, (4, 4, 4), 1, "klopfen"),
])
def test_stammspieler_plan_je_phase(phase, mitte, bricken, wurf, nr, vorhaben):
    for gegner in (1, 3, 5):
        optionen = waehlt(Stammspieler(), wurf, nr, gegner, bricken=bricken, phase=phase, mitte=mitte, mal=20)
        if vorhaben == "klopfen":
            assert {o.aktion for o in optionen} == {"klopfen"}
        else:
            assert {o.neu_fest for o in optionen} == {(1, 1)}


def test_faustregeln_erlauben_immer_eine_option_oder_greifen_nicht():
    """Nach Wurf 3 mit Max am Ende der Hälfte ist kein 1,1 mehr möglich: dann gelten alle Optionen."""
    emp = Engine(3, 2).empfehlung((1, 1, 4), 3)
    lage = Lage((1, 1, 4), 3, phase=1, mitte=2)
    assert not any(faustregel(b.option, lage) for b in emp.optionen)
    assert Stammspieler().waehle(emp, random.Random(1), lage).aktion == "klopfen"


def test_stammspieler_meist_gut():
    """Wählt meistens die beste Option unter den Faustregeln, aber nicht immer; ohne Temperatur immer."""
    rng = random.Random(1)
    faelle = [(emp, lage) for emp, lage in alle_empfehlungen() if len(emp.optionen) > 1]
    treffer = sum(Stammspieler().waehle(emp, rng, lage) == regel_beste(emp, lage).option
                  for emp, lage in faelle) / len(faelle)
    assert 0.5 < treffer < 1
    assert all(Stammspieler(1e-9).waehle(emp, rng, lage) == regel_beste(emp, lage).option for emp, lage in faelle)


def test_stammspieler_keine_groben_fehler():
    """Nie mehr als 3 Prozentpunkte unter der besten Option der Faustregeln; 6,6,1 nach Wurf 2 wird immer gedreht."""
    rng = random.Random(1)
    bot = Stammspieler()
    for emp, lage in alle_empfehlungen():
        nutzen = {b.option: b.nutzen for b in emp.optionen}
        assert regel_beste(emp, lage).nutzen - nutzen[bot.waehle(emp, rng, lage)] <= 0.03 + 1e-12
    for gegner in range(1, 6):
        emp = Engine(3, gegner, startspieler=True).empfehlung((1, 6, 6), 2)
        assert emp.beste.option.aktion == "drehen"
        lage = Lage((1, 6, 6), 2, startspieler=True)
        assert all(bot.waehle(emp, rng, lage) == emp.beste.option for _ in range(200))


def test_anfaenger_dreht_und_macht_groessere_fehler():
    rng = random.Random(1)
    bot = Anfaenger(regeltreue=0)
    gewaehlt = []
    for emp, lage in alle_empfehlungen():
        nutzen = {b.option: b.nutzen for b in emp.optionen}
        o = bot.waehle(emp, rng, lage)
        assert emp.beste.nutzen - nutzen[o] <= 0.15 + 1e-12
        gewaehlt.append(emp.beste.nutzen - nutzen[o])
    assert max(gewaehlt) > 0.03
    assert any(Anfaenger().waehle(emp, rng, lage).aktion == "drehen" for emp, lage in alle_empfehlungen())


def test_anfaenger_haelt_sich_in_einem_drittel_an_die_faustregeln():
    """Startspieler mit 6,6,2 nach Wurf 1 gegen 3: Die Engine will klar klopfen (Schuss),
    die Faustregel verbietet es. Der Anfänger klopft also in etwa 2/3 der Fälle."""
    klopfen = sum(o.aktion == "klopfen" for o in waehlt(Anfaenger(), (2, 6, 6), 1, 3, startspieler=True, mal=900))
    assert 0.58 < klopfen / 900 < 0.75


def test_bot_namen():
    for seed in range(20):
        namen = bot_namen(5, random.Random(seed), gesperrt=" anna ")
        assert len(set(namen)) == 5 and set(namen) <= set(NAMEN) and "Anna" not in namen
    assert len(bot_namen(len(NAMEN) - 1, random.Random(1), gesperrt="Paul")) == len(NAMEN) - 1
    zwei = [NAMEN[0].upper(), NAMEN[1]]
    namen = bot_namen(len(NAMEN) - 2, random.Random(1), gesperrt=zwei)
    assert set(namen) == set(NAMEN) - set(NAMEN[:2])
