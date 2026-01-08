from database import MatchDatabase
from datetime import datetime

db = MatchDatabase()

print("🔮 Simulando que vuelves a jugar el mismo matchup...")

# Creamos una partida NUEVA (ID distinto) pero con los MISMOS campeones
# Ashe (Tú) vs Lucian (Enemigo)
fake_rematch = {
    'game_id': 'TEST_MATCHUP_REMATCH_001',
    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'champion_name': 'Ashe',       # <--- Mismo champ
    'role': 'ADC',
    'kills': 10, 'deaths': 2, 'assists': 15,
    'cs_total': 220, 'game_duration_minutes': 35,
    'control_wards_bought': 3,
    'win': True,                   # ¡Esta vez ganamos!
    'enemy_champion': 'Lucian'     # <--- Mismo enemigo
}

# La guardamos directament en la DB para simular que la API la bajó
if db.save_match(fake_rematch):
    print("✅ Partida de revancha guardada.")
    print("👉 Ahora ve a la App, dale a F5 (Recargar) y mira si aparece la alerta azul.")
else:
    print("⚠️ Error: La partida ya existía.")

db.close()