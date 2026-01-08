from riot_client import LoLClient

API_KEY = "RGAPI-0ee2314b-369c-4535-84e3-954142d95c76" # Pega tu RGAPI...
REGION = "euw1" # O la1, na1, etc
SUMMONER = "Lucho77#0709" # Y tu tag si hace falta (Riot ID)

try:
    client = LoLClient(API_KEY, REGION)
    stats = client.get_last_match_stats(SUMMONER)
    print("Datos recuperados con éxito:")
    print(stats)
except Exception as e:
    print(f"Error: {e}")