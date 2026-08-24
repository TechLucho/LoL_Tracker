import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, List, Dict, Any

class MatchDatabase:
    """Clase para gestionar la persistencia de partidas usando PostgreSQL (Supabase)."""
    
    def __init__(self):
        # 1. Obtener credenciales de variables de entorno
        self.host = os.getenv("DB_HOST")
        self.database = os.getenv("DB_NAME")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.port = os.getenv("DB_PORT", "5432")

        # Verificar que existen
        if not all([self.host, self.database, self.user, self.password]):
            # Fallback para desarrollo local si no hay env vars configuradas, o lanzar error
            print("⚠️ Faltan credenciales de Base de Datos en .env")
            self.connection = None
            return

        # 2. Conexión
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port
            )
            self.connection.autocommit = False # Manejamos transacciones manualmente
        except Exception as e:
            print(f"Error conectando a BD: {e}")
            self.connection = None

        if self.connection:
            self.create_table()
    
    def get_cursor(self):
        """Devuelve un cursor que permite acceder a columnas por nombre."""
        if self.connection:
            return self.connection.cursor(cursor_factory=RealDictCursor)
        return None

    def create_table(self):
        """Crea la tabla 'matches' si no existe (Sintaxis PostgreSQL)."""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS matches (
            game_id TEXT PRIMARY KEY,
            date TIMESTAMP,
            champion TEXT NOT NULL,
            role TEXT NOT NULL,
            kills INTEGER NOT NULL,
            deaths INTEGER NOT NULL,
            assists INTEGER NOT NULL,
            cs_total INTEGER NOT NULL,
            cs_min REAL NOT NULL,
            control_wards INTEGER NOT NULL,
            win BOOLEAN NOT NULL,
            enemy_champion TEXT,
            game_duration_minutes REAL,
            lp_change INTEGER,
            tilt_level INTEGER,
            impact_rating TEXT,
            notes TEXT,
            vod_review BOOLEAN DEFAULT FALSE
        )
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            print(f"Error al crear la tabla: {e}")
    
    def save_match(self, match_data: Dict[str, Any]) -> bool:
        """Guarda una partida en la base de datos."""
        if not self.connection: return False
        
        try:
            game_id = match_data.get('game_id')
            if not game_id: return False

            game_duration = match_data.get('game_duration_minutes', 0)
            if 'cs_min' not in match_data:
                cs_min = round(match_data['cs_total'] / game_duration, 2) if game_duration > 0 else 0.0
            else:
                cs_min = match_data['cs_min']
            
            match_date = match_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Sintaxis Postgres para "INSERT OR IGNORE" es "ON CONFLICT DO NOTHING"
            insert_query = """
            INSERT INTO matches (
                game_id, date, champion, role, kills, deaths, assists,
                cs_total, cs_min, control_wards, win, enemy_champion, game_duration_minutes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id) DO NOTHING
            """
        
            with self.connection.cursor() as cursor:
                cursor.execute(insert_query, (
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
                    bool(match_data['win']), # Postgres usa bool
                    match_data.get('enemy_champion', 'Unknown'),
                    game_duration
                ))
                inserted = cursor.rowcount > 0
            self.connection.commit()
            return inserted
            
        except Exception as e:
            self.connection.rollback()
            raise Exception(f"Error al guardar la partida: {e}")
    
    def update_match_details(self, game_id: str, lp_change: Optional[int] = None, 
                           tilt_level: Optional[int] = None, impact_rating: Optional[str] = None, 
                           notes: Optional[str] = None, vod_review: Optional[bool] = None) -> bool:
        """Actualiza los detalles subjetivos de una partida."""
        if not self.connection: return False

        update_fields = []
        params = []
        
        if lp_change is not None: 
            update_fields.append("lp_change = %s")
            params.append(lp_change)
        if tilt_level is not None: 
            update_fields.append("tilt_level = %s")
            params.append(tilt_level)
        if impact_rating is not None: 
            update_fields.append("impact_rating = %s")
            params.append(impact_rating)
        if notes is not None: 
            update_fields.append("notes = %s")
            params.append(notes)
        if vod_review is not None: 
            update_fields.append("vod_review = %s")
            params.append(bool(vod_review))
        
        if not update_fields: return False
        
        params.append(game_id)
        update_query = f"UPDATE matches SET {', '.join(update_fields)} WHERE game_id = %s"
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(update_query, params)
                updated = cursor.rowcount > 0
            self.connection.commit()
            return updated
        except Exception as e:
            self.connection.rollback()
            raise Exception(f"Error al actualizar: {e}")
    
    def get_recent_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.connection: return []
        select_query = "SELECT * FROM matches ORDER BY date DESC LIMIT %s"
        try:
            with self.get_cursor() as cursor:
                cursor.execute(select_query, (limit,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error: {e}")
            return []
        
    def get_stats_summary(self) -> Dict[str, Any]:
        if not self.connection: return {}
        try:
            with self.get_cursor() as cursor:
                # Stats Generales
                cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins FROM matches")
                gen = cursor.fetchone()
                total_games = gen['total'] if gen else 0
                total_wins = gen['wins'] if gen and gen['wins'] else 0
                winrate = (total_wins / total_games * 100) if total_games > 0 else 0.0
                
                # Promedios
                cursor.execute("SELECT AVG(kills) as k, AVG(deaths) as d, AVG(assists) as a, AVG(cs_min) as cs FROM matches")
                avgs = cursor.fetchone()
                
            return {
                'total_games': total_games,
                'total_wins': total_wins,
                'winrate': round(winrate, 1),
                'kda': f"{round(avgs['k'], 1)} / {round(avgs['d'], 1)} / {round(avgs['a'], 1)}" if avgs and avgs['k'] else "0/0/0",
                'cs_min_avg': round(avgs['cs'], 1) if avgs and avgs['cs'] else 0
            }
        except Exception as e:
            print(f"Error stats: {e}")
            return {}

    def get_match_by_id(self, game_id: str) -> Optional[Dict[str, Any]]:
        if not self.connection: return None
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT * FROM matches WHERE game_id = %s", (game_id,))
                return cursor.fetchone()
        except Exception:
            return None

    def get_matchup_notes(self, my_champion: str, enemy_champion: str) -> List[Dict[str, Any]]:
        if not self.connection: return []
        query = "SELECT * FROM matches WHERE champion = %s AND enemy_champion = %s ORDER BY date DESC"
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (my_champion, enemy_champion))
                return cursor.fetchall()
        except Exception:
            return []

    def get_matches_vs_enemy(self, enemy_champion_pattern: str) -> List[Dict[str, Any]]:
        if not self.connection: return []
        # En Postgres LIKE es Case Sensitive, ILIKE no lo es
        query = "SELECT * FROM matches WHERE enemy_champion ILIKE %s ORDER BY date DESC"
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (enemy_champion_pattern,))
                return cursor.fetchall()
        except Exception:
            return []
    
    def get_champion_performance(self) -> List[Dict[str, Any]]:
        if not self.connection: return []
        # Sintaxis Postgres para CAST de booleanos a int para sumar: SUM(win::int)
        query = """
        SELECT 
            champion,
            COUNT(*) as games_played,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
            AVG(kills) as avg_kills,
            AVG(deaths) as avg_deaths,
            AVG(assists) as avg_assists,
            AVG(cs_min) as avg_cs_min
        FROM matches
        GROUP BY champion
        ORDER BY games_played DESC, wins DESC
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error champ perf: {e}")
            return []
        
    def get_nemesis_list(self, min_games: int = 2) -> List[Dict[str, Any]]:
        if not self.connection: return []
        query = """
        SELECT 
            enemy_champion,
            COUNT(*) as games,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
            (CAST(SUM(CASE WHEN win THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)) * 100 as winrate,
            AVG(cs_min) as avg_cs_min,
            AVG(deaths) as avg_deaths
        FROM matches
        WHERE enemy_champion IS NOT NULL AND enemy_champion != 'Unknown'
        GROUP BY enemy_champion
        HAVING COUNT(*) >= %s
        ORDER BY winrate ASC, games DESC
        LIMIT 5
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (min_games,))
                return cursor.fetchall()
        except Exception as e:
            print(e)
            return []

    def get_activity_heatmap_data(self) -> List[Dict[str, Any]]:
        if not self.connection: return []
        # PostgreSQL usa EXTRACT(DOW ...) para día semana (0=Domingo)
        # y EXTRACT(HOUR ...) para hora
        query = """
        SELECT 
            CAST(EXTRACT(DOW FROM date) AS INTEGER) as weekday,
            CAST(EXTRACT(HOUR FROM date) AS INTEGER) as hour,
            COUNT(*) as games,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins
        FROM matches
        GROUP BY weekday, hour
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(e)
            return []

    def close(self):
        if self.connection: 
            self.connection.close()