from database import MatchDatabase

db = MatchDatabase()

# Creamos una derrota falsa
fake_loss = {
    'game_id': 'SIMULATED_LOSS_002',
    'date': '2026-01-06 11:00:00',
    'champion_name': 'Ahri',
    'role': 'MID',
    'kills': 20, 'deaths': 7, 'assists': 5,
    'cs_total': 174, 'game_duration_minutes': 22, # Para calcular cs_min
    'control_wards_bought': 0,
    'win': False, # <--- DERROTA
    'enemy_champion': 'Syndra'
}

db.save_match(fake_loss)
print("Derrota simulada añadida. ¡Revisa tu App!")
db.close()