"""Normalizador textual estricto del Rosco (Regla 5).

Toda comparación de respuestas pasa por aquí: permite que "kog'maw" (o "Kog'Maw", o "KOG MAW"),
"Xin Zhao", "xin zhao" y "xinzhao" golpeen siempre a la misma forma canónica, sin depender de
mayúsculas, tildes, espacios ni puntuación.

El resultado es alfanumérico puro en minúsculas (a-z, 0-9), pegada y sin separadores:
    "Kog'Maw"        -> "kogmaw"
    "Nunu & Willump" -> "nunuwillump"
    "Xin Zhao"       -> "xinzhao"
    "K'Sante"        -> "ksante"

Tres pasos:
  1. minúsculas.
  2. NFD + descarte de combining marks (á/a, é/e, ñ/n).
  3. Una sola regex: fuera TODO lo que no sea [a-z0-9] (espacios, apóstrofos, guiones,
     ampersands y cualquier puntuación). No hace falta abrir separadores "permitidos" en una
     segunda pasada: la comparación canónica pega la respuesta directamente.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_answer(text: str) -> str:
    """Normaliza una respuesta a la forma canónica de comparación del Rosco.

    1. minúsculas
    2. NFD + descarte de combining marks (á/a, é/e, ñ/n)
    3. regex única: fuera lo que no sea alfanumérico — espacios, apóstrofos, guiones,
       ampersands y puntuación dura desaparecen todos por igual ("Xin Zhao" == "xinzhao")
    """
    lowered = unicodedata.normalize("NFD", text.lower())
    accent_free = "".join(ch for ch in lowered if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", accent_free)