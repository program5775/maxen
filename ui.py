"""Gemeinsame UI-Teile für Assistent und Spielseite."""
import base64

import streamlit as st

from maxen import Engine, wuerfel_aktionen
from maxen.raum import Raeume
from maxen.regeln import MAX, PASCH, STRASSE

AUGEN = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
GRUEN = "#22a559"
BLAU = "#1c83e1"
# Neu gewürfelter Würfel als Kästchen mit „?“, wie die verdeckten Würfe (`verdeckt`). In Knöpfen geht
# kein HTML, dort steht es als SVG-Bild (grau, passt zu hellem und dunklem Design)
_FRAGE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><rect x="1.5" y="1.5" width="17" '
              'height="17" rx="3" fill="none" stroke="#808495" stroke-width="2"/><text x="10" y="15" '
              'font-size="13" font-weight="700" text-anchor="middle" fill="#808495" font-family="sans-serif">?</text></svg>')
NEU_MD = f"![neu](data:image/svg+xml;base64,{base64.b64encode(_FRAGE_SVG.encode()).decode()})"

STIL = f"""
<style>
/* Platz für die Kopfleiste (3,75rem), sonst wird die erste Zeile verdeckt */
.block-container {{ padding-top: 2.5rem; }}
div[data-testid="stButtonGroup"] button {{
    min-height: 3.2rem; min-width: 3.2rem; font-size: 1.4rem; flex: 1 1 0;
}}
div[data-testid="stButton"] button {{ min-height: 3.2rem; }}
.st-key-stufe_wahl button {{ font-size: 1rem; padding-left: .25rem; padding-right: .25rem; }}
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

/* Assistent: Empfehlung direkt unter den Würfeln (liegen grün, neu blass, drehen blau) */
.empf {{ display: flex; gap: 1rem; margin: .2rem 0 .8rem; }}
.empf .ew {{ display: flex; flex-direction: column; align-items: center; }}
.empf .ew > span {{ font-size: 4.5rem; line-height: 1.05; }}
.empf .ew small {{ font-size: 1.05rem; font-weight: 600; white-space: nowrap; }}
.empf .liegen {{ color: {GRUEN}; }}
.empf .neu > span {{ opacity: .4; }}
.empf .drehen, .dreh {{ color: {BLAU}; }}
.legende {{ white-space: nowrap; }}
/* Status unter dem Schalter „Bildschirm anlassen“ (vom Skript gefüllt) */
.wach-status {{ font-size: .85rem; opacity: .7; margin-top: -.6rem; }}
.wach-status:empty {{ display: none; }}

/* Optionen als Piktogramme: groß genug, dass man sie am Handy lesen kann */
.st-key-optionen button p {{ font-size: 1.35rem; }}
/* Würfelsymbole sind in der Schrift klein; sie stehen als farbiger Text in eigenen Spans */
.st-key-optionen button .stMarkdownColoredText {{ font-size: 1.7em; line-height: 1; vertical-align: -.12em; }}
.st-key-optionen button p img {{ height: 1.45em; max-height: none; vertical-align: -.3em; margin: 0 .05em; }}
/* Empfohlene Option hellgrün mit grünem Rahmen statt voll in der Primärfarbe (grüne Würfel auf grünem
   Knopf wären kaum lesbar) */
.st-key-optionen button[kind="primary"] {{
    background: rgba(34, 165, 89, .15); border: 2px solid {GRUEN}; color: inherit;
}}
.st-key-optionen button[kind="primary"]:hover {{ background: rgba(34, 165, 89, .25); border-color: {GRUEN}; color: inherit; }}
table.maxen.optionen {{ font-size: 1rem; }}
table.maxen.optionen th, table.maxen.optionen td {{ padding-left: .25rem; padding-right: .25rem; }}
table.maxen.optionen td:not(:first-child), table.maxen.optionen th:not(:first-child) {{ text-align: right; }}
table.maxen.optionen td:not(:first-child) {{ white-space: nowrap; }}
table.maxen.optionen td .w, table.maxen.optionen td .q {{ font-size: 1.3em; }}
.tabelle-scroll {{ overflow-x: auto; }}

/* Eigener Wurf: Würfel antippen, die liegen bleiben (grün) */
.st-key-spiel_wuerfel button {{ min-height: 4.6rem; }}
.st-key-spiel_wuerfel button * {{ font-size: 3.4rem; line-height: 1.1; }}
/* Ausgewählte Pills (react-aria, Attribut data-selected) färbt Streamlit in der Primärfarbe,
   daher !important. Grüne Würfel wie in der Tabelle und unter „Dein Wurf“, dazu ein grüner Rahmen */
.st-key-spiel_wuerfel button[data-selected],
.st-key-spiel_wuerfel button[data-selected]:hover,
.st-key-spiel_wuerfel button[data-selected]:focus {{
    background: rgba(34, 165, 89, .12) !important; border: 2px solid {GRUEN} !important; color: {GRUEN} !important;
}}
.st-key-spiel_wuerfel button[data-selected] * {{ color: {GRUEN} !important; }}
</style>
"""


WACH_JS = """<div class="wach-status"></div><script>
// Bildschirm anlassen (Screen Wake Lock API). Der Browser gibt die Sperre frei, sobald die Seite
// nicht sichtbar ist (Tab gewechselt, Handy gesperrt); beim Zurückkehren wird sie neu angefordert.
// Manche Browser erlauben sie erst nach einer Berührung, und im Energiesparmodus lehnen sie ab:
// Solange keine Sperre besteht, wird es bei jedem Tippen erneut versucht. Der Status steht unter dem
// Schalter, damit man am Handy sieht, was passiert. Läuft bei jeder Änderung des Schalters erneut,
// die Listener werden nur einmal registriert.
(() => {
  const w = window;
  w.maxenWach = __AN__;
  const status = (text) => {
    w.maxenWachStatus = text;
    document.querySelectorAll(".wach-status").forEach((e) => { e.textContent = w.maxenWach ? text : ""; });
  };
  // Ohne HTTPS (z. B. lokal über http://192.168…) blenden Browser die API ganz aus; localhost zählt als sicher
  if (!isSecureContext) { status("Geht nur über HTTPS, nicht über http://."); return; }
  if (!("wakeLock" in navigator)) { status("Kann dieser Browser leider nicht."); return; }
  w.maxenWachAnfordern ??= async () => {
    if (!w.maxenWach || w.maxenWachLaeuft || document.visibilityState !== "visible") return;
    if (w.maxenSperre && !w.maxenSperre.released) return;
    w.maxenWachLaeuft = true;
    try {
      const sperre = await navigator.wakeLock.request("screen");
      w.maxenSperre = sperre;
      status("Aktiv.");
      sperre.addEventListener("release", () => status("Freigegeben, wird beim nächsten Tippen erneuert."));
    } catch (e) {
      status(`Abgelehnt (${e.name}${e.message ? ": " + e.message : ""}). Wird beim nächsten Tippen erneut versucht.`);
    } finally {
      w.maxenWachLaeuft = false;
    }
  };
  if (!w.maxenWachListener) {
    w.maxenWachListener = true;
    document.addEventListener("visibilitychange", () => w.maxenWachAnfordern());
    document.addEventListener("pointerup", () => w.maxenWachAnfordern(), true);
  }
  status(w.maxenWachStatus || "Wird angefordert …");
  if (w.maxenWach) w.maxenWachAnfordern();
  else if (w.maxenSperre) { w.maxenSperre.release(); w.maxenSperre = null; w.maxenWachStatus = ""; }
})();
</script>"""


def bildschirm_anlassen(an: bool) -> None:
    """Hält den Bildschirm des Handys an, solange die Seite sichtbar ist (wenn der Browser es kann).
    JavaScript muss direkt in der Seite laufen, nicht im iframe von `st.components.v1.html`."""
    st.html(WACH_JS.replace("__AN__", "true" if an else "false"), unsafe_allow_javascript=True)


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


def tabelle_html(kopf: list[str], zeilen: list[dict], klasse: str = "maxen") -> str:
    """HTML-Tabelle; Zellen sind fertiges HTML. Zeilen mit `_am_zug` werden hervorgehoben,
    ebenso `_klasse` (CSS-Klasse der Zeile, z. B. „bester“ oder „verlierer“)."""
    th = "".join(f"<th>{k}</th>" for k in kopf)
    tr = "".join(
        ('<tr class="am-zug">' if z.get("_am_zug") else f'<tr class="{z["_klasse"]}">' if z.get("_klasse") else "<tr>")
        + "".join(f"<td>{z[k]}</td>" for k in kopf) + "</tr>"
        for z in zeilen
    )
    return f'<table class="{klasse}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def prozent(x: float) -> str:
    return f"{x * 100:.0f} %"


def option_teile(option, wurf) -> tuple[int, tuple[int, ...], int]:
    """(gedrehte Sechsen, liegen gelassene Würfel ohne die gedrehten 1en, neu gewürfelte Würfel).
    Gedreht werden 6,6 -> 1 oder 6,6,6 -> 1,1; ohne Drehen ist die erste Zahl 0."""
    liegen = list(option.neu_fest)
    zu_eins = 0
    if option.aktion == "drehen":
        zu_eins = 2 if tuple(wurf).count(6) == 3 and option.neu_fest == (1, 1) else 1
        for _ in range(zu_eins):
            liegen.remove(1)
    return (zu_eins + 1 if zu_eins else 0), tuple(sorted(liegen, reverse=True)), option.neu_wuerfeln


def option_md(option, wurf) -> str:
    """Option als Piktogramm für Knöpfe (Markdown): liegen gelassene Würfel grün, je neu
    gewürfeltem Würfel ein Kästchen mit „?“, Drehen blau als ⚅⚅→⚀. Klopfen als Wort."""
    if option.aktion == "klopfen":
        return "Klopfen"
    sechsen, liegen, neu = option_teile(option, wurf)
    teile = []
    if sechsen:
        teile.append(f":blue[{AUGEN[6] * sechsen}→{AUGEN[1] * (sechsen - 1)}]")
    if liegen:
        teile.append(f":green[{''.join(AUGEN[w] for w in liegen)}]")
    if neu:
        teile.append(NEU_MD * neu)
    return " ".join(teile)


def option_html(option, wurf) -> str:
    """Wie `option_md`, als HTML für Tabellen."""
    if option.aktion == "klopfen":
        return "Klopfen"
    sechsen, liegen, neu = option_teile(option, wurf)
    # Leerzeichen zwischen den Gruppen, damit lange Optionen in der Tabelle umbrechen können
    teile = [f'<span class="dreh">{augen((6,) * sechsen)}→{augen((1,) * (sechsen - 1))}</span>' if sechsen else "",
             augen(liegen, liegt=True), verdeckt(neu)]
    return " ".join(t for t in teile if t)


LEGENDE = (f'<span class="legende"><span class="w liegt">{AUGEN[6]}</span> liegen lassen · {verdeckt(1)} neu würfeln · '
           f'<span class="dreh"><span class="w">{AUGEN[6]}{AUGEN[6]}</span>→<span class="w">{AUGEN[1]}</span></span>'
           ' drehen</span>')


def empfehlung_html(wuerfel, option) -> str:
    """Große Würfel in der Reihenfolge von `wuerfel`, darunter, was mit jedem passiert:
    liegen lassen (grün), neu würfeln (blass, „?“-Kästchen) oder auf die 1 drehen (blau, →⚀)."""
    if option.aktion == "klopfen":
        teile = [f'<div class="ew liegen"><span>{AUGEN[w]}</span></div>' for w in wuerfel]
        return f'<div class="empf">{"".join(teile)}</div>'
    beschriftung = {"liegen": "liegen", "neu": f"{verdeckt(1)} neu", "drehen": f"→ {AUGEN[1]}"}
    teile = [f'<div class="ew {a}"><span>{AUGEN[w]}</span><small>{beschriftung[a]}</small></div>'
             for w, a in zip(wuerfel, wuerfel_aktionen(wuerfel, option))]
    return f'<div class="empf">{"".join(teile)}</div>'


def optionstabelle(emp, wurf) -> None:
    """Pro Option die Chance, nicht zu verlieren, und die kumulativen Kategorie-Chancen.
    Als HTML-Tabelle mit Piktogrammen statt `st.dataframe`, weil dessen Schrift am Handy zu klein ist."""
    kopf = ["Option", "Nicht<br>verlieren", "≥ Max", "≥ Pasch", "≥ Straße"]
    zeilen = [
        {
            "Option": option_html(b.option, wurf),
            "Nicht<br>verlieren": f"<b>{prozent(b.nutzen)}</b>",
            "≥ Max": prozent(b.mindestens(MAX)),
            "≥ Pasch": prozent(b.mindestens(PASCH)),
            "≥ Straße": prozent(b.mindestens(STRASSE)),
            "_klasse": "bester" if b is emp.beste else "",
        }
        for b in emp.optionen
    ]
    st.markdown(f'<div class="tabelle-scroll">{tabelle_html(kopf, zeilen, klasse="maxen optionen")}</div>',
                unsafe_allow_html=True)
    st.caption("„≥“ bedeutet: diese Kategorie oder besser, bei optimalem Weiterspiel. "
               "Die Empfehlung maximiert die Chance, nicht zu verlieren – nicht die Chance auf eine bestimmte Kategorie.")


def optionsknoepfe(emp, wurf, on_click, *args) -> None:
    """Ein Knopf pro Option als Piktogramm mit Chance, sortiert nach Empfehlung, die beste
    hervorgehoben. Aufruf: on_click(option, *args)."""
    with st.container(key="optionen"):
        for b in emp.optionen:
            o = b.option
            st.button(
                f"{option_md(o, wurf)} · {prozent(b.nutzen)}",
                key=f"opt_{o.aktion}_{o.neu_fest}",
                type="primary" if b is emp.beste else "secondary",
                icon=":material/front_hand:" if o.aktion == "klopfen" else None,
                width="stretch",
                on_click=on_click,
                args=(o, *args),
            )
