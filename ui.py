"""Gemeinsame UI-Teile für Assistent und Spielseite."""
import streamlit as st

from maxen import Engine, wuerfel_aktionen
from maxen.raum import Raeume
from maxen.regeln import MAX, PASCH, STRASSE

AUGEN = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

STIL = """
<style>
.block-container { padding-top: 2rem; }
div[data-testid="stButtonGroup"] button {
    min-height: 3.2rem; min-width: 3.2rem; font-size: 1.4rem; flex: 1 1 0;
}
div[data-testid="stButton"] button { min-height: 3.2rem; }
.wuerfel { font-size: 4.5rem; line-height: 1.1; letter-spacing: .4rem; }
.wuerfel .fest { opacity: .5; }
</style>
"""

AKTION_BADGE = {
    "liegen": ":green-badge[:material/lock: liegen lassen]",
    "neu": ":orange-badge[:material/casino: neu würfeln]",
    "drehen": ":blue-badge[:material/autorenew: auf 1 drehen]",
}


@st.cache_resource(show_spinner="Berechne optimale Strategie …")
def lade_engine(wuerfe: int, gegner: int, startspieler: bool = False) -> Engine:
    return Engine(wuerfe=wuerfe, gegner=gegner, startspieler=startspieler)


@st.cache_resource
def raeume() -> Raeume:
    """Alle Spielräume, gemeinsam für alle Sitzungen des Prozesses."""
    return Raeume(engine=lade_engine)


def wuerfel_html(fest, neu=()) -> str:
    """Würfelbilder; liegen gelassene Würfel werden blasser dargestellt."""
    teile = [f'<span class="fest">{AUGEN[w]}</span>' for w in fest]
    teile += [AUGEN[w] for w in neu]
    return f'<div class="wuerfel">{"".join(teile)}</div>'


def prozent(x: float) -> str:
    return f"{x * 100:.0f} %"


def wuerfel_tabelle(wuerfel, option) -> None:
    """Was mit jedem Würfel passiert, in der Reihenfolge von `wuerfel`."""
    st.table(
        {
            "Würfel": [f"{AUGEN[w]} {w}" for w in wuerfel],
            "Empfehlung": [AKTION_BADGE[a] for a in wuerfel_aktionen(wuerfel, option)],
        },
        hide_index=True,
        alt="Empfohlene Aktion pro Würfel",
    )


def optionstabelle(emp) -> None:
    """Pro Option die Chance, nicht zu verlieren, und die kumulativen Kategorie-Chancen."""
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


def optionsknoepfe(optionen, on_click, *args, emp=None) -> None:
    """Ein Knopf pro Option, Aufruf: on_click(option, *args).
    Mit `emp` (Tipp): sortiert nach Empfehlung, mit Chance, die beste hervorgehoben."""
    nutzen = {}
    if emp is not None:
        optionen = [b.option for b in emp.optionen]
        nutzen = {b.option: b.nutzen for b in emp.optionen}
    for o in optionen:
        st.button(
            f"{o.text} · {prozent(nutzen[o])}" if nutzen else o.text,
            key=f"opt_{o.aktion}_{o.neu_fest}",
            type="primary" if emp is not None and o == emp.beste.option else "secondary",
            width="stretch",
            on_click=on_click,
            args=(o, *args),
        )
