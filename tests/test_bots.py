import random

from maxen import Engine
from maxen.bots import NAMEN, Anfaenger, Fortgeschritten, Profi, bot_namen
from maxen.regeln import ALLE_WUERFE


def alle_empfehlungen():
    """Empfehlungen für jeden Wurf, jede Wurfgrenze und jede Wurfnummer."""
    for e in (Engine(1), Engine(2), Engine(3), Engine(3, startspieler=True)):
        for nr in range(1, (4 if e.wuerfe == 3 else e.wuerfe) + 1):
            for wurf in ALLE_WUERFE:
                yield e.empfehlung(wurf, nr)


def test_profi_waehlt_immer_beste():
    rng = random.Random(1)
    assert all(Profi().waehle(emp, rng) == emp.beste.option for emp in alle_empfehlungen())


def test_bots_waehlen_nur_erlaubte_optionen():
    rng = random.Random(1)
    for bot in (Profi(), Fortgeschritten(), Anfaenger()):
        for emp in alle_empfehlungen():
            assert bot.waehle(emp, rng) in [b.option for b in emp.optionen]


def test_anfaenger_dreht_nie():
    rng = random.Random(1)
    assert all(Anfaenger().waehle(emp, rng).aktion != "drehen" for emp in alle_empfehlungen())


def test_fortgeschritten_meist_gut():
    """Wählt meistens die beste Option, aber nicht immer; ohne Temperatur wie der Profi."""
    rng = random.Random(1)
    emps = [emp for emp in alle_empfehlungen() if len(emp.optionen) > 1]
    treffer = sum(Fortgeschritten().waehle(emp, rng) == emp.beste.option for emp in emps) / len(emps)
    assert 0.5 < treffer < 1
    assert all(Fortgeschritten(1e-9).waehle(emp, rng) == emp.beste.option for emp in emps)


def test_fortgeschritten_keine_groben_fehler():
    """Nie mehr als 10 Prozentpunkte unter der besten Option; 6,6,1 nach Wurf 2 wird immer gedreht."""
    rng = random.Random(1)
    bot = Fortgeschritten()
    for emp in alle_empfehlungen():
        nutzen = {b.option: b.nutzen for b in emp.optionen}
        assert emp.beste.nutzen - nutzen[bot.waehle(emp, rng)] <= 0.10
    for gegner in range(1, 6):
        emp = Engine(3, gegner, startspieler=True).empfehlung((1, 6, 6), 2)
        assert emp.beste.option.aktion == "drehen"
        assert all(bot.waehle(emp, rng) == emp.beste.option for _ in range(200))


def test_bot_namen():
    for seed in range(20):
        namen = bot_namen(5, random.Random(seed), gesperrt=" anna ")
        assert len(set(namen)) == 5 and set(namen) <= set(NAMEN) and "Anna" not in namen
    assert len(bot_namen(len(NAMEN) - 1, random.Random(1), gesperrt="Paul")) == len(NAMEN) - 1
    zwei = [NAMEN[0].upper(), NAMEN[1]]
    namen = bot_namen(len(NAMEN) - 2, random.Random(1), gesperrt=zwei)
    assert set(namen) == set(NAMEN) - set(NAMEN[:2])
