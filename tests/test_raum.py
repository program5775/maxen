import random

import pytest

from maxen.bots import NAMEN
from maxen.raum import ABLAUF, PAUSE_DURCHGANG, PAUSE_RUNDE, SPIEL, WARTEN, Raeume, raum_id
from maxen.spiel import WUERFELN


class Uhr:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def raeume(seed=1):
    uhr = Uhr()
    return Raeume(rng_fabrik=lambda: random.Random(seed), uhr=uhr), uhr


def raum_mit(namen, bots=0, seed=1, stufe="Mathematiker"):
    """Raum „Tisch“ mit den Menschen `namen` (der erste ist Ersteller), gestartet."""
    rs, uhr = raeume(seed)
    r, _ = rs.betreten("Tisch", namen[0])
    for n in namen[1:]:
        rs.betreten("Tisch", n)
    r.einstellen(namen[0], bots=bots, stufe=stufe)
    assert r.starten(namen[0], r.marke(namen[0]))
    return rs, r, uhr


def spiele_bis(r, bis, rng=None, schritte=5000):
    """Menschen handeln zufällig (wer von denen, die dran sind, und welche Option) und bestätigen
    jede Pause sofort, bis `bis()` gilt."""
    rng = rng or random.Random(0)
    for _ in range(schritte):
        if bis():
            return
        if r.pause is not None:
            n = next(n for n in r.menschen if r.index(n) in r.pause.warten_auf)
            assert r.bestaetigen(n, r.marke(n))
            continue
        dran = [n for n in r.menschen if r.index(n) in r.sitzung.offen]
        assert dran, "Niemand ist dran, obwohl keine Pause ist"
        n = rng.choice(dran)
        assert r.ausfuehren(n, r.marke(n), rng.choice(r.optionen(n)))
    raise AssertionError("Bedingung nicht erreicht")


# --- Warteraum -------------------------------------------------------------------
def test_raum_id():
    assert raum_id(" Stamm Tisch ") == raum_id("stammtisch") == "stammtisch"


def test_betreten_und_wiedereinstieg():
    rs, _ = raeume()
    r, n = rs.betreten("Stamm Tisch", "Anna")
    assert (r.id, n, r.ersteller, r.status) == ("stammtisch", "Anna", "Anna", WARTEN)
    r2, n2 = rs.betreten("stammtisch", " anna ")
    assert r2 is r and n2 == "Anna" and r.menschen == ["Anna"]
    rs.betreten("STAMMTISCH", "Ben")
    assert r.menschen == ["Anna", "Ben"] and r.ersteller == "Anna"
    with pytest.raises(ValueError):
        rs.betreten("stammtisch", "  ")
    with pytest.raises(ValueError):
        rs.betreten(" ", "Cleo")


def test_nur_der_ersteller_stellt_ein_und_startet():
    rs, _ = raeume()
    r, _ = rs.betreten("Tisch", "Anna")
    rs.betreten("Tisch", "Ben")
    assert not r.einstellen("Ben", bots=3)
    assert r.einstellen("anna", bots=2, stufe="Mathematiker", tipps=True)
    assert (r.bots, r.stufe, r.tipps) == (2, "Mathematiker", True)
    assert not r.starten("Ben", r.marke("Ben"))
    veraltet = r.marke("Anna")
    r.einstellen("Anna", tipps=False)
    assert r.starten("Anna", veraltet)        # Einstellungen ändern die Marke nicht
    s = r.sitzung
    assert r.status == SPIEL and len(s.spieler) == 4
    assert [sp.name for sp in s.spieler[:2]] == ["Anna", "Ben"] and r.index("ben") == 1
    assert {sp.name for sp in s.spieler[2:]} <= set(NAMEN) - {"Anna", "Ben"}
    assert not r.einstellen("Anna", bots=1)   # Bots nur im Warteraum
    assert r.einstellen("Anna", tipps=True)   # Tipps jederzeit
    assert not r.starten("Anna", r.marke("Anna"))   # läuft schon


def test_allein_ohne_bots_nicht_startbar():
    rs, _ = raeume()
    r, _ = rs.betreten("Tisch", "Anna")
    with pytest.raises(ValueError):
        r.starten("Anna", r.marke("Anna"))
    with pytest.raises(ValueError):
        r.einstellen("Anna", bots=6)


def test_entfernen_im_warteraum():
    rs, _ = raeume()
    r, _ = rs.betreten("Tisch", "Anna")
    rs.betreten("Tisch", "Ben")
    assert not r.entfernen("Ben", r.marke("Ben"), "Anna")
    assert not r.entfernen("Anna", r.marke("Anna"), "Anna")
    assert r.entfernen("Anna", r.marke("Anna"), "ben")
    assert r.menschen == ["Anna"]


def test_ersteller_geht_und_letzter_raum_verschwindet():
    rs, _ = raeume()
    r, _ = rs.betreten("Tisch", "Anna")
    rs.betreten("Tisch", "Ben")
    rs.verlassen("Tisch", "Anna")
    assert r.ersteller == "Ben" and rs.raum("tisch") is r
    rs.verlassen("Tisch", "Ben")
    assert rs.raum("tisch") is None
    r2, n = rs.betreten("Tisch", "Cleo")      # gleiche ID, neuer Raum
    assert r2 is not r and r2.ersteller == "Cleo"


def test_raeume_verfallen():
    rs, uhr = raeume()
    alt, _ = rs.betreten("Alt", "Anna")
    uhr.t += ABLAUF - 1
    rs.betreten("Neu", "Ben")
    assert rs.raum("alt") is alt
    uhr.t += 2
    rs.betreten("Neu", "Ben")
    assert rs.raum("alt") is None and rs.raum("neu") is not None



def test_liste_der_aktiven_raeume():
    """Zuletzt geänderte zuerst; verfallene und leere Räume fehlen."""
    rs, uhr = raeume()
    alt, _ = rs.betreten("Alt", "Anna")
    uhr.t += 10
    neu, _ = rs.betreten("Neu", "Ben")
    assert rs.liste() == [neu, alt]
    uhr.t += 10
    alt.einstellen("Anna", bots=1)                 # Änderung: wieder oben
    assert rs.liste() == [alt, neu]
    rs.verlassen("Neu", "Ben")
    uhr.t += ABLAUF + 1
    assert rs.liste() == []


# --- Spiel ---------------------------------------------------------------------
def test_doppeltipp_wirkt_nur_einmal():
    _, r, _ = raum_mit(["Anna"], bots=1)
    m = r.marke("Anna")
    assert r.ausfuehren("Anna", m, WUERFELN)  # Schuss
    assert not r.ausfuehren("Anna", m, WUERFELN)
    assert not r.ausfuehren("Cleo", r.marke("Cleo"), WUERFELN)   # nicht im Raum


def test_schuss_gleichzeitig():
    """Beide Knöpfe wurden gezeichnet, bevor jemand gewürfelt hat. Beide Klicks wirken."""
    _, r, _ = raum_mit(["Anna", "Ben"])
    assert r.sitzung.durchgang.schuss and sorted(r.sitzung.offen) == [0, 1]
    ma, mb = r.marke("Anna"), r.marke("Ben")
    v = r.version
    assert r.ausfuehren("Ben", mb, WUERFELN)
    assert r.ausfuehren("Anna", ma, WUERFELN)
    assert r.version > v


def test_pause_nach_durchgang_mit_zeitlimit():
    _, r, uhr = raum_mit(["Anna", "Ben"], bots=1)
    spiele_bis(r, lambda: r.pause is not None)
    p = r.pause
    assert not p.runde and p.zeitlimit == PAUSE_DURCHGANG and p.warten_auf == {0, 1}
    assert r.optionen("Anna") == [] and not r.ausfuehren("Anna", r.marke("Anna"), WUERFELN)
    assert r.bestaetigen("Anna", r.marke("Anna"))
    assert not r.bestaetigen("Anna", r.marke("Anna"))   # schon bestätigt
    uhr.t += PAUSE_DURCHGANG - 1
    v = r.tick()
    assert r.pause is p and r.restzeit() == pytest.approx(1)
    assert r.tick() == v                      # ohne Änderung bleibt die Version
    uhr.t += 1
    assert r.tick() > v and r.pause is None
    assert r.sitzung.offen                    # der nächste Durchgang läuft, Bots sind gezogen
    assert all(not r.sitzung.spieler[i].bot for i in r.sitzung.offen)


def test_pause_endet_wenn_alle_bestaetigt_haben():
    _, r, _ = raum_mit(["Anna", "Ben"])
    spiele_bis(r, lambda: r.pause is not None)
    r.bestaetigen("Ben", r.marke("Ben"))
    assert r.pause is not None
    r.bestaetigen("Anna", r.marke("Anna"))
    assert r.pause is None


def test_urlaub_muss_nicht_bestaetigen():
    _, r, _ = raum_mit(["Anna", "Ben", "Cleo"], bots=1)
    menschen = {r.index(n) for n in r.menschen}

    def urlauber_pause():
        return (r.pause is not None and not r.pause.runde
                and not menschen <= set(r.sitzung.ausgewertet[-1].reihenfolge))
    spiele_bis(r, urlauber_pause, schritte=20000)
    spielten = set(r.sitzung.ausgewertet[-1].reihenfolge)
    assert r.pause.warten_auf == menschen & spielten and r.pause.warten_auf


def test_vorspulen_wenn_nur_noch_bots_spielen():
    """Hat Anna Urlaub oder ist nicht im Finale, spulen die Bots bis zum Ende der Hälfte bzw. Runde vor."""
    _, r, _ = raum_mit(["Anna"], bots=3)
    s = r.sitzung
    assert not r.vorspulen("Anna", r.marke("Anna"))            # keine Pause, Anna spielt mit
    spiele_bis(r, lambda: r.pause is not None and not r.pause.runde and r.nur_bots, schritte=50000)
    haelfte, durchgaenge = s.haelfte, len(s.ausgewertet)
    assert r.vorspulen("Anna", r.marke("Anna"))
    assert len(s.ausgewertet) > durchgaenge and r.pause is not None
    assert s.runde.beendet or s.haelfte is not haelfte            # Hälfte oder Runde vorbei
    assert r.pause.runde == s.runde.beendet and r.pause.warten_auf == {r.index("Anna")}
    assert r.ausgewertet is s.ausgewertet[-1]                      # die Pause zeigt den letzten Durchgang
    assert not r.nur_bots or s.runde.beendet
    assert not r.vorspulen("Anna", r.marke("Anna"))            # nichts mehr vorzuspulen


def test_allein_ohne_zeitlimit():
    _, r, uhr = raum_mit(["Anna"], bots=2)
    spiele_bis(r, lambda: r.pause is not None)
    assert r.pause.zeitlimit is None and r.restzeit() is None
    uhr.t += 10 * PAUSE_RUNDE
    r.tick()
    assert r.pause is not None
    assert r.bestaetigen("Anna", r.marke("Anna")) and r.pause is None


def test_komplette_runde_und_naechste():
    _, r, uhr = raum_mit(["Anna", "Ben"], bots=1)
    s = r.sitzung
    spiele_bis(r, lambda: s.runde.beendet)
    assert r.pause.runde and r.pause.zeitlimit == PAUSE_RUNDE
    verlierer = s.runde.verlierer
    uhr.t += PAUSE_RUNDE
    r.tick()
    assert len(s.runden) == 2 and not s.durchgang.schuss    # gleiche Spieler: kein Schuss
    assert s.runden[1].haelften[0].durchgaenge[0].startspieler == verlierer


def test_zuschauer_steigen_am_ende_der_runde_ein():
    rs, r, uhr = raum_mit(["Anna", "Ben"], bots=1)
    s = r.sitzung
    assert rs.betreten("Tisch", "Cleo") == (r, "Cleo")
    assert r.zuschauer == ["Cleo"] and r.index("Cleo") is None
    assert not r.ausfuehren("Cleo", r.marke("Cleo"), WUERFELN) and r.optionen("Cleo") == []
    spiele_bis(r, lambda: s.runde.beendet)
    assert r.pause.warten_auf == {0, 1} and r.index("Cleo") is None   # Zuschauer bestätigen nicht
    uhr.t += PAUSE_RUNDE
    r.tick()
    assert r.zuschauer == [] and r.index("Cleo") == 3
    assert sorted(s.sitzordnung) == [0, 1, 2, 3] and s.durchgang.schuss


def test_bot_name_ist_im_spiel_gesperrt():
    rs, r, _ = raum_mit(["Anna"], bots=2)
    bot = r.sitzung.spieler[1].name
    with pytest.raises(ValueError):
        rs.betreten("Tisch", bot.upper())


def test_verlassen_mitten_in_der_runde():
    rs, r, _ = raum_mit(["Anna", "Ben", "Cleo"])
    s = r.sitzung
    rs.verlassen("Tisch", "Anna")
    assert r.ersteller == "Ben"
    assert s.runde.beendet and s.runde.verlassen and s.runde.verlierer == 0
    assert r.pause.runde and r.pause.warten_auf == {1, 2}
    r.bestaetigen("Ben", r.marke("Ben"))
    r.bestaetigen("Cleo", r.marke("Cleo"))
    assert len(s.runden) == 2 and sorted(s.sitzordnung) == [1, 2] and s.durchgang.schuss


def test_verlassen_waehrend_der_auswertung():
    """Wer während der Pause nach einem Durchgang geht, beendet die Runde: Die Pause wird zur Rundenpause."""
    rs, r, _ = raum_mit(["Anna", "Ben", "Cleo"])
    spiele_bis(r, lambda: r.pause is not None and not r.pause.runde)
    rs.verlassen("Tisch", "Cleo")
    assert r.sitzung.runde.verlassen and r.pause.runde and r.pause.warten_auf == {0, 1}


def test_verlassen_in_der_rundenpause():
    rs, r, _ = raum_mit(["Anna", "Ben", "Cleo"])
    s = r.sitzung
    spiele_bis(r, lambda: s.runde.beendet)
    r.bestaetigen("Anna", r.marke("Anna"))
    r.bestaetigen("Ben", r.marke("Ben"))
    rs.verlassen("Tisch", "Cleo")             # Cleo war die Letzte, auf die gewartet wurde
    assert r.pause is None and len(s.runden) == 2 and sorted(s.sitzordnung) == [0, 1]


def test_zu_wenige_spieler_zurueck_in_den_warteraum():
    rs, r, _ = raum_mit(["Anna", "Ben"])
    rs.verlassen("Tisch", "Ben")              # Runde verloren, Anna allein
    assert r.pause.runde and r.pause.zeitlimit is None
    r.bestaetigen("Anna", r.marke("Anna"))
    assert r.status == WARTEN and r.menschen == ["Anna"]


def test_ersteller_entfernt_im_spiel():
    _, r, _ = raum_mit(["Anna", "Ben", "Cleo"])
    assert r.entfernen("Anna", r.marke("Anna"), "Cleo")
    assert r.menschen == ["Anna", "Ben"] and r.sitzung.runde.verlierer == 2


def test_beenden_zurueck_in_den_warteraum():
    rs, r, _ = raum_mit(["Anna", "Ben"], bots=1)
    rs.betreten("Tisch", "Cleo")
    m = r.marke("Ben")
    assert not r.beenden("Ben", m)
    assert r.beenden("Anna", r.marke("Anna"))
    assert r.status == WARTEN and r.menschen == ["Anna", "Ben", "Cleo"] and r.zuschauer == []
    assert not r.ausfuehren("Ben", m, WUERFELN)
    assert r.starten("Anna", r.marke("Anna")) and len(r.sitzung.spieler) == 4


def test_mehrere_runden_mit_wechselnden_spielern():
    """Längerer Ablauf: Runden, Zuschauer, Verlassen, Rückkehr. Die Bricken stimmen immer."""
    rs, r, uhr = raum_mit(["Anna", "Ben"], bots=2, stufe="Kneipengänger", seed=3)
    rng = random.Random(3)
    for runde in range(4):
        s = r.sitzung
        if runde == 1:
            rs.betreten("Tisch", "Cleo")
        if runde == 2:
            rs.verlassen("Tisch", "Ben")
        if runde == 3:
            rs.betreten("Tisch", "ben")
        spiele_bis(r, lambda: s.runde.beendet and r.pause is not None, rng)
        h = s.haelfte
        assert h.mitte + sum(h.bricken.values()) == 15
        uhr.t += PAUSE_RUNDE
        r.tick()
    assert r.index("Ben") == 1 and len(r.sitzung.runden) == 5


def test_gleichzeitige_klicks_aus_mehreren_threads():
    """Wie mehrere Handys: Jeder Mensch klickt doppelt, alle gleichzeitig. Jeder würfelt genau einmal."""
    import threading
    namen = ["Anna", "Ben", "Cleo", "Dora"]
    _, r, _ = raum_mit(namen)
    marken = {n: r.marke(n) for n in namen}
    start = threading.Barrier(2 * len(namen))
    erfolge = []

    def klick(n):
        start.wait()
        erfolge.append(r.ausfuehren(n, marken[n], WUERFELN))
        r.tick()

    threads = [threading.Thread(target=klick, args=(n,)) for n in namen * 2]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(erfolge) == [False] * 4 + [True] * 4
    assert r.pause is not None or r.sitzung.stechen is not None   # je nach Reihenfolge der Würfe
    schuss = r.sitzung.runde.haelften[0].durchgaenge[0]
    assert schuss.fertig and all(len(schuss.zug(i).schritte) == 1 for i in range(4))
