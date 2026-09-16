"""Regla 5 del Rosco: normalizador textual estricto (`normalize_answer`).

Dos respuestas escritas de forma distinta deben colisionar en la misma forma canónica:
"Kog'Maw" == "kogmaw", "Nunu & Willump" == "nunuwillump". El test fija el comportamiento de los
dos ejemplos canónicos de la regla más un caso de diacríticos y otro de puntuación dura.
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
    ],
)
def test_normalize_answer_canonica(raw: str, expected: str) -> None:
    assert normalize_answer(raw) == expected