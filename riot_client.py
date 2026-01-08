from datetime import datetime
from riotwatcher import LolWatcher, RiotWatcher, ApiError

class LoLClient:
    """Cliente para interactuar con la API de Riot Games para League of Legends."""
    
    def __init__(self, api_key: str, region: str = 'EUW1'):
        self.api_key = api_key
        self.region = region.lower()
        self.platform = region.upper()
        
        # HERRAMIENTA 1: Para cosas del juego (Match)
        self.lol_watcher = LolWatcher(api_key)
        
        # HERRAMIENTA 2: Para buscar cuentas (Riot ID)
        self.riot_watcher = RiotWatcher(api_key)
        
        # Mapeo de regiones a rutas continentales
        self.routing_map = {
            'BR1': 'americas', 'LA1': 'americas', 'LA2': 'americas', 'NA1': 'americas',
            'EUN1': 'europe', 'EUW1': 'europe', 'TR1': 'europe', 'RU': 'europe',
            'JP1': 'asia', 'KR': 'asia',
            'OC1': 'sea', 'PH2': 'sea', 'SG2': 'sea', 'TH2': 'sea', 'TW2': 'sea', 'VN2': 'sea',
        }
        self.continental_route = self.routing_map.get(self.platform, 'europe')
    
    def get_summoner_info(self, summoner_name_tag: str) -> dict:
        try:
            if "#" not in summoner_name_tag:
                raise ValueError("El formato debe ser Nombre#Tag (Ej: Lucho77#0709)")
            
            game_name, tag_line = summoner_name_tag.split('#')
            account = self.riot_watcher.account.by_riot_id(self.continental_route, game_name, tag_line)
            puuid = account['puuid']

            return {
                'puuid': puuid,
                'name': account['gameName'],
                'tag': account['tagLine']
            }
        except ApiError as err:
            if err.response.status_code == 403:
                raise ApiError("API Key inválida o caducada.", response=err.response)
            elif err.response.status_code == 404:
                raise ApiError(f"Usuario {summoner_name_tag} no encontrado.", response=err.response)
            else:
                raise err

    def get_recent_matches(self, summoner_name: str, limit: int = 5) -> list:
        """Descarga las últimas 'limit' partidas."""
        try:
            # 1. Obtener PUUID
            summoner_info = self.get_summoner_info(summoner_name)
            puuid = summoner_info['puuid']
            
            # 2. Buscar lista de IDs
            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                self.continental_route, 
                puuid, 
                count=limit
            )
            
            if not match_ids:
                raise ValueError(f"No se encontraron partidas para {summoner_name}.")
            
            # 3. Procesar cada partida
            results = []
            for m_id in match_ids:
                try:
                    match_data = self.lol_watcher.match.by_id(self.continental_route, m_id)
                    participant = next((p for p in match_data['info']['participants'] if p['puuid'] == puuid), None)
                    
                    if participant:
                        # Cálculo seguro del rol
                        role = participant.get('teamPosition', '')
                        if not role:
                            role = participant.get('individualPosition', 'Unknown')

                        stats = {
                            'game_id': match_data['metadata']['matchId'],
                            'date': datetime.fromtimestamp(match_data['info']['gameEndTimestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'champion_name': participant['championName'],
                            'kills': participant['kills'],
                            'deaths': participant['deaths'],
                            'assists': participant['assists'],
                            'win': participant['win'],
                            'cs_total': participant['totalMinionsKilled'] + participant['neutralMinionsKilled'],
                            'game_duration_minutes': round(match_data['info']['gameDuration'] / 60, 2),
                            'control_wards_bought': participant['visionWardsBoughtInGame'],
                            'role': role,
                            'enemy_champion': self._get_enemy_laner(match_data, participant)
                        }
                        results.append(stats)
                except Exception as e:
                    print(f"Error procesando partida {m_id}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            raise e
    
    def _get_enemy_laner(self, match_data: dict, player_data: dict) -> str:
        try:
            player_team = player_data['teamId']
            player_role = player_data.get('teamPosition')
            if not player_role or player_role == 'Invalid': return 'Unknown'
            
            for participant in match_data['info']['participants']:
                if (participant['teamId'] != player_team and 
                    participant.get('teamPosition') == player_role):
                    return participant['championName']
            return 'Unknown'
        except:
            return 'Unknown'