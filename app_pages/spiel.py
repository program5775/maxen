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
import time
from functools import partial
from html import escape

import streamlit as st

from maxen.bots import STUFEN
from maxen.raum import MAX_BOTS, WARTEN
from maxen.regeln import bewerte, name, wurf_name
from maxen.spiel import AM_WUERFELN, BEREIT, WUERFELN, aufzaehlung
from ui import (AUGEN, augen, dreh_text, ergebnis_html, lade_engine, optionstabelle, prozent, raeume, schritte_html,
                tabelle_html, verdeckt)

DIALOG_SEKUNDEN = 3     # so lange bleibt das Ergebnis-Pop-up offen

ss = st.session_state
ss.setdefault("spiel_raum", None)       # ID des Raums, in dem du bist
ss.setdefault("spiel_name", None)        # dein Name, wie er im Raum steht
ss.setdefault("spiel_seed", None)        # nur für Tests: fester Zufall für neue Räume
ss.setdefault("spiel_version", -1)       # Version des Raums beim letzten Zeichnen
ss.setdefault("spiel_meldung", None)
ss.setdefault("spiel_dialog_key", None)  # Durchgang, dessen Ergebnis-Pop-up zuletzt gezeigt wurde
ss.setdefault("spiel_dialog_bis", 0.0)   # bis wann es offen bleibt (time.monotonic)
ss.setdefault("spiel_dialog_zu", False)  # vom Spieler weggeklickt
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


def dialog_zu(bestaetigen=None) -> None:
    """Pop-up weggeklickt (X oder daneben): gilt als „Nächster Durchgang“. Nur, solange es noch offen
    sein sollte; schließt es sich nach Ablauf der Zeit selbst, wird nichts bestätigt."""
    offen = time.monotonic() < ss.spiel_dialog_bis
    ss.spiel_dialog_zu = True
    if offen and bestaetigen is not None:
        bestaetigen()


def einstellen(feld: str) -> None:
    r = raeume().raum(ss.spiel_raum)
    if r is not None:
        r.einstellen(ss.spiel_name, **{feld: ss[f"cfg_raum_{feld}"]})


def auswahl_ausfuehren(r, n: str, m, key: str, werte: tuple[int, ...]) -> None:
    """Würfeln: die markierten Würfel bleiben liegen, der Rest wird neu gewürfelt."""
    fest = tuple(sorted(werte[k] for k in ss.get(key) or ()))
    o = next((o for o in r.optionen(n) if o.aktion == "legen" and o.neu_fest == fest), None)
    if o is not None:
        r.ausfuehren(n, m, o)


# Nach einem Neuladen: mit Raum und Name aus der URL zurück in den Raum, aber nur, wenn du noch
# drin bist. Wer gegangen ist oder entfernt wurde, muss bewusst neu beitreten.
if not ss.spiel_url_geprueft:
    ss.spiel_url_geprueft = True
    q = st.query_params
    if ss.spiel_raum is None and q.get("raum") and q.get("name"):
        ss.cfg_spiel_raum, ss.cfg_spiel_name = q["raum"], q["name"]
        alt = raeume().raum(q["raum"])
        if alt is not None and alt.ist_da(q["name"]):
            betreten()

raum = raeume().raum(ss.spiel_raum) if ss.spiel_raum else None
if ss.spiel_raum and (raum is None or ss.spiel_name not in raum.menschen):
    ss.spiel_meldung = ("Den Raum gibt es nicht mehr." if raum is None
                        else "Du bist nicht mehr in diesem Raum.")
    ss.spiel_raum = ss.spiel_name = raum = None
    st.query_params.clear()


@st.fragment(run_every=1)
def aktualisieren() -> None:
    """Fragt den Raum ab (prüft dabei die Zeitlimits) und zeichnet bei Änderungen alles neu.
    Während einer Pause mit Zeitlimit zeigt es den Countdown."""
    r = raeume().raum(ss.spiel_raum) if ss.spiel_raum else None
    if r is None or r.tick() != ss.spiel_version:
        st.rerun(scope="app")
    if ss.spiel_dialog_bis and time.monotonic() >= ss.spiel_dialog_bis:
        ss.spiel_dialog_bis = 0.0          # Zeit um: Pop-up schließen
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


def wurf_html(w) -> str:
    """Ein Wurf beim Stechen: Würfel und Augensumme."""
    return f"{augen(w)} = {sum(w)}"


def spieler_spalte(i: int, start: int | None, am_zug: bool = False) -> str:
    sp = s.spieler[i]
    n = escape(sp.name) + (" (du)" if i == ich else "") + (" 🤖" if sp.bot else "")
    if am_zug:
        n = f"<b>{n}</b> ◀"
    if i == start:
        n += " 🚩"
    return n


def bricken_spalte(vorher: int, nachher: int) -> str:
    if nachher > vorher:
        return f'<span class="mehr">{vorher} → <b>{nachher}</b></span>'
    if nachher < vorher:
        return f'<span class="weniger">{vorher} → <b>{nachher}</b></span>'
    return str(nachher)


def durchgang_tabelle(haelfte, zeilen: dict[int, dict]) -> None:
    """Eine Zeile pro Spieler der Runde, immer in Sitzordnung. Wer im Durchgang keinen Platz hat
    (Urlaub in Phase 2, nicht im Finale), hat Urlaub. Die Würfe stehen als zweite Zeile unter dem
    Namen, damit die Tabelle auf dem Handy in die Breite passt."""
    alle = [zeilen.get(i) or {"Spieler": spieler_spalte(i, None), "Würfe": "", "Ergebnis": "Urlaub",
                              "Bricken": str(haelfte.bricken[i]) if i in haelfte.teilnehmer else ""}
            for i in s.runde.teilnehmer]
    for z in alle:
        if z["Würfe"]:
            z["Spieler"] += f'<div class="wuerfe">{z["Würfe"]}</div>'
    # Platz für alle Zeilen mit Würfen reservieren, damit nichts darunter springt, wenn die Tabelle wächst
    hoehe = 2 + 4.6 * len(alle)
    st.markdown(f'<div style="min-height: {hoehe:.1f}rem">'
                + tabelle_html(["Spieler", "Bricken", "Ergebnis"], alle) + "</div>", unsafe_allow_html=True)


def mein_wurf(z) -> None:
    """Dein Wurf groß, verdeckte Würfel als „?“ (auch für dich selbst, wie unter dem Becher)."""
    sch = z.schritte[-1]
    zu = z.aufgedeckt
    st.markdown(f'<div class="wuerfel">{augen(sch.fest, liegt=True)}'
                f'{augen(sch.neu) if zu else verdeckt(len(sch.neu))}</div>', unsafe_allow_html=True)
    st.markdown(f"**{wurf_name(z.wurf)}**" if zu else "**Verdeckt** – wird beim Aufdecken gezeigt.")


def du(i: int, du_form: str, er_form: str) -> str:
    return f"Du {du_form}" if i == ich else f"{s.name(i)} {er_form}"


def namen(indizes) -> str:
    return aufzaehlung(s.name(i) for i in indizes)


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
            st.caption("Anfänger: macht öfter Fehler, hält sich nur manchmal an die Faustregeln. "
                       "Stammspieler: spielt nach den Faustregeln vom Tisch und sonst meist gut. "
                       "Mathematiker: spielt immer die Empfehlung der Engine.")
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
                durchgang_tabelle(h, {
                    z.spieler: {"Spieler": spieler_spalte(z.spieler, fertig.startspieler),
                                "Bricken": bricken_spalte(a.vorher[z.spieler], a.nachher[z.spieler]),
                                "Würfe": schritte_html(z, alles=True), "Ergebnis": ergebnis_html(z, alles=True),
                                "_klasse": ("verlierer" if z.spieler == a.empfaenger
                                            else "bester" if bewerte(a.ergebnisse[z.spieler]) == a.bestes
                                            else "")}
                    for z in fertig.zuege
                })

                def ergebnis_inhalt() -> None:
                    if a.empfaenger == ich:
                        st.error(text, icon=":material/sentiment_dissatisfied:")
                    elif ich in fertig.reihenfolge:
                        st.success(text, icon=":material/sentiment_satisfied:")
                    else:
                        st.info(text)
                    for stich in a.stechen:
                        runden = [", ".join(f"{escape(s.name(i))} {wurf_html(w)}" for i, w in wuerfe.items())
                                  for wuerfe in stich.runden]
                        st.caption(f"Stechen, {stich.worum}: " + " · dann ".join(runden), unsafe_allow_html=True)
                    if a.geber is not None and a.nachher[a.geber] == 0 and not a.verloren:
                        st.caption(du(a.geber, "hast", "hat") + " keine Bricken mehr und damit Urlaub.")
                    if a.phase_2:
                        st.info("Die Mitte ist leer.", icon=":material/swap_horiz:")

                # Ergebnis als Pop-up, das nach DIALOG_SEKUNDEN von selbst verschwindet. Der Dialog muss
                # bei jedem Lauf neu aufgerufen werden, sonst schließt ihn der nächste Rerun.
                if ss.spiel_dialog_key != id(fertig):
                    ss.spiel_dialog_key, ss.spiel_dialog_zu = id(fertig), False
                    ss.spiel_dialog_bis = time.monotonic() + DIALOG_SEKUNDEN
                if not ss.spiel_dialog_zu and time.monotonic() < ss.spiel_dialog_bis:
                    weiter = None
                    if ich in p.warten_auf and not p.runde:
                        weiter = partial(raum.bestaetigen, ich_name, marke)
                    st.dialog("Ergebnis", on_dismiss=partial(dialog_zu, weiter))(ergebnis_inhalt)()

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
            st.caption(f"Runde {len(s.runden)} · {h.art} · Mitte: {h.mitte}")
            zug = d.zug(ich) if ich in s.offen and s.stechen is None else None
            durchgang_tabelle(h, {
                z.spieler: {"Spieler": spieler_spalte(z.spieler, d.startspieler, z.spieler in s.offen),
                            "Bricken": str(h.bricken[z.spieler]), "Würfe": schritte_html(z),
                            "Ergebnis": ergebnis_html(z), "_am_zug": z.spieler in s.offen}
                for z in d.zuege
            })

            if s.stechen is not None and ich in s.stechen.kandidaten:
                stechen = s.stechen
                andere = namen(i for i in stechen.kandidaten if i != ich)
                st.subheader("Stechen")
                st.markdown(f"Gleichstand mit {andere}. Gestochen wird, {stechen.worum}.")
                st.caption("Jeder würfelt einmal mit allen drei Würfeln, es zählt die Augensumme. "
                           + ("Die höchste Summe gewinnt." if stechen.hoch else "Die niedrigste Summe verliert.")
                           + " Bei gleicher Summe wird neu geworfen.")
                for wuerfe in stechen.runden:
                    st.caption("Gleiche Summe: " + ", ".join(f"{escape(s.name(i))} {wurf_html(w)}"
                                                             for i, w in wuerfe.items()), unsafe_allow_html=True)
                if stechen.aktuell:
                    st.caption("Schon gewürfelt: " + ", ".join(f"{escape(s.name(i))} {wurf_html(w)}"
                                                               for i, w in stechen.aktuell.items()),
                               unsafe_allow_html=True)
                if ich in stechen.offen:
                    st.button("Würfeln", key="spiel_wuerfeln", type="primary", width="stretch",
                              on_click=raum.ausfuehren, args=(ich_name, marke, WUERFELN), icon=":material/casino:")
                else:
                    st.caption(f":material/hourglass_empty: Warte auf {namen(stechen.offen)}.")

            elif zug is None:
                wer = namen(s.offen)
                if ich in d.reihenfolge and d.zug(ich).wurf is not None:
                    mein_wurf(d.zug(ich))        # bleibt bis zum Ende des Durchgangs stehen
                if s.stechen is not None:
                    st.markdown(f"**Stechen:** {namen(s.stechen.kandidaten)} stechen, {s.stechen.worum}. "
                                f"Warte auf {wer}.")
                else:
                    st.markdown(f":material/hourglass_empty: **{wer}** {'ist' if len(s.offen) == 1 else 'sind'} dran.")

            elif zug.stand == BEREIT:
                if d.schuss:
                    st.markdown("**Schuss:**")
                elif zug.bestimmt_grenze:
                    st.markdown("**Du fängst an.")
                else:
                    st.markdown(f"Du darfst **{zug.grenze}-mal** würfeln.")
                if tipps:
                    start = lade_engine(zug.grenze, d.gegner, zug.bestimmt_grenze).startwert()
                    st.caption(f"Vor dem ersten Wurf: {prozent(start.nutzen)} Chance, nicht zu verlieren.")
                st.button("Würfeln", key="spiel_wuerfeln", type="primary", width="stretch",
                          on_click=raum.ausfuehren, args=(ich_name, marke, WUERFELN), icon=":material/casino:")

            else:
                opts = zug.optionen()
                emp = s.empfehlung(ich) if tipps else None
                nutzen = {b.option: b.nutzen for b in emp.optionen} if emp is not None else {}

                def mit_chance(text: str, o) -> str:
                    return f"{text} · {prozent(nutzen[o])}" if o in nutzen else text

                stehen = next(o for o in opts if o.aktion == "stehen")
                if zug.stand == AM_WUERFELN:
                    st.caption(f"Wurf {zug.wurf_nr} (Startspieler, bis zu 3)" if zug.bestimmt_grenze
                               else f"Wurf {zug.wurf_nr} von {zug.grenze}")
                    # Würfel antippen, die liegen bleiben; vorbelegt mit denen, die schon lagen
                    sch = zug.schritte[-1]
                    werte = tuple(sorted(sch.fest, reverse=True)) + tuple(sorted(sch.neu, reverse=True))
                    key = f"spiel_auswahl_{marke[0]}_{marke[1]}"
                    # Pills merken sich die Auswahl über die Beschriftung: gleiche Augen (6,6) per
                    # unsichtbarem Zeichen unterscheidbar machen
                    with st.container(key="spiel_wuerfel"):
                        auswahl = st.pills("Liegen lassen", options=[0, 1, 2],
                                           format_func=lambda k: AUGEN[werte[k]] + "​" * k,
                                           selection_mode="multi", default=list(range(len(sch.fest))), key=key,
                                           label_visibility="collapsed")
                    fest = tuple(sorted(werte[k] for k in auswahl))
                else:
                    st.subheader("Drehst du?")
                    st.markdown(f'<div class="wuerfel">{augen(zug.wurf)}</div>', unsafe_allow_html=True)
                    st.markdown(f"**{wurf_name(zug.wurf)}**")
                if emp is not None:
                    st.success(emp.begruendung(), icon="👉")
                    if zug.bestimmt_grenze and zug.stand == AM_WUERFELN and zug.wurf_nr < 3:
                        st.caption(f"Bleibst du jetzt stehen, dürfen die anderen höchstens {zug.wurf_nr}-mal würfeln.")

                if zug.stand == AM_WUERFELN:
                    neu = 3 - len(fest)
                    legen = next((o for o in opts if o.aktion == "legen" and o.neu_fest == fest), None)
                    text = ("Alle 3 neu würfeln" if neu == 3 else f"{neu} Würfel neu würfeln") if neu else "Würfeln"
                    st.button(mit_chance(text, legen), key="spiel_wuerfeln", type="primary" if neu else "secondary",
                              width="stretch", icon=":material/casino:", disabled=legen is None,
                              on_click=auswahl_ausfuehren, args=(raum, ich_name, marke, key, werte))
                    st.button(mit_chance(f"Klopfen ({wurf_name(zug.wurf)})", stehen), key="spiel_stehen",
                              type="secondary" if neu else "primary", width="stretch", icon=":material/front_hand:",
                              on_click=raum.ausfuehren, args=(ich_name, marke, stehen))
                else:
                    st.button(mit_chance("Nicht drehen", stehen), key="spiel_stehen", type="primary",
                              width="stretch", on_click=raum.ausfuehren, args=(ich_name, marke, stehen))
                for o in opts:
                    if o.aktion == "drehen":
                        st.button(mit_chance(dreh_text(o), o), key=f"opt_{o.aktion}_{o.neu_fest}", width="stretch",
                                  icon=":material/autorenew:", on_click=raum.ausfuehren, args=(ich_name, marke, o))
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
