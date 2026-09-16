"""Normalizador textual estricto del Rosco (Regla 5).

Toda comparación de respuestas pasa por aquí: permite que "kog'maw" (o "Kog'Maw", o "KOG MAW")
golpee siempre a la misma forma canónica, sin depender de mayúsculas, tildes ni puntuación.

El resultado es alfanumérico puro en minúsculas (a-z, 0-9) y sin separadores:
    "Kog'Maw"        -> "kogmaw"
    "Nunu & Willump" -> "nunuwillump"

Dos pasadas de regex:
  1. Fuera TODO lo que no sea alfanumérico, espacio, apóstrofo, guion o ampersand (la
     puntuación dura — puntos, comas, barras, signos — no debe sobrevivir).
  2. Fuera los separadores que sí pasaron la primera (espacio, apóstrofo, guion, ampersand),
     compactando la respuesta a su forma pegada para la comparación.
"""

from __future__ import annotations

import re
import unicodedata

# Primera pasada: caracteres no alfanuméricos fuera, salvo separadores permitidos.
_STRIP_PUNCTUATION = re.compile(r"[^a-z0-9\s'&-]+")

# Segunda pasada: los separadores permitidos se eliminan para comparar en forma compacta.
_STRIP_SEPARATORS = re.compile(r"[\s'&-]+")


def normalize_answer(text: str) -> str:
    """Normaliza una respuesta a la forma canónica de comparación del Rosco.

    1. minúsculas
    2. NFD + descarte de combining marks (á/a, é/e, ñ/n)
    3. regex: fuera lo que no sea alfanumérico/separador
    4. regex: fuera los separadores (espacios, apóstrofos, guiones, ampersands)
    """
    lowered = unicodedata.normalize("NFD", text.lower())
    accent_free = "".join(ch for ch in lowered if unicodedata.category(ch) != "Mn")
    kept = _STRIP_PUNCTUATION.sub("", accent_free)
    return _STRIP_SEPARATORS.sub("", kept)