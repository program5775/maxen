"""UI-Tests mit AppTest (ohne Browser)."""
from streamlit.testing.v1 import AppTest

import pytest

from maxen import Engine
from maxen.bots import NAMEN
from maxen.raum import PAUSE_DURCHGANG
from maxen.spiel import AM_WUERFELN, FERTIG, VERDECKT, Schritt, Zug
from maxen.engine import optionen
from ui import AUGEN, NEU_MD, augen, empfehlung_html, ergebnis_html, option_md, raeume, schritte_html

AUGEN_WERT = {v: k for k, v in AUGEN.items()}

APP = "../app.py"


def starte() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=10).run()
    assert not at.exception
    return at


def assistent() -> AppTest:
    """Neue Sitzung auf der Seite Assistent (Startseite ist Spielen)."""
    at = starte()
    at.switch_page("app_pages/assistent.py").run()
    assert not at.exception
    return at


def wuerfle(at: AppTest, *augen) -> None:
    ss = at.session_state
    for i, w in enumerate(augen):
        at.segmented_control(key=f"w_{ss.durchgang}_{ss.wurf_nr}_{i}").set_value(w)
    at.run()
    assert not at.exception


def wurf_auswahl(at: AppTest):
    ss = at.session_state
    return at.segmented_control(key=f"sprung_{ss.durchgang}_{ss.wurf_nr}")


def test_assistent_empfehlung_und_ablauf():
    at = assistent()
    assert wurf_auswahl(at).value == 1 and wurf_auswahl(at).label == "Wurf (von 3)"
    wuerfle(at, 2, 3, 5)
    emp = Engine(3, 1).empfehlung((2, 3, 5), 1)
    assert at.success[0].value == emp.begruendung()
    knoepfe = [b for b in at.button if b.key.startswith("opt_")]
    assert len(knoepfe) == len(emp.optionen) and knoepfe[0].label == f"{NEU_MD * 3} · {emp.beste.nutzen * 100:.0f} %"
    assert 'class="maxen optionen"' in "".join(m.value for m in at.markdown)

    # beste Option wählen -> Wurf 2, nichts liegt
    at.button(key=f"opt_{emp.beste.option.aktion}_{emp.beste.option.neu_fest}").click().run()
    assert wurf_auswahl(at).value == 2

    # 6,6,6 -> zu 1,1 drehen, dann mit Max 6 klopfen
    wuerfle(at, 6, 6, 6)
    at.button(key="opt_drehen_(1, 1)").click().run()
    assert at.session_state.fest == (1, 1)
    wuerfle(at, 6)
    at.button(key="opt_klopfen_(1, 1, 6)").click().run()
    assert at.subheader[0].value == "Durchgang beendet"
    assert at.metric[0].value == "Max 6"

    # Zurück und neuer Durchgang
    at.button[1].click().run()
    assert at.session_state.ende is None and at.session_state.wurf_nr == 3
    at.button(key="opt_klopfen_(1, 1, 6)").click().run()
    at.button[0].click().run()
    assert wurf_auswahl(at).value == 1 and at.session_state.verlauf == []


def test_assistent_direkt_zu_wurf_springen():
    at = assistent()
    assert wurf_auswahl(at).options == ["1", "2", "3", "4 Bonus"]
    wurf_auswahl(at).set_value(3).run()
    assert at.session_state.wurf_nr == 3 and wurf_auswahl(at).value == 3
    wuerfle(at, 6, 6, 1)
    e = Engine(3, 1)
    assert at.success[0].value == e.empfehlung((1, 6, 6), 3).begruendung()
    assert at.button(key="opt_drehen_(1, 1)")                       # nach Wurf 3 drehen -> Bonuswurf
    # schon gedreht: kein zweites Mal
    at.toggle(key=f"vorher_gedreht_{at.session_state.durchgang}_3").set_value(True).run()
    assert at.success[0].value == e.empfehlung((1, 6, 6), 3, gedreht=True).begruendung()
    assert not any(b.key.startswith("opt_drehen") for b in at.button)
    # weiter zum Bonuswurf: dort bleibt nur Klopfen
    wurf_auswahl(at).set_value(4).run()
    wuerfle(at, 1, 1, 4)
    assert [b.key for b in at.button if b.key.startswith("opt_")] == ["opt_klopfen_(1, 1, 4)"]
    at.button(key="opt_klopfen_(1, 1, 4)").click().run()
    assert at.metric[0].value == "Max 4"


def test_assistent_schuss_ohne_wurfauswahl():
    at = assistent()
    at.segmented_control(key="cfg_wuerfe").set_value(1).run()
    assert at.subheader[0].value == "Schuss" and not [s for s in at.segmented_control if s.key.startswith("sprung")]
    at.segmented_control(key="cfg_wuerfe").set_value(2).run()
    assert wurf_auswahl(at).options == ["1", "2"]


def test_optionen_als_piktogramme():
    o = {x.neu_fest: x for x in optionen((3, 6, 6), True, True)}
    assert option_md(o[(6, 6)], (3, 6, 6)) == ":green[⚅⚅] " + NEU_MD
    assert option_md(o[()], (3, 6, 6)) == NEU_MD * 3
    assert option_md(o[(1, 3)], (3, 6, 6)) == ":blue[⚅⚅→⚀] :green[⚂] " + NEU_MD
    assert option_md(o[(3, 6, 6)], (3, 6, 6)) == "Klopfen"
    assert option_md(next(x for x in optionen((6, 6, 6), True, True) if x.neu_fest == (1, 1)),
                     (6, 6, 6)) == ":blue[⚅⚅⚅→⚀⚀] " + NEU_MD
    # 6,6,1: einmal drehen und die 1 liegen lassen ergibt auch 1,1, aber nur eine 6 wird gedreht
    assert option_md(next(x for x in optionen((1, 6, 6), True, True) if x.neu_fest == (1, 1) and x.aktion == "drehen"),
                     (1, 6, 6)) == ":blue[⚅⚅→⚀] :green[⚀] " + NEU_MD
    html = empfehlung_html((6, 3, 6), o[(1, 3)])
    assert html.count('class="ew drehen"') == 1 and html.count('class="ew neu"') == 1 and 'class="ew liegen"' in html


def test_assistent_startspieler():
    at = assistent()
    at.toggle(key="cfg_start").set_value(True).run()
    assert wurf_auswahl(at).label == "Wurf (Startspieler, bis zu 3)"
    wuerfle(at, 4, 4, 6)
    assert at.success[0].value == Engine(3, 1, startspieler=True).empfehlung((4, 4, 6), 1).begruendung()
    assert any("höchstens 1-mal" in c.value for c in at.caption)


def test_seitenwechsel_behaelt_eingaben():
    at = assistent()
    at.number_input(key="cfg_gegner").set_value(3).run()
    wuerfle(at, 6, 6, 2)
    at.switch_page("app_pages/spiel.py").run()
    assert not at.exception and at.button(key="spiel_betreten") and not at.title
    at.switch_page("app_pages/assistent.py").run()
    assert not at.exception
    assert at.number_input(key="cfg_gegner").value == 3
    assert at.success[0].value == Engine(3, 3).empfehlung((2, 6, 6), 1).begruendung()


def betrete(raum: str, name: str, seed=None) -> AppTest:
    """Neue Sitzung (ein Handy), die mit `name` den Raum `raum` betritt."""
    at = starte()
    at.switch_page("app_pages/spiel.py").run()
    if seed is not None:
        at.session_state["spiel_seed"] = seed
    at.text_input(key="cfg_spiel_name").set_value(name)
    at.text_input(key="cfg_spiel_raum").set_value(raum)
    at.button(key="spiel_betreten").click().run()
    assert not at.exception
    return at


def raum_von(at: AppTest):
    return raeume().raum(at.session_state.spiel_raum)


def tabelle(at: AppTest) -> str:
    """HTML der Tabelle des Durchgangs."""
    return next(m.value for m in at.markdown if 'class="maxen"' in m.value)


def schritt(at: AppTest) -> bool:
    """Neu zeichnen (wie das Polling) und, falls möglich, einen Knopf drücken:
    Würfeln (mit den vorbelegten Würfeln), Ergebnis bestätigen, Drehen oder Klopfen."""
    at.run()
    assert not at.exception
    keys = [b.key for b in at.button if not b.disabled]
    if "spiel_wuerfeln" in keys:
        at.button(key="spiel_wuerfeln").click()
    elif "spiel_bestaetigen" in keys:
        at.button(key="spiel_bestaetigen").click()
    elif any(k and k.startswith("opt_") for k in keys):
        next(b for b in at.button if b.key and b.key.startswith("opt_")).click()
    elif "spiel_klopfen" in keys:
        at.button(key="spiel_klopfen").click()
    else:
        return False
    at.run()
    assert not at.exception
    return True


def spiele(ats, bis, schritte=3000) -> None:
    """Alle Handys klicken reihum, bis `bis(sitzung)` gilt."""
    ats = ats if isinstance(ats, list) else [ats]
    r = raum_von(ats[0])
    for _ in range(schritte):
        geklickt = False
        for at in ats:
            if bis(r.sitzung):
                return
            geklickt = schritt(at) or geklickt
        if not geklickt:
            raise AssertionError("Niemand kann klicken")
    raise AssertionError("Spiel ist nicht fertig geworden")


def starte_spiel(at: AppTest, bots: int, stufe="Mathematiker") -> None:
    at.segmented_control(key="cfg_raum_bots").set_value(bots).run()
    at.segmented_control(key="cfg_raum_stufe").set_value(stufe).run()
    at.button(key="spiel_starten").click().run()
    assert not at.exception


def test_spiel_komplette_haelfte_gegen_bots():
    at = betrete("bots-haelfte", "Anna", seed=3)
    r = raum_von(at)
    assert at.session_state.spiel_name == "Anna" and r.ersteller == "Anna"
    assert at.query_params["raum"] == "bots-haelfte" and at.query_params["name"] == "Anna"
    starte_spiel(at, 3)
    s = r.sitzung
    assert s.spieler[0].name == "Anna" and s.spieler[0].bot is None
    bots = [sp.name for sp in s.spieler[1:]]
    assert len(set(bots)) == 3 and set(bots) <= set(NAMEN) - {"Anna"}
    at.toggle(key="cfg_raum_tipps").set_value(True).run()   # Tipps einmal mit durchlaufen
    assert r.tipps
    spiele(at, lambda s: s.runde.haelften[0].verlierer is not None and r.pause is not None)
    # Ergebnis der verlorenen Hälfte steht da, bis es bestätigt wird; allein ohne Zeitlimit
    assert tabelle(at).count("<tr") == 1 + 4 and at.caption[0].value.endswith("Ergebnis")
    assert any(b.label.startswith("Weiter: ") or b.label == "Nächste Runde" for b in at.button)
    assert r.restzeit() is None
    at.toggle(key="cfg_raum_tipps").set_value(False).run()
    spiele(at, lambda s: s.runde.beendet)
    assert "Nächste Runde" in [b.label for b in at.button]
    at.button(key="spiel_bestaetigen").click().run()
    assert not at.exception and len(r.sitzung.runden) == 2
    at.button(key="spiel_beenden").click().run()
    assert r.status == "warten" and at.button(key="spiel_starten")
    at.button(key="spiel_verlassen").click().run()
    assert at.button(key="spiel_betreten") and raeume().raum("bots-haelfte") is None
    assert "raum" not in at.query_params


def test_tipps_im_spiel_fuer_die_haelfte():
    """Tipps im Spiel rechnen mit der Chance, die Hälfte nicht zu verlieren (Spielstand der Hälfte)."""
    at = betrete("tipp-haelfte", "Anna", seed=1)
    starte_spiel(at, 2)
    r = raum_von(at)
    at.toggle(key="cfg_raum_tipps").set_value(True).run()
    spiele(at, lambda s: r.pause is None and s.am_zug is not None and s.am_zug.spieler == 0
           and s.am_zug.wurf is not None)
    at.run()
    emp = r.sitzung.empfehlung(0)
    assert at.success[0].value == emp.begruendung() and "die Hälfte nicht zu verlieren" in emp.begruendung()


def test_zum_ende_springen_wenn_nur_bots_spielen():
    at = betrete("vorspulen", "Anna", seed=4)
    starte_spiel(at, 3, stufe="Kneipengänger")
    r = raum_von(at)
    assert not [b for b in at.button if b.key == "spiel_vorspulen"]
    spiele(at, lambda s: r.pause is not None and not r.pause.runde and r.nur_bots, schritte=20000)
    at.run()
    knopf = at.button(key="spiel_vorspulen")
    assert knopf.label in ("Zum Ende der Hälfte springen", "Zum Rundenende springen")
    s, n = r.sitzung, len(r.sitzung.ausgewertet)
    knopf.click().run()
    assert not at.exception and len(s.ausgewertet) > n and not r.nur_bots
    assert not [b for b in at.button if b.key == "spiel_vorspulen"] and at.button(key="spiel_bestaetigen")


def test_spiel_ohne_tipp_verraet_nichts():
    at = betrete("ohne-tipp", "Anna", seed=1)
    starte_spiel(at, 2)
    r = raum_von(at)
    spiele(at, lambda s: r.pause is None and s.am_zug is not None and s.am_zug.spieler == 0
           and s.am_zug.wurf is not None)
    at.run()
    knoepfe = [b for b in at.button if b.key in ("spiel_wuerfeln", "spiel_klopfen") or b.key.startswith("opt_")]
    assert knoepfe and all("%" not in b.label for b in knoepfe) and not at.success


def test_spiel_wuerfel_markieren():
    """Angetippte Würfel bleiben liegen, der Rest wird neu gewürfelt; die Tabelle folgt der Sitzordnung."""
    at = betrete("markieren", "Anna", seed=6)
    starte_spiel(at, 2)
    r = raum_von(at)
    s = r.sitzung
    spiele(at, lambda s: r.pause is None and s.am_zug is not None and s.am_zug.spieler == 0
           and s.am_zug.stand == AM_WUERFELN)
    at.run()
    zug = s.durchgang.zug(0)
    reihe = [s.name(i) for i in s.runde.teilnehmer]
    html = tabelle(at)
    assert [html.index(n) for n in reihe] == sorted(html.index(n) for n in reihe)
    auswahl = at.pills[0]
    werte = [AUGEN_WERT[o.strip("​")] for o in auswahl.options]
    assert len(set(auswahl.options)) == 3                     # auch bei gleichen Augen unterscheidbar
    auswahl.set_value([0, 2]).run()
    assert "1 Würfel neu würfeln" in at.button(key="spiel_wuerfeln").label
    nr = zug.wurf_nr
    at.button(key="spiel_wuerfeln").click().run()
    assert not at.exception and zug.wurf_nr == nr + 1
    assert zug.schritte[-1].fest == tuple(sorted((werte[0], werte[2])))
    # alle drei markiert: nur noch Klopfen
    if zug.stand == AM_WUERFELN:
        at.pills[0].set_value([0, 1, 2]).run()
        assert at.button(key="spiel_wuerfeln").disabled
        at.button(key="spiel_klopfen").click().run()
        assert not at.exception and zug.stand == FERTIG


def test_verdeckter_wurf_auch_fuer_dich_verdeckt():
    z = Zug(0, grenze=3, wurf_nr=3, wurf=(1, 1, 5), stand=VERDECKT, aufgedeckt=False,
            schritte=[Schritt((), (2, 3, 6)), Schritt((), (1, 4, 6)), Schritt((1, 1), (5,))])
    assert schritte_html(z).count('class="q"') == 1 and AUGEN[5] not in schritte_html(z).split("→")[-1]
    assert ergebnis_html(z) == augen((1, 1), liegt=True) + '<span class="q"></span>'   # „Max ?“
    assert ergebnis_html(z, alles=True) == augen((1, 1, 5))                               # Würfel statt „Max 5“


def test_spiel_stechen_per_wuerfeln():
    at = betrete("stechen", "Anna", seed=2)
    starte_spiel(at, 2)
    s = raum_von(at).sitzung
    s.haelfte.werte_aus({0: (2, 4, 5), 1: (2, 4, 5), 2: (6, 6, 6)})   # du und Bot 1 sind Schlechteste
    at.run()
    assert at.subheader[0].value == "Stechen"
    assert any(f"Gleichstand mit {s.name(1)}." in m.value for m in at.markdown)
    assert any(c.value.startswith("Schon gewürfelt: ") for c in at.caption)   # der Bot würfelt sofort
    for _ in range(20):
        if s.stechen is None:
            break
        at.button(key="spiel_wuerfeln").click().run()
        assert not at.exception
    assert s.stechen is None and sum(s.haelfte.bricken.values()) == 3
    assert any(e.art == "stechen" and "=" in e.text for e in s.protokoll)


def test_zwei_handys_in_einem_raum():
    anna = betrete("zwei handys", "Anna", seed=4)
    ben = betrete("Zwei Handys", "Ben")
    r = raum_von(anna)
    assert raum_von(ben) is r and r.menschen == ["Anna", "Ben"]
    assert any("Anna startet das Spiel" in i.value for i in ben.info)
    assert not [b for b in ben.button if b.key == "spiel_starten"]          # nur der Ersteller startet
    anna.run()
    assert "Ben" in anna.table[0].value.iloc[1, 0]
    starte_spiel(anna, 1)
    # Schuss: Beide dürfen würfeln, egal wer zuerst
    ben.run()
    anna.run()
    assert ben.button(key="spiel_wuerfeln") and anna.button(key="spiel_wuerfeln")
    ben.button(key="spiel_wuerfeln").click().run()
    assert any("Anna" in m.value and "ist dran" in m.value for m in ben.markdown)
    spiele([anna, ben], lambda s: r.pause is not None)
    anna.run()
    ben.run()
    assert r.restzeit() == pytest.approx(PAUSE_DURCHGANG, abs=2)
    assert any("Weiter in spätestens" in c.value for c in anna.caption)
    anna.button(key="spiel_bestaetigen").click().run()
    assert any("Warte auf Ben" in c.value for c in anna.caption)
    spiele([anna, ben], lambda s: len(s.ausgewertet) >= 4)      # ein paar Durchgänge reichen
    assert not anna.exception and not ben.exception


def test_wiedereinstieg_ueber_die_url():
    anna = betrete("neu laden", "Anna")
    nochmal = AppTest.from_file(APP, default_timeout=10)
    nochmal.query_params["raum"] = "neu laden"
    nochmal.query_params["name"] = "anna"
    nochmal.run()
    nochmal.switch_page("app_pages/spiel.py").run()
    assert not nochmal.exception
    assert nochmal.session_state.spiel_raum == "neuladen" and nochmal.session_state.spiel_name == "Anna"
    assert raum_von(anna).menschen == ["Anna"] and nochmal.button(key="spiel_starten")


def test_zuschauer_und_entfernen():
    anna = betrete("zuschauen", "Anna", seed=5)
    starte_spiel(anna, 2)
    cleo = betrete("zuschauen", "Cleo")
    assert any("Du schaust zu" in i.value for i in cleo.info)
    assert not any(b.key in ("spiel_wuerfeln", "spiel_bestaetigen") for b in cleo.button)
    anna.run()
    anna.button(key="spiel_entfernen_Cleo").click().run()
    cleo.run()
    assert cleo.button(key="spiel_betreten")
    assert any("nicht mehr in diesem Raum" in w.value for w in cleo.warning)
    # Ein altes Handy mit Raum und Name in der URL kommt nicht von selbst zurück
    alt = AppTest.from_file(APP, default_timeout=10)
    alt.query_params["raum"] = "zuschauen"
    alt.query_params["name"] = "Cleo"
    alt.run()
    alt.switch_page("app_pages/spiel.py").run()
    assert not alt.exception and alt.session_state.spiel_raum is None
    assert alt.text_input(key="cfg_spiel_name").value == "Cleo" and "Cleo" not in raum_von(anna).menschen


def test_betreten_ohne_name():
    at = starte()
    at.switch_page("app_pages/spiel.py").run()
    at.text_input(key="cfg_spiel_raum").set_value("irgendwo")
    at.button(key="spiel_betreten").click().run()
    assert not at.exception and at.session_state.spiel_raum is None
    assert any("Namen" in w.value for w in at.warning)


def test_bildschirm_anlassen_schalter():
    """Schalter im Seitenmenü, Standard an; das Skript bekommt den Zustand mit."""
    at = starte()
    schalter = at.sidebar.toggle(key="wach")
    assert schalter.value is True
    assert "maxenWach = true" in at.sidebar.get("html")[0].proto.body
    schalter.set_value(False).run()
    assert "maxenWach = false" in at.sidebar.get("html")[0].proto.body
    at.switch_page("app_pages/assistent.py").run()
    assert at.sidebar.toggle(key="wach").value is False        # gilt für alle Seiten


def test_raum_aus_der_liste_betreten():
    """Aktive Räume stehen beim Einstieg; antippen tritt bei, wenn der Name schon steht."""
    anna = betrete("liste-tisch", "Anna")
    ben = starte()
    ben.switch_page("app_pages/spiel.py").run()
    knopf = ben.button(key="spiel_raum_liste-tisch")
    assert "liste-tisch" in knopf.label and "1 Mensch" in knopf.label and "Warteraum" in knopf.label
    # ohne Namen: nur eintragen und nach dem Namen fragen
    knopf.click().run()
    assert ben.text_input(key="cfg_spiel_raum").value == "liste-tisch" and ben.warning
    assert ben.button(key="spiel_betreten")
    # mit Namen: sofort im Raum
    ben.text_input(key="cfg_spiel_name").set_value("Ben")
    ben.button(key="spiel_raum_liste-tisch").click().run()
    assert not ben.exception and raum_von(anna).menschen == ["Anna", "Ben"]
    assert ben.query_params["raum"] == "liste-tisch" and ben.subheader[0].value == "Raum liste-tisch"
