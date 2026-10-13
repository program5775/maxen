"""Seite „Spielen“: Maxen mit anderen Menschen und Computergegnern, jeder am eigenen Handy.

Mit Name und Raum-ID betritt man einen Raum oder erstellt ihn. Im Warteraum stellt der Ersteller
die Computergegner ein und startet das Spiel. Allein gegen Computergegner: einfach einen eigenen
Raum erstellen und starten.

Der Spielzustand liegt in `maxen.raum` (ein `Raeume`-Objekt für alle Sitzungen, `ui.raeume`),
in der Session nur Raum-ID und Name. Ein Fragment fragt regelmäßig nach, ob sich im Raum etwas
geändert hat, und zeichnet dann die ganze Seite neu. Raum-ID und Name stehen in der URL, damit
man nach einem Neuladen ohne Eingabe zurückkommt.
"""
import random

import streamlit as st

from maxen.bots import STUFEN
from maxen.raum import MAX_BOTS, WARTEN
from maxen.regeln import bewerte, name, wurf_name
from maxen.spiel import AM_WUERFELN, BEREIT, VERTEILEN, WUERFELN, Durchgang, aufzaehlung
from ui import lade_engine, optionsknoepfe, optionstabelle, prozent, raeume, wuerfel_html, wuerfel_tabelle

ss = st.session_state
ss.setdefault("spiel_raum", None)        # ID des Raums, in dem du bist
ss.setdefault("spiel_name", None)        # dein Name, wie er im Raum steht
ss.setdefault("spiel_seed", None)        # nur für Tests: fester Zufall für neue Räume
ss.setdefault("spiel_version", -1)       # Version des Raums beim letzten Zeichnen
ss.setdefault("spiel_meldung", None)
ss.setdefault("spiel_url_geprueft", False)
ss.setdefault("cfg_spiel_name", "")
if "cfg_spiel_raum" not in ss:
    ss.cfg_spiel_raum = st.query_params.get("raum", "")


# --- Ein- und Austritt ---------------------------------------------------------------
def betreten() -> None:
    ss.spiel_meldung = None
    rng = random.Random(ss.spiel_seed) if ss.spiel_seed is not None else None
    try:
        r, n = raeume().betreten(ss.cfg_spiel_raum, ss.cfg_spiel_name, rng=rng)
    except ValueError as e:
        ss.spiel_meldung = str(e)
        return
    ss.spiel_raum, ss.spiel_name = r.id, n
    st.query_params.from_dict({"raum": r.id, "name": n})


def verlassen() -> None:
    raeume().verlassen(ss.spiel_raum, ss.spiel_name)
    ss.spiel_raum = ss.spiel_name = None
    st.query_params.clear()


def einstellen(feld: str) -> None:
    r = raeume().raum(ss.spiel_raum)
    if r is not None:
        r.einstellen(ss.spiel_name, **{feld: ss[f"cfg_raum_{feld}"]})


# Nach einem Neuladen: mit Raum und Name aus der URL zurück in den Raum, falls es ihn noch gibt
if not ss.spiel_url_geprueft:
    ss.spiel_url_geprueft = True
    q = st.query_params
    if ss.spiel_raum is None and q.get("raum") and q.get("name") and raeume().raum(q["raum"]):
        ss.cfg_spiel_raum, ss.cfg_spiel_name = q["raum"], q["name"]
        betreten()

raum = raeume().raum(ss.spiel_raum) if ss.spiel_raum else None
if ss.spiel_raum and (raum is None or ss.spiel_name not in raum.menschen):
    ss.spiel_meldung = ("Den Raum gibt es nicht mehr." if raum is None
                        else "Du bist nicht mehr in diesem Raum.")
    ss.spiel_raum = ss.spiel_name = raum = None
    st.query_params.clear()


@st.fragment(run_every=1.5)
def aktualisieren() -> None:
    """Fragt den Raum ab (prüft dabei die Zeitlimits) und zeichnet bei Änderungen alles neu.
    Während einer Pause mit Zeitlimit zeigt es den Countdown."""
    r = raeume().raum(ss.spiel_raum) if ss.spiel_raum else None
    if r is None or r.tick() != ss.spiel_version:
        st.rerun(scope="app")
    rest = r.restzeit()
    if rest is not None:
        st.caption(f":material/timer: Weiter in spätestens {rest:.0f} s.")


# --- Anzeige-Hilfen ----------------------------------------------------------------
def zeile(e) -> str:
    """Protokollzeile als Markdown."""
    t = e.text.replace(". Hälfte", "\\. Hälfte")      # „1. Hälfte“ nicht als Liste lesen
    if e.art in ("verloren", "verlassen"):
        return f":red[**{t}**]"
    if e.art == "bricken":
        return f"**{t}**"
    if e.art in ("runde", "haelfte", "durchgang", "phase", "sitzordnung"):
        return f":blue[{t}]"
    if e.art == "urlaub":
        return f":green[{t}]"
    return t


def kurz(wurf) -> str:
    return ",".join(map(str, sorted(wurf, reverse=True)))


def wuerfe_spalte(z, sichtbar_alle: bool) -> str:
    """Alle Würfe des Zugs: liegen gelassene Würfel fett, dahinter die neu gewürfelten,
    verdeckte als „?“. Deine eigenen Würfe siehst du immer."""
    sichtbar = len(z.schritte) if sichtbar_alle else z.sichtbar
    teile = []
    for k, sch in enumerate(z.schritte):
        neu = kurz(sch.neu) if k < sichtbar else ",".join("?" * len(sch.neu))
        teil = f"**{kurz(sch.fest)}** + {neu}" if sch.fest else neu
        teile.append(f":material/autorenew: {teil}" if sch.gedreht else teil)
    return " → ".join(teile)


def ergebnis_spalte(z, meins: bool) -> str:
    if z.wurf is None:
        return "–"
    if z.aufgedeckt:
        return wurf_name(z.wurf)
    return f"{wurf_name(z.wurf)} (verdeckt)" if meins else "verdeckt"


def spieler_spalte(i: int, start: int | None, am_zug: bool = False) -> str:
    sp = s.spieler[i]
    n = sp.name + (" (du)" if i == ich else "") + (" :material/smart_toy:" if sp.bot else "")
    if am_zug:
        n = f"**{n}** :material/arrow_left:"
    if i == start:
        n += " :material/flag:"
    return n


def bricken_spalte(vorher: int, nachher: int) -> str:
    if nachher > vorher:
        return f":red[{vorher} → **{nachher}**]"
    if nachher < vorher:
        return f":green[{vorher} → **{nachher}**]"
    return str(nachher)


def durchgang_tabelle(d: Durchgang, haelfte, zeilen: list[dict]) -> None:
    """Spieler ohne Platz im Durchgang (Urlaub, nicht im Finale) unten anhängen."""
    for i in s.runde.teilnehmer:
        if i not in d.reihenfolge:
            dabei = i in haelfte.teilnehmer
            zeilen.append({"Spieler": spieler_spalte(i, None), "Bricken": str(haelfte.bricken[i]) if dabei else "",
                           "Würfe": "", "Ergebnis": "Urlaub" if dabei else "spielt nicht"})
    st.table(zeilen, hide_index=True, alt=f"Durchgang {d.nummer}: Würfe, Ergebnisse und Bricken pro Spieler")
    st.caption("Würfe: **fett** = liegen gelassen, dahinter + neu gewürfelt · "
               ":material/autorenew: = gedreht · ? = verdeckt · :material/flag: = Startspieler")


def du(i: int, du_form: str, er_form: str) -> str:
    return f"Du {du_form}" if i == ich else f"{s.name(i)} {er_form}"


def namen(indizes) -> str:
    return aufzaehlung(s.name(i) for i in indizes)


st.title("🎲🎲🎲 Maxen spielen") #

# --- Einstieg ----------------------------------------------------------------------
if raum is None:
    if ss.spiel_meldung:
        st.warning(ss.spiel_meldung, icon=":material/info:")
    st.text_input("Dein Name", key="cfg_spiel_name", max_chars=20, persist_state="session")
    st.text_input("Raum", key="cfg_spiel_raum", max_chars=30, persist_state="session",
                  placeholder="z. B. stammtisch")
    st.caption("Gibt es den Raum noch nicht, wird er erstellt. Wer dieselbe Raum-ID eingibt, spielt mit. "
               "Allein gegen Computergegner: einfach einen eigenen Raum erstellen.")
    st.button("Raum betreten", key="spiel_betreten", type="primary", width="stretch", on_click=betreten,
              icon=":material/login:")
    st.stop()

ich_name = ss.spiel_name
countdown = False                        # Fragment schon gezeichnet (in der Pause beim Weiter-Knopf)

with raum.lock:     # nichts von halb geänderten Zuständen zeichnen
    ss.spiel_version = raum.version
    ersteller = raum.ersteller == ich_name
    marke = raum.marke(ich_name)

    # --- Warteraum -------------------------------------------------------------------
    if raum.status == WARTEN:
        st.subheader(f"Raum {raum.id}")
        st.table(
            [{"Spieler": n + (" (du)" if n == ich_name else ""),
              "Rolle": ":material/star: Ersteller" if n == raum.ersteller else ""} for n in raum.menschen],
            hide_index=True, alt="Menschen im Raum",
        )
        if ersteller:
            ss.cfg_raum_bots, ss.cfg_raum_stufe = raum.bots, raum.stufe
            st.segmented_control("Computergegner", options=list(range(MAX_BOTS + 1)), key="cfg_raum_bots",
                                 required=True, on_change=einstellen, args=("bots",))
            st.segmented_control("Stärke", options=list(STUFEN), key="cfg_raum_stufe", required=True,
                                 on_change=einstellen, args=("stufe",))
            st.caption("Anfänger: einfache Faustregel, dreht nie. Fortgeschritten: spielt meist gut, macht kleine "
                       "Fehler, aber keine groben. Profi: spielt immer die Empfehlung der Engine.")
            genug = len(raum.menschen) + raum.bots >= 2
            st.button("Spiel starten", key="spiel_starten", type="primary", width="stretch",
                      on_click=raum.starten, args=(ich_name, marke), disabled=not genug,
                      icon=":material/play_arrow:")
            if not genug:
                st.caption("Warte auf Mitspieler oder wähle Computergegner.")
        else:
            bots = f"{raum.bots} Computergegner ({raum.stufe})" if raum.bots else "keine Computergegner"
            st.info(f"{raum.ersteller} startet das Spiel, sobald alle da sind. Bisher: {bots}.",
                    icon=":material/hourglass_empty:")

    # --- Spiel -----------------------------------------------------------------------
    else:
        s = raum.sitzung
        r = s.runde
        ich = raum.index(ich_name)          # None: du schaust zu
        p = raum.pause
        tipps = raum.tipps
        if ich is None:
            st.info("Du schaust zu und spielst ab der nächsten Runde mit.", icon=":material/visibility:")

        if p is not None:
            # --- Pause: Ergebnis des Durchgangs bzw. Ende der Runde ---------------------------
            fertig = raum.ausgewertet
            if fertig is not None:
                a = fertig.auswertung
                h = a.haelfte
                st.caption(f"Runde {len(s.runden)} · {h.art} · Durchgang {fertig.nummer} · Ergebnis")
                art = "das Finale" if h.art == "Finale" else f"die {h.art}"
                if a.anzahl is None:
                    text = f"General! {du(a.empfaenger, 'hast', 'hat')} das schlechteste Ergebnis und damit {art} verloren."
                else:
                    if a.geber is None:
                        text = du(a.empfaenger, "bekommst", "bekommt") + f" {a.anzahl} Bricken aus der Mitte"
                    else:
                        text = du(a.geber, "gibst", "gibt") + f" {a.anzahl} Bricken an " + \
                            ("dich" if a.empfaenger == ich else s.name(a.empfaenger)) + " ab"
                    text += f" (bestes Ergebnis: {name(a.bestes)})."
                    if a.verloren:
                        text += " " + du(a.empfaenger, "hast", "hat") + \
                            f" alle {a.nachher[a.empfaenger]} Bricken und {art} verloren."
                if a.empfaenger == ich:
                    st.error(text, icon=":material/sentiment_dissatisfied:")
                elif ich in fertig.reihenfolge:
                    st.success(text, icon=":material/sentiment_satisfied:")
                else:
                    st.info(text)

                ergebnisse = a.ergebnisse
                reihe = sorted(ergebnisse, key=lambda i: bewerte(ergebnisse[i]), reverse=True)
                durchgang_tabelle(fertig, h, [
                    {"Spieler": spieler_spalte(i, fertig.startspieler),
                     "Bricken": bricken_spalte(a.vorher[i], a.nachher[i]),
                     "Würfe": wuerfe_spalte(fertig.zug(i), True), "Ergebnis": wurf_name(ergebnisse[i])}
                    for i in reihe
                ])
                for stich in a.stechen:
                    runden = [", ".join(f"{s.name(i)} {sum(w)}" for i, w in wuerfe.items()) for wuerfe in stich.runden]
                    st.caption(f"Stechen, {stich.worum}: " + " · dann ".join(runden))
                if a.geber is not None and a.nachher[a.geber] == 0:
                    st.caption(du(a.geber, "hast", "hat") + " keine Bricken mehr und damit Urlaub.")
                if a.phase_2:
                    st.info("Die Mitte ist leer. Ab jetzt Phase 2: Der Beste gibt Bricken an den Schlechtesten ab. "
                            "Wer keine Bricken hat, hat Urlaub.", icon=":material/swap_horiz:")

            if p.runde:
                if r.verlassen:
                    text = f"{s.name(r.verlierer)} hat den Tisch verlassen und damit die Runde verloren."
                else:
                    text = du(r.verlierer, "hast", "hat") + \
                        f" die Runde verloren{' – mit einem glatten Gang' if r.glatter_gang else ''}."
                (st.error if r.verlierer == ich else st.success)(text)
                if raum.zuschauer:
                    st.caption(f"In der nächsten Runde neu dabei: {aufzaehlung(raum.zuschauer)}.")
                weiter_text = "Nächste Runde"
            else:
                weiter_text = f"Weiter: {s.haelfte.art}" if fertig.auswertung.verloren else "Nächster Durchgang"

            if ich in p.warten_auf:
                st.button(weiter_text, key="spiel_bestaetigen", type="primary", width="stretch",
                          on_click=raum.bestaetigen, args=(ich_name, marke), icon=":material/skip_next:")
            elif p.warten_auf:
                st.caption(f":material/hourglass_empty: Warte auf {namen(sorted(p.warten_auf))}.")
            aktualisieren()
            countdown = True

        else:
            # --- Laufender Durchgang -------------------------------------------------------
            h, d = s.haelfte, s.durchgang
            phase = "Phase 1" if h.phase == VERTEILEN else "Phase 2"
            grenze = "Schuss" if d.schuss else (f"Wurfgrenze {d.grenze}" if d.grenze else "Wurfgrenze offen")
            st.caption(f"Runde {len(s.runden)} · {h.art} · {phase} · Mitte: {h.mitte} · Durchgang {d.nummer} · {grenze}")
            durchgang_tabelle(d, h, [
                {"Spieler": spieler_spalte(z.spieler, d.startspieler, z.spieler in s.offen),
                 "Bricken": str(h.bricken[z.spieler]),
                 "Würfe": wuerfe_spalte(z, z.spieler == ich), "Ergebnis": ergebnis_spalte(z, z.spieler == ich)}
                for z in d.zuege
            ])
            zug = d.zug(ich) if ich in s.offen and s.stechen is None else None

            if s.stechen is not None and ich in s.stechen.kandidaten:
                stechen = s.stechen
                andere = namen(i for i in stechen.kandidaten if i != ich)
                st.subheader("Stechen")
                st.markdown(f"Gleichstand mit {andere}. Gestochen wird, {stechen.worum}.")
                st.caption("Jeder würfelt einmal mit allen drei Würfeln, es zählt die Augensumme. "
                           + ("Die höchste Summe gewinnt." if stechen.hoch else "Die niedrigste Summe verliert.")
                           + " Bei gleicher Summe wird neu geworfen.")
                for wuerfe in stechen.runden:
                    st.caption("Gleiche Summe: " + ", ".join(f"{s.name(i)} {kurz(w)} = {sum(w)}"
                                                             for i, w in wuerfe.items()))
                if stechen.aktuell:
                    st.caption("Schon gewürfelt: " + ", ".join(f"{s.name(i)} {kurz(w)} = {sum(w)}"
                                                               for i, w in stechen.aktuell.items()))
                if ich in stechen.offen:
                    st.button("Würfeln", key="spiel_wuerfeln", type="primary", width="stretch",
                              on_click=raum.ausfuehren, args=(ich_name, marke, WUERFELN), icon=":material/casino:")
                else:
                    st.caption(f":material/hourglass_empty: Warte auf {namen(stechen.offen)}.")

            elif zug is None:
                wer = namen(s.offen)
                if s.stechen is not None:
                    st.markdown(f"**Stechen:** {namen(s.stechen.kandidaten)} stechen, {s.stechen.worum}. "
                                f"Warte auf {wer}.")
                else:
                    st.markdown(f":material/hourglass_empty: **{wer}** {'ist' if len(s.offen) == 1 else 'sind'} dran.")

            elif zug.stand == BEREIT:
                if d.schuss:
                    st.markdown("**Schuss:** Alle haben nur einen Wurf und würfeln gleichzeitig.")
                elif zug.bestimmt_grenze:
                    st.markdown("**Du bist Startspieler.** Du darfst bis zu dreimal würfeln. "
                                "Wie oft du würfelst, so oft dürfen die anderen höchstens würfeln.")
                else:
                    st.markdown(f"Du darfst höchstens **{zug.grenze}-mal** würfeln.")
                if tipps:
                    start = lade_engine(zug.grenze, d.gegner, zug.bestimmt_grenze).startwert()
                    st.caption(f"Vor dem ersten Wurf: {prozent(start.nutzen)} Chance, nicht zu verlieren.")
                st.button("Würfeln", key="spiel_wuerfeln", type="primary", width="stretch",
                          on_click=raum.ausfuehren, args=(ich_name, marke, WUERFELN), icon=":material/casino:")

            else:
                if zug.stand == AM_WUERFELN:
                    st.subheader(f"Wurf {zug.wurf_nr} (Startspieler, bis zu 3)" if zug.bestimmt_grenze
                                 else f"Wurf {zug.wurf_nr} von {zug.grenze}")
                else:
                    st.subheader("Aufdecken: drehen?")
                    st.caption("Drehst du, würfelst du verdeckt einen Bonuswurf, bevor die anderen aufdecken.")
                wurf = tuple(sorted(zug.wurf, reverse=True))
                st.markdown(wuerfel_html((), wurf), unsafe_allow_html=True)
                st.markdown(f"**{wurf_name(wurf)}**")
                emp = s.empfehlung(ich) if tipps else None
                if emp is not None:
                    st.success(emp.begruendung(), icon="👉")
                    if zug.bestimmt_grenze and zug.stand == AM_WUERFELN and zug.wurf_nr < 3:
                        st.caption(f"Bleibst du jetzt stehen, dürfen die anderen höchstens {zug.wurf_nr}-mal würfeln.")
                    if emp.beste.option.aktion != "stehen":
                        wuerfel_tabelle(wurf, emp.beste.option)
                st.markdown("**Was machst du?**")
                optionsknoepfe(zug.optionen(), lambda o, n, m: raum.ausfuehren(n, m, o), ich_name, marke, emp=emp)
                if emp is not None:
                    with st.expander("Wahrscheinlichkeiten pro Option"):
                        optionstabelle(emp)

        with st.expander("Spielstand"):
            st.table(
                {
                    "Spieler": [s.name(i) for i in r.teilnehmer],
                    "Stärke": [s.spieler[i].bot.stufe if s.spieler[i].bot else "Mensch" for i in r.teilnehmer],
                    "Hälften verloren": [", ".join(x.art for x in r.haelften if x.verlierer == i)
                                         for i in r.teilnehmer],
                    "Runden verloren": [sum(x.verlierer == i for x in s.runden) for i in r.teilnehmer],
                },
                hide_index=True,
                alt="Verlorene Hälften und Runden pro Spieler",
            )
        with st.expander("Protokoll"):
            st.markdown("\n".join(f"- {zeile(e)}" for e in s.protokoll))

    # --- Raum: Teilen, Menschen, Verwaltung ------------------------------------------------
    with st.expander(f"Raum {raum.id}", icon=":material/group:", expanded=raum.status == WARTEN):
        if st.context.url:
            st.caption("Link zum Mitspielen:")
            st.code(f"{st.context.url}?raum={raum.id}", language=None)
        if raum.status != WARTEN:
            st.markdown("Im Raum: " + ", ".join(
                n + (" :material/star:" if n == raum.ersteller else "")
                + (" (schaut zu)" if n in raum.zuschauer else "") for n in raum.menschen))
        if ersteller:
            ss.cfg_raum_tipps = raum.tipps
            st.toggle("Tipps für alle anzeigen", key="cfg_raum_tipps", on_change=einstellen, args=("tipps",))
            for n in raum.menschen:
                if n != ich_name:
                    st.button(f"{n} entfernen", key=f"spiel_entfernen_{n}", icon=":material/person_remove:",
                              on_click=raum.entfernen, args=(ich_name, marke, n),
                              help="Mitten in einer Runde zählt das als verloren.")
            if raum.status != WARTEN:
                st.button("Spiel beenden", key="spiel_beenden", width="stretch", on_click=raum.beenden,
                          args=(ich_name, marke), icon=":material/stop:",
                          help="Alle kommen zurück in den Warteraum.")
        else:
            st.caption(f"Ersteller: {raum.ersteller}. Tipps sind {'an' if raum.tipps else 'aus'}.")
        with st.popover("Raum verlassen", icon=":material/logout:", width="stretch"):
            if raum.status != WARTEN and raum.index(ich_name) is not None and not raum.sitzung.runde.beendet:
                st.warning("Die Runde läuft noch. Wenn du jetzt gehst, hast du sie verloren.")
            st.button("Ja, verlassen", key="spiel_verlassen", type="primary", width="stretch", on_click=verlassen)

    if not countdown:
        aktualisieren()
