import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

class MatchDatabase:
    """Clase para gestionar la persistencia de partidas de League of Legends usando SQLite."""
    
    def __init__(self, db_path: str = None):
        # 1. Lógica de rutas (Lo que ya tenías bien)
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, 'data')
            
            # Crear la carpeta data si no existe
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
                
            self.db_path = os.path.join(data_dir, 'lol_tracker.db')
        else:
            self.db_path = db_path

        # 2. Conexión y Configuración (ESTO ES LO QUE FALTABA)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
        self.cursor = self.connection.cursor()     # El ejecutor de SQL
        self.create_table()                        # Crear tabla al iniciar
    
    def create_table(self):
        """Crea la tabla 'matches' si no existe."""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS matches (
            game_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            champion TEXT NOT NULL,
            role TEXT NOT NULL,
            kills INTEGER NOT NULL,
            deaths INTEGER NOT NULL,
            assists INTEGER NOT NULL,
            cs_total INTEGER NOT NULL,
            cs_min REAL NOT NULL,
            control_wards INTEGER NOT NULL,
            win INTEGER NOT NULL,
            enemy_champion TEXT,
            lp_change INTEGER,
            tilt_level INTEGER,
            impact_rating TEXT,
            notes TEXT,
            vod_review INTEGER DEFAULT 0
        )
        """
        try:
            self.cursor.execute(create_table_query)
            self.connection.commit()
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al crear la tabla: {e}")
    
    def save_match(self, match_data: Dict[str, Any]) -> bool:
        try:
            game_id = match_data.get('game_id')
            if not game_id:
                raise ValueError("El diccionario match_data no contiene 'game_id'")

            if 'cs_min' not in match_data:
                cs_min = round(match_data['cs_total'] / match_data['game_duration_minutes'], 2) if match_data['game_duration_minutes'] > 0 else 0.0
            else:
                cs_min = match_data['cs_min']
            
            match_date = match_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            insert_query = """
            INSERT OR IGNORE INTO matches (
                game_id, date, champion, role, kills, deaths, assists,
                cs_total, cs_min, control_wards, win, enemy_champion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        
            self.cursor.execute(insert_query, (
                game_id,
                match_date,
                match_data['champion_name'],
                match_data['role'],
                match_data['kills'],
                match_data['deaths'],
                match_data['assists'],
                match_data['cs_total'],
                cs_min,
                match_data['control_wards_bought'],
                1 if match_data['win'] else 0,
                match_data['enemy_champion']
            ))
            self.connection.commit()
            return self.cursor.rowcount > 0
            
        except sqlite3.Error as e:
            self.connection.rollback()
            raise sqlite3.Error(f"Error al guardar la partida: {e}")
    
    def update_match_details(self, game_id: str, lp_change: Optional[int] = None, tilt_level: Optional[int] = None, impact_rating: Optional[str] = None, notes: Optional[str] = None, vod_review: Optional[bool] = None) -> bool:
        if tilt_level is not None and (tilt_level < 1 or tilt_level > 5):
            raise ValueError("tilt_level debe estar entre 1 y 5")
        
        update_fields = []
        params = []
        
        if lp_change is not None: update_fields.append("lp_change = ?"); params.append(lp_change)
        if tilt_level is not None: update_fields.append("tilt_level = ?"); params.append(tilt_level)
        if impact_rating is not None: update_fields.append("impact_rating = ?"); params.append(impact_rating)
        if notes is not None: update_fields.append("notes = ?"); params.append(notes)
        if vod_review is not None: update_fields.append("vod_review = ?"); params.append(1 if vod_review else 0)
        
        if not update_fields: return False
        
        params.append(game_id)
        update_query = f"UPDATE matches SET {', '.join(update_fields)} WHERE game_id = ?"
        
        try:
            self.cursor.execute(update_query, params)
            self.connection.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.connection.rollback()
            raise sqlite3.Error(f"Error al actualizar: {e}")
    
    def get_recent_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        select_query = "SELECT * FROM matches ORDER BY date DESC LIMIT ?"
        try:
            self.cursor.execute(select_query, (limit,))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al leer partidas: {e}")
        
    def get_stats_summary(self) -> Dict[str, Any]:
        try:
            self.cursor.execute("SELECT COUNT(*), SUM(win) FROM matches")
            total_games, total_wins = self.cursor.fetchone()
            total_games = total_games or 0
            total_wins = total_wins or 0
            winrate = (total_wins / total_games * 100) if total_games > 0 else 0.0
            
            self.cursor.execute("SELECT AVG(kills), AVG(deaths), AVG(assists), AVG(cs_min) FROM matches")
            avg_k, avg_d, avg_a, avg_cs = self.cursor.fetchone()
            
            return {
                'total_games': total_games,
                'total_wins': total_wins,
                'winrate': round(winrate, 1),
                'kda': f"{round(avg_k or 0, 1)} / {round(avg_d or 0, 1)} / {round(avg_a or 0, 1)}",
                'cs_min_avg': round(avg_cs or 0, 1)
            }
        except Exception as e:
            return {'total_games': 0, 'total_wins': 0, 'winrate': 0, 'kda': "0/0/0", 'cs_min_avg': 0}

    def get_match_by_id(self, game_id: str) -> Optional[Dict[str, Any]]:
        try:
            self.cursor.execute("SELECT * FROM matches WHERE game_id = ?", (game_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

    def get_matchup_notes(self, my_champion: str, enemy_champion: str) -> List[Dict[str, Any]]:
        """Historial Específico (Yo con X vs Él con Y)"""
        matchup_query = """
        SELECT * FROM matches WHERE champion = ? AND enemy_champion = ? ORDER BY date DESC
        """
        try:
            self.cursor.execute(matchup_query, (my_champion, enemy_champion))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error: {e}")

    def get_matches_vs_enemy(self, enemy_champion: str) -> List[Dict[str, Any]]:
        """
        NUEVO: Busca todas las partidas contra un campeón enemigo específico,
        sin importar qué jugaste tú. Ideal para el Scout Pre-Game.
        """
        query = "SELECT * FROM matches WHERE enemy_champion LIKE ? ORDER BY date DESC"
        try:
            # El LIKE permite que si buscas "Zed" encuentre "Zed" sin problemas de mayúsculas a veces
            self.cursor.execute(query, (enemy_champion,))
            return [dict(row) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error Scout: {e}")
        
    
    def get_champion_performance(self) -> List[Dict[str, Any]]:
        """
        Obtiene estadísticas de rendimiento agrupadas por campeón.
        Útil para identificar tus mejores y peores campeones.
    
        Returns:
            List[Dict]: Lista de diccionarios con estadísticas por campeón:
                - champion: Nombre del campeón
                - games_played: Total de partidas jugadas
                - wins: Total de victorias
                - losses: Total de derrotas
                - winrate: Porcentaje de victorias
                - avg_kills: Promedio de kills
                - avg_deaths: Promedio de deaths
                - avg_assists: Promedio de assists
                - kda_ratio: Ratio KDA calculado
                - avg_cs_min: Promedio de CS por minuto
            
        Raises:
            sqlite3.Error: Si hay error en la consulta
        """
        champion_stats_query = """
        SELECT 
            champion,
            COUNT(*) as games_played,
            SUM(win) as wins,
            AVG(kills) as avg_kills,
            AVG(deaths) as avg_deaths,
            AVG(assists) as avg_assists,
            AVG(cs_min) as avg_cs_min
        FROM matches
        GROUP BY champion
        ORDER BY games_played DESC, wins DESC
        """
    
        try:
            self.cursor.execute(champion_stats_query)
            rows = self.cursor.fetchall()
        
            champion_stats = []
            for row in rows:
                games_played = row['games_played']
                wins = row['wins'] or 0
                losses = games_played - wins
            
                # Calcular winrate
                winrate = round((wins / games_played * 100), 1) if games_played > 0 else 0.0
            
                # Calcular KDA ratio (evitar división por cero)
                avg_kills = row['avg_kills'] or 0
                avg_deaths = row['avg_deaths'] or 0
                avg_assists = row['avg_assists'] or 0
            
                if avg_deaths > 0:
                    kda_ratio = round((avg_kills + avg_assists) / avg_deaths, 2)
                else:
                    kda_ratio = round(avg_kills + avg_assists, 2)
            
                stats = {
                    'champion': row['champion'],
                    'games_played': games_played,
                    'wins': wins,
                    'losses': losses,
                    'winrate': winrate,
                    'avg_kills': round(avg_kills, 1),
                    'avg_deaths': round(avg_deaths, 1),
                    'avg_assists': round(avg_assists, 1),
                    'kda_ratio': kda_ratio,
                    'avg_cs_min': round(row['avg_cs_min'] or 0, 1)
                }
                champion_stats.append(stats)
        
            return champion_stats
        
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al obtener estadísticas por campeón: {e}")

    def close(self):
        if self.connection: self.connection.close()