-- 014_user_settings_riot.sql — v2.1 (P0): el Riot ID y la región pasan a ser por usuario.
--
-- Hasta ahora el sync leía `RIOT_ID`/`RIOT_REGION` del .env (Settings global), una
-- asunción mono-usuario que no sobrevive a la v2.0 multi-tenant. A partir de esta migración
-- la vinculación de la cuenta Riot vive en la fila de `user_settings` de cada usuario:
--
--   * `riot_id`     VARCHAR  NULL      — 'Nombre#TAG'. NULL = el usuario aún no vinculó.
--   * `riot_region` VARCHAR  NOT NULL  — plataforma Riot (normalizado a mayúsculas al usarse).
--                                        Default 'euw1' (clave de ROUTING_MAP es 'EUW1').
--
-- El backend normaliza la región a mayúsculas en lectura (ROUTING_MAP usa claves en
-- mayúsculas: 'EUW1', 'LA1'...). Las columnas nuevas caen dentro del RLS existente
-- (`user_isolation_user_settings`): la política es a nivel de fila, no de columna.
--
-- Es un ALTER aditivo: la DB existente no necesita truncar nada (a diferencia de 013).
ALTER TABLE user_settings
    ADD COLUMN riot_id VARCHAR NULL,
    ADD COLUMN riot_region VARCHAR NOT NULL DEFAULT 'euw1';