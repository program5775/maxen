"""Seite „Assistent“: Empfehlung für echte Würfe am Tisch.

Ablauf eines Durchgangs: Würfe eingeben -> Empfehlung + Optionstabelle -> Option
wählen -> nächster Wurf (liegen gelassene Würfel sind vorbelegt) -> … bis
„klopfen“. Die App wird am Handy benutzt, daher große Touch-Ziele.
"""
import streamlit as st

from maxen.regeln import RANG, bewerte, wurf_name
from ui import AUGEN, augen, lade_engine, optionsknoepfe, optionstabelle, prozent, wuerfel_html, wuerfel_tabelle


# --- Zustand ----------------------------------------------------------------
ss = st.session_state
ss.setdefault("durchgang", 0)     # Teil der Widget-Keys, damit ein neuer Durchgang die Eingaben leert
ss.setdefault("wurf_nr", 1)
ss.setdefault("fest", ())         # Würfel, die aus dem letzten Wurf liegen
ss.setdefault("verlauf", [])
ss.setdefault("ende", None)       # Endwurf, sobald „klopfen“ gewählt wurde
ss.setdefault("cfg_wuerfe", 3)
ss.setdefault("cfg_gegner", 1)
ss.setdefault("cfg_start", False)
ss.setdefault("letzte_wuerfe", 3)


def neuer_durchgang() -> None:
    ss.durchgang += 1
    ss.wurf_nr = 1
    ss.fest = ()
    ss.verlauf = []
    ss.ende = None


def wuerfe_geaendert() -> None:
    # Segmented Control lässt sich abwählen – dann den alten Wert behalten
    if ss.cfg_wuerfe is None:
        ss.cfg_wuerfe = ss.letzte_wuerfe
    if ss.cfg_wuerfe != ss.letzte_wuerfe:
        ss.letzte_wuerfe = ss.cfg_wuerfe
        neuer_durchgang()


def wuerfel_key(i: int) -> str:
    return f"w_{ss.durchgang}_{ss.wurf_nr}_{i}"


def waehle(option, wurf, neu) -> None:
    ss.verlauf.append(dict(wurf_nr=ss.wurf_nr, fest=ss.fest, neu=neu, wurf=wurf, text=option.text,
                           gedreht=option.aktion == "drehen"))
    if option.aktion == "klopfen":
        ss.ende = wurf
    else:
        ss.fest = option.neu_fest
        ss.wurf_nr += 1


def zurueck() -> None:
    schritt = ss.verlauf.pop()
    ss.ende = None
    ss.wurf_nr = schritt["wurf_nr"]
    ss.fest = schritt["fest"]
    for i, w in enumerate(schritt["neu"]):
        ss[wuerfel_key(i)] = w


# --- Konfiguration des Durchgangs --------------------------------------------
with st.expander("Durchgang einstellen", expanded=not ss.verlauf and ss.ende is None):
    st.toggle("Ich bin Startspieler", key="cfg_start", on_change=neuer_durchgang, persist_state="session")
    if ss.cfg_start:
        st.caption("Als Startspieler darfst du bis zu dreimal würfeln. "
                   "Wie oft du würfelst, dürfen die anderen höchstens würfeln.")
    st.segmented_control(
        "Erlaubte Würfe", options=[1, 2, 3], key="cfg_wuerfe", on_change=wuerfe_geaendert,
        format_func=lambda n: "1 (Schuss)" if n == 1 else str(n), disabled=ss.cfg_start,
        persist_state="session",
    )
    st.number_input("Gegner (Mitspieler außer dir)", min_value=1, max_value=10, step=1,
                    key="cfg_gegner", on_change=neuer_durchgang, persist_state="session")

startspieler, gegner = ss.cfg_start, ss.cfg_gegner
wuerfe = 3 if startspieler else ss.cfg_wuerfe
engine = lade_engine(wuerfe, gegner, startspieler)

# --- Ende des Durchgangs -----------------------------------------------------
if ss.ende is not None:
    s = bewerte(ss.ende)
    st.subheader("Durchgang beendet")
    st.markdown(wuerfel_html((), ss.ende), unsafe_allow_html=True)
    st.metric("Ergebnis", wurf_name(ss.ende), f"Rang {RANG[s]}", delta_color="off")
    letzter_wurf = ss.verlauf[-1]["wurf_nr"]
    st.write(f"Chance, nicht zu verlieren: **{prozent(engine.endnutzen(letzter_wurf)[s])}**")
    if startspieler:
        st.write(f"Die anderen dürfen höchstens **{min(letzter_wurf, 3)}-mal** würfeln.")
    st.button("Neuer Durchgang", type="primary", width="stretch", on_click=neuer_durchgang)
    st.button("↩ Zurück", width="stretch", on_click=zurueck)
    st.stop()

# --- Würfeleingabe ----------------------------------------------------------
if ss.wurf_nr == 4:
    st.subheader("Bonuswurf (Wurf 4)")
elif startspieler:
    st.subheader(f"Wurf {ss.wurf_nr} (Startspieler, bis zu 3)")
elif wuerfe == 1:
    st.subheader("Schuss")
else:
    st.subheader(f"Wurf {ss.wurf_nr} von {wuerfe}")

if ss.fest:
    st.markdown(f"Liegen: {augen(ss.fest, liegt=True)} – gib die neu gewürfelten Würfel ein:",
                unsafe_allow_html=True)

neu = []
with st.container(key="assistent_wuerfel"):
    for i in range(3 - len(ss.fest)):
        neu.append(st.segmented_control(
            f"Würfel {len(ss.fest) + i + 1}", options=list(AUGEN), format_func=AUGEN.get, key=wuerfel_key(i),
            persist_state="session",
        ))

if None in neu:
    if ss.wurf_nr == 1:
        st.caption(f"Vor dem ersten Wurf: {prozent(engine.startwert().nutzen)} Chance, nicht zu verlieren.")
    if ss.verlauf:
        st.button("↩ Zurück", width="stretch", on_click=zurueck)
    st.stop()

neu = tuple(neu)
wurf = tuple(sorted(ss.fest + neu))
gedreht = any(schritt.get("gedreht") for schritt in ss.verlauf)   # höchstens einmal pro Zug
emp = engine.empfehlung(wurf, ss.wurf_nr, gedreht)

# --- Empfehlung -------------------------------------------------------------
st.markdown(wuerfel_html(ss.fest, neu), unsafe_allow_html=True)
st.markdown(f"**{wurf_name(wurf)}** (Rang {RANG[bewerte(wurf)]})")
st.success(emp.begruendung(), icon="👉")
if startspieler and ss.wurf_nr < 3:
    st.caption(f"Klopfst du jetzt, dürfen die anderen höchstens {ss.wurf_nr}-mal würfeln.")

# --- Was tun mit jedem Würfel? ------------------------------------------------
if emp.beste.option.aktion != "klopfen":
    angezeigt = ss.fest + neu   # gleiche Reihenfolge wie die Würfelbilder oben
    wuerfel_tabelle(angezeigt, emp.beste.option)

# --- Optionstabelle ---------------------------------------------------------
optionstabelle(emp)

# --- Auswahl ----------------------------------------------------------------
st.markdown("**Was machst du?**")
optionsknoepfe([], waehle, wurf, neu, emp=emp)

if ss.verlauf:
    st.button("↩ Zurück", width="stretch", on_click=zurueck)
    with st.expander("Verlauf"):
        for schritt in ss.verlauf:
            st.write(f"Wurf {schritt['wurf_nr']}: {', '.join(map(str, schritt['wurf']))} → {schritt['text']}")
