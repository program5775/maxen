"""Einstiegspunkt der Maxen-App: Navigation zwischen Assistent und Spiel.

Start: streamlit run app.py
"""
import streamlit as st

from ui import STIL

st.set_page_config(page_title="Maxen", page_icon="🎲", layout="centered")
st.markdown(STIL, unsafe_allow_html=True)

seite = st.navigation(
    [
        st.Page("app_pages/assistent.py", title="Assistent", icon=":material/lightbulb:", default=True),
        st.Page("app_pages/spiel.py", title="Spielen", icon=":material/casino:"),
    ],
    position="top",
)
seite.run()
