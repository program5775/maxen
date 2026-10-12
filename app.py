"""Streamlit-UI für den Maxen-Assistenten.

Start: streamlit run app.py

Ablauf einer Runde: Würfe eingeben -> Empfehlung + Optionstabelle -> Option
wählen -> nächster Wurf (liegen gelassene Würfel sind vorbelegt) -> … bis
„stehen“. Die App wird am Handy benutzt, daher große Touch-Ziele.
"""
import streamlit as st

from maxen import Engine, wuerfel_aktionen
from maxen.regeln import MAX, PASCH, RANG, STRASSE, bewerte, wurf_name

AUGEN = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

st.set_page_config(page_title="Maxen", page_icon="🎲", layout="centered")
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stButtonGroup"] button {
        min-height: 3.2rem; min-width: 3.2rem; font-size: 1.4rem; flex: 1 1 0;
    }
    div[data-testid="stButton"] button { min-height: 3.2rem; }
    .wuerfel { font-size: 4.5rem; line-height: 1.1; letter-spacing: .4rem; }
    .wuerfel .fest { opacity: .5; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Berechne optimale Strategie …")
def lade_engine(wuerfe: int, gegner: int) -> Engine:
    return Engine(wuerfe=wuerfe, gegner=gegner)


def wuerfel_html(fest, neu=()) -> str:
    """Würfelbilder; liegen gelassene Würfel werden blasser dargestellt."""
    teile = [f'<span class="fest">{AUGEN[w]}</span>' for w in fest]
    teile += [AUGEN[w] for w in neu]
    return f'<div class="wuerfel">{"".join(teile)}</div>'


def prozent(x: float) -> str:
    return f"{x * 100:.0f} %"


AKTION_BADGE = {
    "liegen": ":green-badge[:material/lock: liegen lassen]",
    "neu": ":orange-badge[:material/casino: neu würfeln]",
    "drehen": ":blue-badge[:material/autorenew: auf 1 drehen]",
}


# --- Zustand ----------------------------------------------------------------
ss = st.session_state
ss.setdefault("runde", 0)         # Teil der Widget-Keys, damit eine neue Runde die Eingaben leert
ss.setdefault("wurf_nr", 1)
ss.setdefault("fest", ())         # Würfel, die aus dem letzten Wurf liegen
ss.setdefault("verlauf", [])
ss.setdefault("ende", None)       # Endwurf, sobald „stehen“ gewählt wurde
ss.setdefault("cfg_wuerfe", 3)
ss.setdefault("cfg_gegner", 1)
ss.setdefault("letzte_wuerfe", 3)


def neue_runde() -> None:
    ss.runde += 1
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
        neue_runde()


def wuerfel_key(i: int) -> str:
    return f"w_{ss.runde}_{ss.wurf_nr}_{i}"


def waehle(option, wurf, neu) -> None:
    ss.verlauf.append(dict(wurf_nr=ss.wurf_nr, fest=ss.fest, neu=neu, wurf=wurf, text=option.text))
    if option.aktion == "stehen":
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


# --- Rundenkonfiguration ----------------------------------------------------
st.title("🎲🎲🎲 Maxen")

with st.expander("Runde einstellen", expanded=not ss.verlauf and ss.ende is None):
    st.segmented_control(
        "Erlaubte Würfe", options=[1, 2, 3], key="cfg_wuerfe", on_change=wuerfe_geaendert,
        format_func=lambda n: "1 (Schuss)" if n == 1 else str(n),
    )
    st.number_input("Gegner (Mitspieler außer dir)", min_value=1, max_value=10, step=1,
                    key="cfg_gegner", on_change=neue_runde)

wuerfe, gegner = ss.cfg_wuerfe, ss.cfg_gegner
engine = lade_engine(wuerfe, gegner)

# --- Rundenende -------------------------------------------------------------
if ss.ende is not None:
    s = bewerte(ss.ende)
    st.subheader("Runde beendet")
    st.markdown(wuerfel_html((), ss.ende), unsafe_allow_html=True)
    st.metric("Ergebnis", wurf_name(ss.ende), f"Rang {RANG[s]}", delta_color="off")
    st.write(f"Chance, nicht zu verlieren: **{prozent(engine.nutzen[s])}**")
    st.button("Neue Runde", type="primary", width="stretch", on_click=neue_runde)
    st.button("↩ Zurück", width="stretch", on_click=zurueck)
    st.stop()

# --- Würfeleingabe ----------------------------------------------------------
if ss.wurf_nr == 4:
    st.subheader("Bonuswurf (Wurf 4)")
elif wuerfe == 1:
    st.subheader("Schuss")
else:
    st.subheader(f"Wurf {ss.wurf_nr} von {wuerfe}")

if ss.fest:
    st.markdown(f"Liegen: **{', '.join(map(str, ss.fest))}** – gib die neu gewürfelten Würfel ein:")

neu = []
for i in range(3 - len(ss.fest)):
    neu.append(st.segmented_control(
        f"Würfel {len(ss.fest) + i + 1}", options=list(AUGEN), key=wuerfel_key(i),
    ))

if None in neu:
    if ss.wurf_nr == 1:
        st.caption(f"Vor dem ersten Wurf: {prozent(engine.startwert().nutzen)} Chance, nicht zu verlieren.")
    if ss.verlauf:
        st.button("↩ Zurück", width="stretch", on_click=zurueck)
    st.stop()

neu = tuple(neu)
wurf = tuple(sorted(ss.fest + neu))
emp = engine.empfehlung(wurf, ss.wurf_nr)

# --- Empfehlung -------------------------------------------------------------
st.markdown(wuerfel_html(ss.fest, neu), unsafe_allow_html=True)
st.markdown(f"**{wurf_name(wurf)}** (Rang {RANG[bewerte(wurf)]})")
st.success(emp.begruendung(), icon="👉")

# --- Was tun mit jedem Würfel? ------------------------------------------------
if emp.beste.option.aktion != "stehen":
    angezeigt = ss.fest + neu   # gleiche Reihenfolge wie die Würfelbilder oben
    st.table(
        {
            "Würfel": [f"{AUGEN[w]} {w}" for w in angezeigt],
            "Empfehlung": [AKTION_BADGE[a] for a in wuerfel_aktionen(angezeigt, emp.beste.option)],
        },
        hide_index=True,
        alt="Empfohlene Aktion pro Würfel",
    )

# --- Optionstabelle ---------------------------------------------------------
st.dataframe(
    [
        {
            "Option": ("★ " if b is emp.beste else "") + b.option.text,
            "Nicht verlieren": b.nutzen * 100,
            "≥ Max": b.mindestens(MAX) * 100,
            "≥ Pasch": b.mindestens(PASCH) * 100,
            "≥ Straße": b.mindestens(STRASSE) * 100,
        }
        for b in emp.optionen
    ],
    hide_index=True,
    width="stretch",
    column_config={
        "Option": st.column_config.TextColumn(pinned=True),
        **{
            spalte: st.column_config.NumberColumn(format="%.0f %%")
            for spalte in ("Nicht verlieren", "≥ Max", "≥ Pasch", "≥ Straße")
        },
    },
)
st.caption("„≥“ bedeutet: diese Kategorie oder besser, bei optimalem Weiterspiel. "
           "Die Empfehlung maximiert die Chance, nicht zu verlieren – nicht die Chance auf eine bestimmte Kategorie.")

# --- Auswahl ----------------------------------------------------------------
st.markdown("**Was machst du?**")
for b in emp.optionen:
    st.button(
        f"{b.option.text} · {prozent(b.nutzen)}",
        key=f"opt_{b.option.aktion}_{b.option.neu_fest}",
        type="primary" if b is emp.beste else "secondary",
        width="stretch",
        on_click=waehle,
        args=(b.option, wurf, neu),
    )

if ss.verlauf:
    st.button("↩ Zurück", width="stretch", on_click=zurueck)
    with st.expander("Verlauf"):
        for schritt in ss.verlauf:
            st.write(f"Wurf {schritt['wurf_nr']}: {', '.join(map(str, schritt['wurf']))} → {schritt['text']}")
