-- 003_user_settings.sql — persistencia de la configuración del usuario.
--
-- PROBLEMA: el champion pool ("Jax, Fiora, Camille") y los OKRs (meta de CS/min, tope de muertes)
-- vivían hardcodeados en widgets de Streamlit. Cualquier cambio se perdía al recargar, así que
-- "La Constitución" —el conjunto de reglas que el usuario se impone— no sobrevivía a una sesión.
--
-- DISEÑO: una única fila, forzada por CHECK (id = 1). Es una app mono-usuario: una tabla
-- key/value genérica sería más flexible pero perdería la validación de tipos y rangos, que aquí
-- es justo lo que interesa (un tope de muertes negativo no debe poder existir).

CREATE TABLE IF NOT EXISTS user_settings (
    id            SMALLINT    PRIMARY KEY DEFAULT 1,

    -- Champion pool. TEXT[] en vez de una cadena separada por comas: el parseo con `split(',')`
    -- es exactamente lo que producía entradas vacías y falsas alarmas de "fuera de pool".
    champion_pool TEXT[]      NOT NULL DEFAULT ARRAY['Jax', 'Fiora', 'Camille'],

    -- OKRs del sprint.
    target_cs_min REAL        NOT NULL DEFAULT 7.5,
    max_deaths    REAL        NOT NULL DEFAULT 4.0,

    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT user_settings_single_row  CHECK (id = 1),
    CONSTRAINT user_settings_pool_size   CHECK (cardinality(champion_pool) <= 3),
    CONSTRAINT user_settings_cs_positive CHECK (target_cs_min > 0 AND target_cs_min <= 20),
    CONSTRAINT user_settings_deaths_pos  CHECK (max_deaths > 0 AND max_deaths <= 20)
);

-- Fila inicial con los valores que estaban hardcodeados en el sidebar, para que la migración no
-- cambie el comportamiento observable.
INSERT INTO user_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
