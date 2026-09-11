-- 009_user_settings_okrs.sql — objetivos adicionales de rendimiento en user_settings.
-- Alimenta la configuración de OKRs en la vista Settings:
--   target_dpm         = meta de Daño Por Minuto
--   target_kp_percent  = meta de Kill Participation (%)
--   target_vision_score= meta de Vision Score por partida
-- Legacy: filas existentes sin estas columnas obtienen los defaults razonables.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'target_dpm'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN target_dpm         INTEGER NOT NULL DEFAULT 500;
        ALTER TABLE user_settings ADD COLUMN target_kp_percent  INTEGER NOT NULL DEFAULT 50;
        ALTER TABLE user_settings ADD COLUMN target_vision_score INTEGER NOT NULL DEFAULT 20;
        RAISE NOTICE 'Columnas target_dpm, target_kp_percent, target_vision_score añadidas';
    ELSE
        RAISE NOTICE 'Columnas de OKR ya existen, nada que hacer';
    END IF;
END $$;
