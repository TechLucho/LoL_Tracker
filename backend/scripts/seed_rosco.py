"""Semilla del banco del Rosco: 26 preguntas básicas de LoL (A-Z).

    python -m backend.scripts.seed_rosco

Inyecta el catálogo estático de preguntas para testeos locales (respuestas = campeones de la
A a la Z). Idempotente: `ON CONFLICT (letter) DO NOTHING` — con la UNIQUE de la migración 015
ejecutarlo N veces nunca duplica filas.

El reglamento de comparación vive en backend/app/utils/text.py (Regla 5): las respuestas del
catálogo son nombres canónicos de campeón ("Master Yi", "Nunu & Willump") y el normalizador
las convierte a su forma pegada antes de compararlas contra lo que escriba el jugador.
"""

from __future__ import annotations

import logging
import sys

import psycopg
from dotenv import load_dotenv

from backend.scripts.migrate import _dsn_from_env

load_dotenv()

log = logging.getLogger("seed_rosco")

# (letter, question_text, answer, category)
QUESTIONS = [
    ("A", "¿Qué campeón ascendido de Shurima es 'El Destructor de Mundos'?", "Aatrox", "Lore"),
    ("B", "¿Qué guardián errante colecciona campanas y cura aliados con sus meeps?", "Bard", "Lore"),
    ("C", "¿Qué alguacil francotiradora vigila las calles de Piltover?", "Caitlyn", "Lore"),
    ("D", "¿Qué Campeón de Noxus, 'La Mano', ejecuta con 'Guillotina Noxiana'?", "Darius", "Mecánicas"),
    ("E", "¿Qué demonio de las Islas de la Sombra caza con encanto y latigazo?", "Evelynn", "Lore"),
    ("F", "¿Qué Gran Duelista de Demacia usa 'Riposta' para devolver paradas?", "Fiora", "Mecánicas"),
    ("G", "¿Qué paladín de Demacia, hermano de Lux, gira con 'Juicio'?", "Garen", "Mecánicas"),
    ("H", "¿Qué inventor yordle de Piltover despliega torretas y granadas?", "Heimerdinger", "Jugabilidad"),
    ("I", "¿Qué Dama de las Cuchillas lidera la resistencia de Ionia contra Noxus?", "Irelia", "Lore"),
    ("J", "¿Qué maníaca de Zaun disparó su cohete contra el Consejo de Piltover?", "Jinx", "Lore"),
    ("K", "¿Qué asesina de Noxus gira sus dagas en 'Death Lotus'?", "Katarina", "Mecánicas"),
    ("L", "¿Qué Dama de la Luz de Demacia lanza 'Chispa Final' con su báculo?", "Lux", "Mecánicas"),
    ("M", "¿Qué maestro Wuju de Ionia medita y corta con 'Golpe Wuju'?", "Master Yi", "Jugabilidad"),
    ("N", "¿Qué semidiós de Shurima recolecta minions para hacer crecer su bastón?", "Nasus", "Lore"),
    ("O", "¿Qué autómata de Piltover baila y controla su bola por toda la Grieta?", "Orianna", "Jugabilidad"),
    ("P", "¿Qué yordle empuña el martillo de Orlon, aunque dice no ser la heroína?", "Poppy", "Lore"),
    ("Q", "¿Qué exploradora de Demacia vuela en dupla con su águila Valor?", "Quinn", "Lore"),
    ("R", "¿Qué espadachina exiliada de Noxus partió su espada rúnica?", "Riven", "Lore"),
    ("S", "¿Qué Soberana Oscura de Ionia lanza orbes de energía oscura?", "Syndra", "Lore"),
    ("T", "¿Qué carcelero de las Islas de la Sombra arrastra con su 'Sentencia'?", "Thresh", "Mecánicas"),
    ("U", "¿Qué cabezón escopeta de Noxus ejecuta a los débiles con su ulti?", "Urgot", "Mecánicas"),
    ("V", "¿Qué cazadora nocturna persigue monstruos con 'Tumble' y 'Hora Final'?", "Vayne", "Mecánicas"),
    ("W", "¿Qué bestia de Zaun, creada por Singed, se enfurece al oler sangre?", "Warwick", "Lore"),
    ("X", "¿Qué Ascendente de pura energía fue encerrado en un sarcófago de Shurima?", "Xerath", "Lore"),
    ("Y", "¿Qué espadachín de Ionia, 'El Imperdonable', domina el viento con su espada?", "Yasuo", "Lore"),
    ("Z", "¿Qué maestro de las sombras de Ionia firma con 'Marca de la muerte'?", "Zed", "Lore"),
]

_INSERT_SQL = """
INSERT INTO rosco_questions (letter, question_text, answer, category)
VALUES (%s, %s, %s, %s)
ON CONFLICT (letter) DO NOTHING
"""


def seed(dsn: str | None = None) -> int:
    """Inserta las 26 preguntas y devuelve cuántas filas nuevas entraron realmente."""
    if dsn is None:
        dsn = _dsn_from_env()
    with psycopg.connect(dsn) as conn:
        cur = conn.cursor()
        cur.executemany(_INSERT_SQL, QUESTIONS)
        inserted = cur.rowcount
        conn.commit()
    log.info("Preguntas insertadas: %d (de %d definidas)", inserted, len(QUESTIONS))
    return inserted


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    try:
        seed()
    except psycopg.OperationalError as exc:
        log.error("No se pudo conectar a la base de datos: %s", exc)
        return 1
    except Exception:  # noqa: BLE001
        log.exception("No se pudo sembrar el banco de preguntas")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())