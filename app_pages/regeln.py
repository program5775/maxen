"""Seite „Regeln“: zeigt die README (ohne den Abschnitt zum lokalen Starten)."""
from pathlib import Path

import streamlit as st

text = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
st.markdown(text.split("## Lokal starten")[0])
