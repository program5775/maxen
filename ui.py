"""Gemeinsame UI-Teile für Assistent und Spielseite."""
import re

import streamlit as st

from maxen import Engine, wuerfel_aktionen
from maxen.raum import Raeume
from maxen.regeln import MAX, PASCH, STRASSE

AUGEN = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
GRUEN = "#22a559"

STIL = f"""
<style>
/* Platz für die Kopfleiste (3,75rem), sonst wird die erste Zeile verdeckt */
.block-container {{ padding-top: 2.5rem; }}
div[data-testid="stButtonGroup"] button {{
    min-height: 3.2rem; min-width: 3.2rem; font-size: 1.4rem; flex: 1 1 0;
}}
div[data-testid="stButton"] button {{ min-height: 3.2rem; }}
.wuerfel {{ font-size: 4.5rem; line-height: 1.1; letter-spacing: .4rem; }}
.wuerfel .fest {{ opacity: .5; }}
.wuerfel .w, .wuerfel .q {{ font-size: 1em; }}

/* Würfelsymbole im Text: liegen gelassene grün, verdeckte als Kästchen mit „?“ */
.w {{ font-size: 1.6em; line-height: 1; vertical-align: -.12em; }}
.w.liegt {{ color: {GRUEN}; }}
.q {{
    display: inline-block; position: relative; box-sizing: border-box; font-size: 1.6em;
    width: .8em; height: .8em; margin: 0 .06em; vertical-align: -.08em;
    border: .08em solid currentColor; border-radius: .15em; opacity: .6;
}}
.q::after {{
    content: "?"; position: absolute; inset: 0; display: flex; align-items: center;
    justify-content: center; font-size: .55em; font-weight: 700; letter-spacing: 0;
}}
.schritt {{ white-space: nowrap; }}

/* Tabelle des Durchgangs */
table.maxen {{ width: 100%; border-collapse: collapse; font-size: .95rem; margin-bottom: .4rem; }}
table.maxen th {{ text-align: left; font-weight: 600; font-size: .8rem; opacity: .7; }}
table.maxen th, table.maxen td {{
    padding: .3rem .35rem; border-bottom: 1px solid rgba(128, 128, 128, .25); vertical-align: middle;
}}
table.maxen tr.am-zug td {{ background: rgba(34, 165, 89, .12); }}
table.maxen tr.bester td {{ background: rgba(34, 165, 89, .15); }}
table.maxen tr.verlierer td {{ background: rgba(220, 53, 69, .15); }}
/* Schmal fürs Handy: Würfe als zweite Zeile unter dem Namen, Bricken und Ergebnis rechts daneben */
table.maxen .wuerfe {{ margin-top: .15rem; line-height: 1.5; }}
table.maxen .wuerfe .w, table.maxen .wuerfe .q {{ font-size: 1.35em; }}
table.maxen th:nth-child(2), table.maxen td:nth-child(2) {{ text-align: center; white-space: nowrap; }}
table.maxen td:nth-child(3) {{ white-space: nowrap; }}
.mehr {{ color: #e5484d; }}
.weniger {{ color: {GRUEN}; }}

/* Assistent: Augen als Würfelsymbole eingeben (6 nebeneinander, muss am Handy in eine Zeile passen) */
.st-key-assistent_wuerfel button {{ padding-left: 0; padding-right: 0; }}
.st-key-assistent_wuerfel button * {{ font-size: 2.4rem; line-height: 1.1; }}

/* Eigener Wurf: Würfel antippen, die liegen bleiben (grün) */
.st-key-spiel_wuerfel button {{ min-height: 4.6rem; }}
.st-key-spiel_wuerfel button * {{ font-size: 3.4rem; line-height: 1.1; }}
/* Ausgewählte Pills (react-aria, Attribut data-selected) färbt Streamlit in der Primärfarbe rot,
   daher !important. Grüne Würfel wie in der Tabelle und unter „Dein Wurf“, dazu ein grüner Rahmen */
.st-key-spiel_wuerfel button[data-selected],
.st-key-spiel_wuerfel button[data-selected]:hover,
.st-key-spiel_wuerfel button[data-selected]:focus {{
    background: rgba(34, 165, 89, .12) !important; border: 2px solid {GRUEN} !important; color: {GRUEN} !important;
}}
.st-key-spiel_wuerfel button[data-selected] * {{ color: {GRUEN} !important; }}
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


def augen(werte, liegt: bool = False) -> str:
    """Würfelsymbole als HTML, absteigend; `liegt`: liegen gelassene Würfel (grün)."""
    k = "w liegt" if liegt else "w"
    return "".join(f'<span class="{k}">{AUGEN[x]}</span>' for x in sorted(werte, reverse=True))


def dreh_text(option) -> str:
    """Optionstext mit Würfelsymbolen statt Zahlen, z. B. „⚅ ⚅ zu ⚀ drehen, ⚀ liegen lassen und
    1 Würfel neu“. Anzahlen („1 Würfel neu“) bleiben Zahlen."""
    text = re.sub(r"[1-6](?:,[1-6])*(?! Würfel)",
                  lambda m: " ".join(AUGEN[int(x)] for x in m.group().split(",")), option.text)
    return re.sub(r", (\d Würfel neu)$", r" und \1", text)


def verdeckt(anzahl: int) -> str:
    return '<span class="q"></span>' * anzahl


def schritte_html(z, alles: bool = False) -> str:
    """Alle Würfe eines Zugs: liegen gelassene Würfel grün, dahinter die neu gewürfelten,
    verdeckte als „?“. Mit `alles` (nach dem Durchgang) ist nichts mehr verdeckt.
    Auch die eigenen verdeckten Würfe bleiben verdeckt, wie unter dem Becher."""
    sichtbar = len(z.schritte) if alles else z.sichtbar
    teile = []
    for k, sch in enumerate(z.schritte):
        teil = augen(sch.fest, liegt=True) + (augen(sch.neu) if k < sichtbar else verdeckt(len(sch.neu)))
        teile.append(f'<span class="schritt">{"🔄" if sch.gedreht else ""}{teil}</span>')
    return " → ".join(teile)


def ergebnis_html(z, alles: bool = False) -> str:
    """Aufgedeckt: immer die Würfel, kein Kategoriename (vom Nutzer gewünscht).
    Verdeckt: was liegt und „?“ für die neu gewürfelten Würfel, z. B. ⚀⚀?."""
    if z.wurf is None:
        return "–"
    if alles or z.aufgedeckt:
        return augen(z.wurf)
    sch = z.schritte[-1]
    return augen(sch.fest, liegt=True) + verdeckt(len(sch.neu))


def tabelle_html(kopf: list[str], zeilen: list[dict]) -> str:
    """HTML-Tabelle; Zellen sind fertiges HTML. Zeilen mit `_am_zug` werden hervorgehoben,
    ebenso `_klasse` (CSS-Klasse der Zeile, z. B. „bester“ oder „verlierer“)."""
    th = "".join(f"<th>{k}</th>" for k in kopf)
    tr = "".join(
        ('<tr class="am-zug">' if z.get("_am_zug") else f'<tr class="{z["_klasse"]}">' if z.get("_klasse") else "<tr>")
        + "".join(f"<td>{z[k]}</td>" for k in kopf) + "</tr>"
        for z in zeilen
    )
    return f'<table class="maxen"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


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
