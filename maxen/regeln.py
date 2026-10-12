"""Spielregeln für „Maxen": Bewertung und Rangfolge von Würfen.

Ein Wurf ist immer ein Tupel aus drei Würfelwerten (1–6). Die Bewertung liefert
einen sortierbaren Schlüssel: größerer Schlüssel = besserer Wurf.
"""
from itertools import combinations_with_replacement

# Kategorie-Index (höher = besser)
NORMAL, STRASSE, PASCH, MAX, GENERAL = range(5)
KATEGORIE_NAMEN = {
    GENERAL: "General",
    MAX: "Max",
    PASCH: "Pasch",
    STRASSE: "Straße",
    NORMAL: "Normal",
}

Wurf = tuple[int, int, int]
Schluessel = tuple[int, int]


def bewerte(wurf) -> Schluessel:
    """Liefert (Kategorie, Wert) – Tupelvergleich ergibt die Rangfolge."""
    if len(wurf) != 3 or any(not 1 <= w <= 6 for w in wurf):
        raise ValueError(f"Ungültiger Wurf: {wurf}")
    c, b, a = sorted(wurf)  # a >= b >= c
    if (a, b, c) == (1, 1, 1):
        return (GENERAL, 0)
    if b == 1 and c == 1:
        return (MAX, a)
    if a == b == c:
        return (PASCH, a)
    if a - b == 1 and b - c == 1:
        return (STRASSE, a)
    return (NORMAL, 100 * a + 10 * b + c)


def name(schluessel: Schluessel) -> str:
    kat, wert = schluessel
    if kat == GENERAL:
        return "General"
    if kat == MAX:
        return f"Max {wert}"
    if kat == PASCH:
        return f"{wert}er Pasch"
    if kat == STRASSE:
        return f"Straße {wert}"
    return str(wert)


def wurf_name(wurf) -> str:
    return name(bewerte(wurf))


# Alle 56 unterscheidbaren Würfe, sortiert vom besten zum schlechtesten
ALLE_WUERFE: list[Wurf] = sorted(
    combinations_with_replacement(range(1, 7), 3), key=bewerte, reverse=True
)

# Rang 1 = General; gleichwertige Würfe teilen sich einen Rang
_schluessel_absteigend = sorted({bewerte(w) for w in ALLE_WUERFE}, reverse=True)
RANG: dict[Schluessel, int] = {s: i + 1 for i, s in enumerate(_schluessel_absteigend)}


def rang(wurf) -> int:
    return RANG[bewerte(wurf)]


def vergleiche(a, b) -> int:
    """>0 wenn a besser als b, <0 wenn schlechter, 0 bei Gleichstand."""
    sa, sb = bewerte(a), bewerte(b)
    return (sa > sb) - (sa < sb)
