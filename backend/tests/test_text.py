"""Regla 5 del Rosco: normalizador textual estricto (`normalize_answer`).

Dos respuestas escritas de forma distinta deben colisionar en la misma forma canónica:
"Kog'Maw" == "kogmaw", "Nunu & Willump" == "nunuwillump", "Xin Zhao" == "xinzhao". El test fija
el comportamiento de los ejemplos canónicos de la regla, nombres con espacios (Xin Zhao) y
apóstrofos difíciles (K'Sante), más casos de diacríticos y puntuación dura.
"""

from __future__ import annotations

import pytest

from backend.app.utils.text import normalize_answer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Kog'Maw", "kogmaw"),  # apóstrofo: el separador se compacta
        ("Nunu & Willump", "nunuwillump"),  # espacios y ampersand desaparecen
        ("Áhri", "ahri"),  # diacríticos fuera
        ("Dr. Mundo!", "drmundo"),  # punto y exclamación fuera
        ("Xin Zhao", "xinzhao"),  # espacios entre nombres propios (Regla 5)
        ("xin zhao", "xinzhao"),  # minúsculas + espacios → misma forma pegada
        ("K'Sante", "ksante"),  # apóstrofo dentro del nombre se pega
        ("  Master   Yi ", "masteryi"),  # espacios extra a los lados y en medio
    ],
)
def test_normalize_answer_canonica(raw: str, expected: str) -> None:
    assert normalize_answer(raw) == expected