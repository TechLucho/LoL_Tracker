import streamlit as st
from riot_client import LoLClient
from database import MatchDatabase
from riotwatcher import ApiError
import sqlite3
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="LoL Performance Tracker",
    page_icon="🎮",
    layout="wide"
)

# Inicializar session_state
if 'api_key' not in st.session_state: st.session_state.api_key = ""
if 'riot_id' not in st.session_state: st.session_state.riot_id = ""
if 'region' not in st.session_state: st.session_state.region = "EUW1"
if 'last_match_data' not in st.session_state: st.session_state.last_match_data = None
if 'last_match_id' not in st.session_state: st.session_state.last_match_id = None
if 'config_saved' not in st.session_state: st.session_state.config_saved = False
if 'matchup_history' not in st.session_state: st.session_state.matchup_history = None

# ============ SIDEBAR ============
st.sidebar.title("⚙️ Configuración")
with st.sidebar:
    api_key_input = st.text_input("Riot API Key", type="password", value=st.session_state.api_key)
    riot_id_input = st.text_input("Riot ID", value=st.session_state.riot_id, placeholder="Ej: Lucho77#0709")
    region_input = st.selectbox("Región", ['EUW1', 'NA1', 'LA1', 'LA2'], index=0)
    
    if st.button("💾 Guardar Configuración", use_container_width=True):
        if not api_key_input or not riot_id_input:
            st.error("⚠️ Completa todos los campos.")
        else:
            st.session_state.api_key = api_key_input
            st.session_state.riot_id = riot_id_input
            st.session_state.region = region_input
            st.session_state.config_saved = True
            st.success("✅ Configuración guardada")
    
    st.markdown("---")
    
    # === LA CONSTITUCIÓN ===
    st.markdown("### 📜 La Constitución")
    try:
        db = MatchDatabase()
        last_3 = db.get_recent_matches(3)
        if len(last_3) >= 1:
            wins = sum(1 for m in last_3 if m['win'])
            losses = len(last_3) - wins
            # Lógica simple: si en las ultimas 3 hay 2 derrotas recientes
            # (Podemos refinar esto, pero para empezar visualmente:)
            current_streak_losses = 0
            for m in last_3:
                if not m['win']: current_streak_losses += 1
                else: break
            
            if current_streak_losses >= 2:
                st.error(f"⛔ STOP: {current_streak_losses} Derrotas seguidas.")
            elif wins == 3 and len(last_3)==3:
                st.success("🔥 ON FIRE: 3 Victorias.")
            else:
                st.info(f"Últimas: {' '.join(['✅' if m['win'] else '❌' for m in last_3])}")
        db.close()
    except Exception:
        pass

    # === OKR TRACKER (ESTILO MÉTRICAS) ===
    st.markdown("---")
    st.markdown("### 🎯 Objetivos (OKR)")
    
    try:
        db = MatchDatabase()
        stats = db.get_stats_summary() 
        db.close()
        
        # 1. Farm (Objetivo: 7.0)
        target_cs = 7.0
        current_cs = stats['cs_min_avg']
        delta_cs = round(current_cs - target_cs, 1)
        
        st.metric(
            label="🌾 Farm (Meta: 7.0)",
            value=f"{current_cs}",
            delta=f"{delta_cs} CS/min",
            delta_color="normal" # Verde si es positivo, Rojo si es negativo
        )

        # 2. Winrate (Objetivo: 50%)
        target_wr = 50.0
        current_wr = stats['winrate']
        delta_wr = round(current_wr - target_wr, 1)
        
        st.metric(
            label="🏆 Winrate (Meta: >50%)",
            value=f"{current_wr}%",
            delta=f"{delta_wr}%",
            delta_color="normal"
        )

    except Exception as e:
        st.error(f"Error cargando objetivos: {e}")

    # === ESTADISTICAS ===
    st.markdown("---")
    st.markdown("### 📊 Stats Globales")
    try:
        db = MatchDatabase()
        stats = db.get_stats_summary()
        c1, c2 = st.columns(2)
        c1.metric("Games", stats['total_games'])
        c1.metric("Winrate", f"{stats['winrate']}%")
        c2.metric("KDA", stats['kda'])
        db.close()
    except Exception:
        st.error("Error DB")

# ============ MAIN ============
st.title("🎮 LoL Performance Tracker")

if not st.session_state.config_saved:
    st.warning("⚠️ Configura tu cuenta en la barra lateral.")
    st.stop()

# ============ PESTAÑAS ============
tab1, tab2 = st.tabs(["📊 Diario", "🏆 Champion Pool"])

# --- PESTAÑA 1: DIARIO ---
with tab1:
    # BOTÓN DE SINCRONIZACIÓN (MODIFICADO: 10 RANKED)
    if st.button("🔄 Sincronizar (10 Ranked Solo/Duo)", use_container_width=True, type="primary"):
        with st.spinner("Analizando tus Rankeds..."):
            try:
                client = LoLClient(st.session_state.api_key, st.session_state.region)
                db = MatchDatabase()
                
                # Pedimos 10 partidas y forzamos queue=420 (Solo/Duo)
                matches = client.get_recent_matches(st.session_state.riot_id, limit=10, queue=420)
                
                new_count = 0
                for m in matches:
                    if db.save_match(m):
                        new_count += 1
                
                # Cargar la MÁS RECIENTE por defecto
                if matches:
                    latest = matches[0]
                    st.session_state.last_match_data = latest
                    st.session_state.last_match_id = latest['game_id']
                    st.session_state.matchup_history = db.get_matchup_notes(latest['champion_name'], latest['enemy_champion'])
                
                if new_count > 0:
                    st.balloons()
                    st.success(f"✨ Se han importado {new_count} Rankeds nuevas.")
                else:
                    if not matches:
                        st.warning("No se encontraron partidas Ranked Solo/Duo recientes.")
                    else:
                        st.info("📌 Todo actualizado. No hay Rankeds nuevas.")
                db.close()
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # ============ VISUALIZACIÓN ============
    if st.session_state.last_match_data:
        m = st.session_state.last_match_data
        
        # Tarjeta Principal
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Campeón", m['champion_name'])
        c2.metric("KDA", f"{m['kills']}/{m['deaths']}/{m['assists']}")
        c3.metric("Resultado", "Victoria 🏆" if m['win'] else "Derrota 💀")
        c4.metric("Vs", m['enemy_champion'])
        
        st.divider()
        
        # Inteligencia de Matchup
        if st.session_state.matchup_history:
            # Filtramos para no contar la partida actual si ya está en el historial
            history = [h for h in st.session_state.matchup_history if h['date'] != m['date']]
            
            if history:
                st.info(f"💡 **Historial vs {m['enemy_champion']}:** Tienes {len(history)} partidas previas.")
                last = history[0]
                st.markdown(f"**Última vez ({last['date']}):** {last['result']} con {last['kda']}.")
                if last['notes']:
                    st.warning(f"📝 **Tus notas pasadas:** {last['notes']}")
        
        st.divider()
        
        # Formulario
        st.subheader("📝 Análisis")
        
        # Intentamos cargar datos guardados
        db = MatchDatabase()
        saved = db.get_match_by_id(st.session_state.last_match_id) or {}
        db.close()
        
        with st.form("analysis"):
            c1, c2 = st.columns(2)
            with c1:
                lp = st.number_input("LP Change", value=saved.get('lp_change', 0))
                tilt = st.slider("Tilt (1-5)", 1, 5, saved.get('tilt_level', 1))
                impact = st.selectbox("Impacto", ["Carree", "Fui Carreado", "Invisible", "Inteé"], 
                                    index=0 if not saved.get('impact_rating') else ["Carree", "Fui Carreado", "Invisible", "Inteé"].index(saved['impact_rating']))
            with c2:
                vod = st.checkbox("VOD Review?", value=bool(saved.get('vod_review', 0)))
                notes = st.text_area("Notas / Matchup", value=saved.get('notes', ""))
                
            if st.form_submit_button("💾 Guardar"):
                db = MatchDatabase()
                db.update_match_details(st.session_state.last_match_id, lp, tilt, impact, notes, vod)
                st.success("Guardado!")
                st.rerun()

    # Historial
    st.divider()
    st.subheader("📜 Historial")
    try:
        db = MatchDatabase()
        recents = db.get_recent_matches(10)
        
        if recents:
            for r in recents:
                # Calcular KDA ratio
                kda_ratio = ((r['kills'] + r['assists']) / r['deaths']) if r['deaths'] > 0 else (r['kills'] + r['assists'])
                
                # Título del expander con emojis y resultado
                expander_title = f"{'🏆' if r['win'] else '💀'} {r['champion']} - {r['role']} | {r['kills']}/{r['deaths']}/{r['assists']} | {r['date']}"
                
                with st.expander(expander_title):
                    # Fila 1: Métricas clave
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("KDA", f"{r['kills']}/{r['deaths']}/{r['assists']}")
                        st.caption(f"Ratio: {kda_ratio:.2f}")
                    
                    with col2:
                        st.metric("CS Total", r['cs_total'])
                        st.caption(f"CS/min: {r['cs_min']:.1f}")
                    
                    with col3:
                        st.metric("Control Wards", r['control_wards'])
                    
                    with col4:
                        if r['lp_change'] is not None:
                            delta_color = "normal" if r['lp_change'] >= 0 else "inverse"
                            st.metric("LP Change", 
                                     f"{'+' if r['lp_change'] > 0 else ''}{r['lp_change']}", 
                                     delta=f"{r['lp_change']} LP",
                                     delta_color=delta_color)
                        else:
                            st.metric("LP Change", "N/A")
                    
                    st.divider()
                    
                    # Fila 2: Matchup e Impacto
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        enemy = r['enemy_champion'] if r['enemy_champion'] else 'Unknown'
                        st.markdown(f"**⚔️ Matchup:** {r['champion']} vs **{enemy}**")
                        if r['tilt_level']:
                            tilt_emoji = "😌" if r['tilt_level'] <= 2 else ("😐" if r['tilt_level'] == 3 else "😤")
                            st.markdown(f"**Tilt Level:** {tilt_emoji} {r['tilt_level']}/5")
                    
                    with col2:
                        if r['impact_rating']:
                            impact_emoji = {
                                "Carreé": "💪",
                                "Carree": "💪",
                                "Fui Carreado": "🚌",
                                "Invisible": "👻",
                                "Inteé": "💩"
                            }.get(r['impact_rating'], "❓")
                            st.markdown(f"**Impacto:** {impact_emoji} {r['impact_rating']}")
                        
                        if r['vod_review']:
                            st.markdown("**VOD Review:** ✅ Revisado")
                        else:
                            st.markdown("**VOD Review:** ❌ Sin revisar")
                    
                    # Notas
                    if r['notes']:
                        st.divider()
                        st.markdown("**📝 Notas:**")
                        st.info(r['notes'])
        else:
            st.info("No hay partidas registradas aún. ¡Carga tu primera partida!")
        
        db.close()
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")

# ============ TAB 2: CHAMPION POOL (CON ICONOS) ============
with tab2:
    st.subheader("🏆 Análisis de Champion Pool")
    st.markdown("Rendimiento detallado de cada campeón jugado")
    
    try:
        db = MatchDatabase()
        champion_stats = db.get_champion_performance()
        db.close()
        
        if champion_stats:
            # Convertir a DataFrame
            df = pd.DataFrame(champion_stats)
            
            # --- NUEVO: AÑADIR IMÁGENES ---
            # Definimos el parche actual (puedes actualizarlo manualmente si salen nuevos champs)
            current_patch = "16.1.1"
            
            # Creamos la columna con la URL de la imagen para cada campeón
            # Data Dragon usa el nombre del campeón (ej: "Ashe", "Garen")
            df['Imagen'] = df['champion'].apply(
                lambda x: f"https://ddragon.leagueoflegends.com/cdn/{current_patch}/img/champion/{x}.png"
            )

            # Reordenamos columnas para poner la imagen primero
            df = df[['Imagen', 'champion', 'games_played', 'wins', 'losses', 'winrate', 'kda_ratio', 'avg_cs_min']]
            
            # Renombrar columnas para mejor presentación
            df = df.rename(columns={
                'champion': 'Campeón',
                'games_played': 'Partidas',
                'wins': 'Wins',     # Abreviamos para que quepa mejor
                'losses': 'Losses',   # Abreviamos
                'winrate': 'Winrate',
                'kda_ratio': 'KDA',
                'avg_cs_min': 'CS/min'
            })
            
            # Configurar el dataframe visualmente
            st.dataframe(
                df,
                column_config={
                    "Imagen": st.column_config.ImageColumn(
                        "Icono", 
                        help="Campeón"
                    ),
                    "Winrate": st.column_config.ProgressColumn(
                        "Winrate",
                        help="Porcentaje de victorias",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                    ),
                    "KDA": st.column_config.NumberColumn(
                        "KDA",
                        format="%.2f ⭐"
                    ),
                    "CS/min": st.column_config.NumberColumn(
                        "CS/min",
                        format="%.1f 🌾"
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Métricas destacadas (Insights)
            st.divider()
            st.subheader("📈 Insights")
            
            col1, col2, col3 = st.columns(3)
            
            # Campeón más jugado (Usamos iloc[0] porque la query SQL ya ordena por partidas)
            most_played = df.iloc[0]
            with col1:
                st.metric(
                    "🎯 Campeón Más Jugado", 
                    most_played['Campeón'],
                    f"{most_played['Partidas']} partidas"
                )
            
            # Filtrar para KDA y Winrate (mínimo 3 partidas para que sea relevante)
            df_filtered = df[df['Partidas'] >= 3]
            
            if not df_filtered.empty:
                # Mejor Winrate
                best_wr = df_filtered.loc[df_filtered['Winrate'].idxmax()]
                with col2:
                    st.metric(
                        "🏆 Mejor Winrate", 
                        best_wr['Campeón'],
                        f"{best_wr['Winrate']:.1f}%"
                    )
                
                # Mejor KDA
                best_kda = df_filtered.loc[df_filtered['KDA'].idxmax()]
                with col3:
                    st.metric(
                        "⚡ Mejor KDA", 
                        best_kda['Campeón'],
                        f"{best_kda['KDA']:.2f}"
                    )
            else:
                st.info("Juega al menos 3 partidas con un campeón para desbloquear insights avanzados.")
            
        else:
            st.info("🎮 Aún no hay datos de campeones. ¡Empieza a jugar y registrar partidas!")
            
    except Exception as e:
        st.error(f"❌ Error al cargar estadísticas de campeones: {e}")