"""Einstiegspunkt der Maxen-App: Navigation zwischen Spiel (Startseite) und Assistent.

Start: streamlit run app.py
"""
import streamlit as st

from ui import STIL, bildschirm_anlassen

st.set_page_config(page_title="Maxen", page_icon="🎲", layout="centered", initial_sidebar_state="collapsed")
st.markdown(STIL, unsafe_allow_html=True)

seite = st.navigation(
    [
        st.Page("app_pages/spiel.py", title="Spielen", icon=":material/casino:", default=True),
        st.Page("app_pages/assistent.py", title="Assistent", icon=":material/lightbulb:"),
        st.Page("app_pages/regeln.py", title="Regeln", icon=":material/menu_book:"),
    ],
    position="top",
)
# Am Handy klappt die Navigation oben in das Seitenmenü; der Schalter steht dort unter „Regeln“
with st.sidebar:
    st.toggle("Bildschirm anlassen", key="wach", value=True,
              help="Verhindert, dass sich der Bildschirm während des Spiels ausschaltet (wenn der Browser das kann).")
    bildschirm_anlassen(st.session_state.wach)
seite.run()
