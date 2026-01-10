from datetime import datetime
from riotwatcher import LolWatcher, RiotWatcher, ApiError

class LoLClient:
    """Cliente para interactuar con la API de Riot Games para League of Legends."""
    
    def __init__(self, api_key: str, region: str = 'EUW1'):
        """
        Inicializa el cliente de Riot API.
        
        Args:
            api_key: Tu clave de API de Riot Games
            region: Región del servidor (por defecto 'EUW1')
        """
        if not api_key:
            raise ValueError("API Key no puede estar vacía")
            
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
        """
        Obtiene la información básica de un invocador usando su Riot ID.
        
        Args:
            summoner_name_tag: Riot ID en formato 'NombreJugador#TAG'
            
        Returns:
            Dict con puuid, name y tag del jugador
            
        Raises:
            ValueError: Si el formato del Riot ID es incorrecto
            ApiError: Si hay problemas con la API de Riot
        """
        try:
            if "#" not in summoner_name_tag:
                raise ValueError("El formato debe ser Nombre#Tag (Ej: Faker#KR1)")
            
            game_name, tag_line = summoner_name_tag.split('#', 1)
            
            if not game_name or not tag_line:
                raise ValueError("Nombre o Tag vacíos. Usa el formato correcto: Nombre#Tag")
            
            account = self.riot_watcher.account.by_riot_id(
                self.continental_route, 
                game_name, 
                tag_line
            )
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
                raise ApiError(f"Usuario {summoner_name_tag} no encontrado en {self.continental_route}.", response=err.response)
            elif err.response.status_code == 429:
                raise ApiError("Límite de peticiones excedido. Espera unos minutos.", response=err.response)
            else:
                raise ApiError(f"Error de API: {err.response.status_code}", response=err.response)
        except Exception as e:
            raise Exception(f"Error inesperado al obtener info del invocador: {e}")

    def get_recent_matches(self, summoner_name: str, limit: int = 10, queue: int = 420) -> list:
        """
        Descarga las últimas 'limit' partidas del jugador.
        
        Args:
            summoner_name: Riot ID en formato 'Nombre#Tag'
            limit: Número de partidas a descargar (máx 20)
            queue: Tipo de cola (420=Ranked Solo/Duo, 440=Ranked Flex, None=Todas)
            
        Returns:
            Lista de diccionarios con estadísticas de cada partida
            
        Raises:
            Exception: Si hay errores al obtener las partidas
        """
        try:
            # 1. Obtener PUUID
            summoner_info = self.get_summoner_info(summoner_name)
            puuid = summoner_info['puuid']
            
            # 2. Buscar lista de IDs (FILTRANDO POR TIPO DE COLA)
            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                self.continental_route, 
                puuid, 
                count=min(limit, 20),  # API limita a 20
                queue=queue
            )
            
            if not match_ids:
                return []
            
            # 3. Procesar cada partida
            results = []
            for m_id in match_ids:
                try:
                    match_data = self.lol_watcher.match.by_id(self.continental_route, m_id)
                    participant = next(
                        (p for p in match_data['info']['participants'] if p['puuid'] == puuid), 
                        None
                    )
                    
                    if not participant:
                        continue
                    
                    # Cálculo seguro del rol
                    role = participant.get('teamPosition', '')
                    if not role or role == 'Invalid':
                        role = participant.get('individualPosition', 'Unknown')
                    
                    # Duración del juego en minutos
                    game_duration_minutes = round(match_data['info']['gameDuration'] / 60, 2)
                    
                    # Total de CS
                    cs_total = participant['totalMinionsKilled'] + participant['neutralMinionsKilled']
                    
                    # Calcular CS/min
                    cs_min = round(cs_total / game_duration_minutes, 2) if game_duration_minutes > 0 else 0.0

                    stats = {
                        'game_id': match_data['metadata']['matchId'],
                        'date': datetime.fromtimestamp(
                            match_data['info']['gameEndTimestamp'] / 1000
                        ).strftime('%Y-%m-%d %H:%M:%S'),
                        'champion_name': participant['championName'],
                        'kills': participant['kills'],
                        'deaths': participant['deaths'],
                        'assists': participant['assists'],
                        'win': participant['win'],
                        'cs_total': cs_total,
                        'cs_min': cs_min,
                        'game_duration_minutes': game_duration_minutes,
                        'control_wards_bought': participant['visionWardsBoughtInGame'],
                        'role': role,
                        'enemy_champion': self._get_enemy_laner(match_data, participant)
                    }
                    results.append(stats)
                    
                except Exception as e:
                    print(f"Error procesando partida {m_id}: {e}")
                    continue
            
            return results
            
        except ApiError as e:
            raise Exception(f"Error de API al obtener partidas: {str(e)}")
        except Exception as e:
            raise Exception(f"Error inesperado al obtener partidas: {str(e)}")
    
    def _get_enemy_laner(self, match_data: dict, player_data: dict) -> str:
        """
        Intenta identificar al rival directo en la lane.
        
        Args:
            match_data: Datos completos de la partida
            player_data: Datos del jugador
            
        Returns:
            Nombre del campeón enemigo o 'Unknown'
        """
        try:
            player_team = player_data['teamId']
            player_role = player_data.get('teamPosition')
            
            if not player_role or player_role == 'Invalid': 
                return 'Unknown'
            
            for participant in match_data['info']['participants']:
                if (participant['teamId'] != player_team and 
                    participant.get('teamPosition') == player_role):
                    return participant['championName']
                    
            return 'Unknown'
        except Exception as e:
            print(f"Error identificando rival: {e}")
            return 'Unknown'