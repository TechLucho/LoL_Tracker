from database import MatchDatabase

# 1. Iniciamos la base de datos
db = MatchDatabase()
print("✅ Base de datos conectada.")

# 2. Creamos un dato falso que imita EXACTAMENTE lo que nos da Riot
fake_match = {
    'game_id': 'EUW1_TEST_001',          # ID único para el test
    'date': '2024-01-06 14:00:00',
    'champion_name': 'Jax',              # ANTES: 'champion' -> AHORA: 'champion_name'
    'role': 'TOP',
    'kills': 5,                          # ANTES: 'kill' -> AHORA: 'kills'
    'deaths': 2,                         # ANTES: 'death' -> AHORA: 'deaths'
    'assists': 10,                       # ANTES: 'assist' -> AHORA: 'assists'
    'cs_total': 200,
    'game_duration_minutes': 30,         # Necesario para calcular cs_min
    'control_wards_bought': 2,           # ANTES: 'control_wards' -> AHORA: 'control_wards_bought'
    'win': True,
    'enemy_champion': 'Renekton'
}

# 3. Guardamos
try:
    if db.save_match(fake_match):
        print("✅ Partida guardada correctamente en la DB.")
    else:
        print("⚠️ La partida ya existía (esto es bueno, evita duplicados).")
        
    # 4. Verificamos que se puede leer
    matches = db.get_recent_matches(1)
    print(f"👀 Leído de la DB: Jugaste {matches[0]['champion']} y quedaste {matches[0]['kills']}/{matches[0]['deaths']}/{matches[0]['assists']}")

except Exception as e:
    print(f"❌ Error: {e}")