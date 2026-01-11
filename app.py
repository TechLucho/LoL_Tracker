import streamlit as st
import os
from dotenv import load_dotenv  # [NUEVO] Importar librería
from riot_client import LoLClient
from database import MatchDatabase
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import time

# [NUEVO] Cargar variables de entorno al inicio
load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="LoL Tryhard Tracker",
    page_icon="🛡️",
    layout="wide"
)

# [NUEVO] Obtener API KEY segura
API_KEY = os.getenv("RIOT_API_KEY")

# Validación de seguridad
if not API_KEY:
    st.error("⛔ ERROR CRÍTICO: No se encontró la API KEY.")
    st.info("Por favor, crea un archivo llamado '.env' en la carpeta del proyecto y añade: RIOT_API_KEY=RGAPI-Tu-Clave")
    st.stop()

# Inicializar session_state
if 'riot_id' not in st.session_state: 
    # [MEJORA] Carga el Riot ID del .env por defecto, o lo deja vacío
    st.session_state.riot_id = os.getenv("RIOT_ID", "")
if 'region' not in st.session_state: 
    st.session_state.region = os.getenv("RIOT_REGION", "EUW1")
if 'last_match_data' not in st.session_state: 
    st.session_state.last_match_data = None
if 'last_match_id' not in st.session_state: 
    st.session_state.last_match_id = None
if 'editing_match_id' not in st.session_state: 
    st.session_state.editing_match_id = None
if 'config_saved' not in st.session_state: 
    # [MEJORA] Si ya hay datos en el .env, asumimos que está configurado
    st.session_state.config_saved = bool(st.session_state.riot_id)
# ============ SIDEBAR: CONFIGURACIÓN & OKRs ============
st.sidebar.title("⚙️ El Cuartel General")

with st.sidebar:
    # 1. Credenciales (SIMPLIFICADO)
    with st.expander("👤 Perfil de Jugador", expanded=not st.session_state.config_saved):
        # [MODIFICADO] Ya no pedimos la API Key por pantalla
        st.success("🔑 API Key: Cargada seguramente desde .env")
        
        riot_id_input = st.text_input("Riot ID", value=st.session_state.riot_id, placeholder="Ej: Faker#KR1")
        region_input = st.selectbox("Región", ['EUW1', 'NA1', 'LA1', 'LA2'], 
                                  index=['EUW1', 'NA1', 'LA1', 'LA2'].index(st.session_state.region) if st.session_state.region in ['EUW1', 'NA1', 'LA1', 'LA2'] else 0)
        
        if st.button("💾 Actualizar Perfil", use_container_width=True):
            if not riot_id_input:
                st.error("Falta el Riot ID.")
            else:
                st.session_state.riot_id = riot_id_input
                st.session_state.region = region_input
                st.session_state.config_saved = True
                st.success("Perfil actualizado")

    st.markdown("---")
    
    # 2. LA CONSTITUCIÓN (Reglas estrictas)
    st.subheader("📜 La Constitución")
    
    # Definición del Champion Pool (Regla de oro)
    st.markdown("**🛡️ Champion Pool (Max 3)**")
    main_champs_str = st.text_area("Tus Mains (separados por coma)", 
                                 value="Jax, Fiora, Camille", 
                                 help="Si juegas algo fuera de esto, la app te avisará.")
    main_champs = [c.strip().lower() for c in main_champs_str.split(',')]

    # Verificación de Estado Mental (Regla de 3 Bloques)
    try:
        db = MatchDatabase()
        last_3 = db.get_recent_matches(3)
        db.close()
        
        if len(last_3) > 0:
            wins = sum(1 for m in last_3 if m['win'])
            losses = len(last_3) - wins
            
            # Lógica de STOP
            streak_losses = 0
            for m in last_3:
                if not m['win']: 
                    streak_losses += 1
                else: 
                    break
            
            st.markdown("#### Estado Actual:")
            if streak_losses >= 2:
                st.error(f"⛔ **STOP OBLIGATORIO**\n\nLlevas {streak_losses} derrotas seguidas. Cierra el juego 1 hora.")
            elif wins == 3 and len(last_3) == 3:
                st.success("🔥 **ON FIRE**\n\n3/3 Victorias. Sigue jugando hasta perder.")
            else:
                st.info(f"Racha: {' '.join(['✅' if m['win'] else '❌' for m in last_3])}")
                st.caption("Recuerda: Bloques de 3 partidas.")
    except Exception as e:
        st.caption(f"No hay datos suficientes para mostrar estado.")

    st.markdown("---")

    # 3. OKRs (Objetivos Escalables)
    st.subheader("🎯 Objetivos (Sprint)")
    
    # Inputs configurables para OKRs
    target_cs = st.number_input("Meta CS/min", value=7.5, step=0.1)
    target_deaths = st.number_input("Tope Muertes/game", value=4.0, step=0.5)
    
    try:
        db = MatchDatabase()
        stats = db.get_stats_summary() 
        db.close()
        
        # CS Metric
        delta_cs = round(stats['cs_min_avg'] - target_cs, 1)
        st.metric("🌾 Farm Promedio", f"{stats['cs_min_avg']}", delta=delta_cs)
        
        # Deaths Metric
        try:
            avg_deaths_actual = float(stats['kda']  ('/')[1].strip())
            delta_deaths = round(target_deaths - avg_deaths_actual, 1) 
            st.metric("💀 Muertes Promedio", f"{avg_deaths_actual}", delta=delta_deaths, delta_color="normal")
        except:
            st.caption("Sin datos de KDA aún")

    except Exception as e:
        st.write("Juega partidas para ver métricas.")

# ============ MAIN APP ============
st.title("🛡️ LoL Tryhard Tracker")

if not st.session_state.config_saved:
    st.warning("⚠️ Confirma tu Riot ID en la barra lateral para empezar.")
    st.stop()

# Pestañas de navegación
tab1, tab2, tab3 = st.tabs(["📊 Diario & Sincronización", "🔎 Scout & Matchups", "🏆 Champion Pool"])

# --- TAB 1: DIARIO (Sincronización y Análisis Post-Game) ---
with tab1:
    # === GRÁFICO DE PROGRESO (LP) ===
    st.subheader("📈 Tendencia de LP")
    try:
        db = MatchDatabase()
        history_matches = db.get_recent_matches(20)
        db.close()

        if len(history_matches) > 1:
            # Invertir para ir del pasado al futuro
            history_matches = history_matches[::-1]
            
            dates = []
            lp_changes = []
            current_lp = 0
            
            for m in history_matches:
                change = m['lp_change'] if m['lp_change'] is not None else 0
                current_lp += change
                
                short_date = m['date'].strftime('%m-%d')
                dates.append(f"{short_date} ({m['champion']})")
                lp_changes.append(current_lp)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates, 
                y=lp_changes,
                mode='lines+markers',
                name='LP',
                line=dict(color='#00cc96', width=3),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                title="Evolución de LP Acumulado (Últimas 20)",
                xaxis_title="Partida",
                yaxis_title="LP Ganado/Perdido (Neto)",
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("Juega y registra LP en al menos 2 partidas para ver tu gráfica.")
            
    except Exception as e:
        st.error(f"No se pudo cargar el gráfico: {e}")

    # === SECCIÓN NUEVA: HEATMAP DE HORARIOS ===
    st.subheader("🕰️ Tu Horario Biológico (Winrate)")
    
    try:
        db = MatchDatabase()
        heat_data = db.get_activity_heatmap_data()
        db.close()

        if heat_data:
            days = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
            hours = [str(i) for i in range(24)]
            
            # Iniciamos con NaN para que lo vacío no se pinte de rojo
            z_data = np.full((7, 24), np.nan)
            text_data = [["" for _ in range(24)] for _ in range(7)]

            for d in heat_data:
                d_idx = int(d['weekday']) 
                h_idx = int(d['hour'])
                games = d['games']
                wins = d['wins']
                wr = int((wins/games)*100) if games > 0 else 0
                
                # El color (z) ahora es el Winrate
                z_data[d_idx][h_idx] = wr
                
                # El texto sigue mostrando detalles
                text_data[d_idx][h_idx] = f"WR: {wr}%<br>{games} Games<br>({wins}W - {games-wins}L)"

            fig_heat = go.Figure(data=go.Heatmap(
                z=z_data,
                x=hours,
                y=days,
                hoverongaps=False,
                colorscale='RdYlGn',  # Escala Rojo-Amarillo-Verde
                zmin=0,               # 0% es el rojo más fuerte
                zmax=100,             # 100% es el verde más fuerte
                text=text_data,
                hoverinfo='text'      # Solo mostrar nuestro texto personalizado
            ))

            fig_heat.update_layout(
                title="Rendimiento por Horario (Rojo=Lose / Verde=Win)",
                xaxis_title="Hora del día",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis=dict(dtick=2),
                plot_bgcolor='rgba(0,0,0,0)' # Fondo transparente para lo vacío
            )
            
            st.plotly_chart(fig_heat, use_container_width=True)
            st.caption("💡 **Interpretación:** Evita jugar en las horas rojas. Busca tus bloques verdes.")
        else:
            st.info("Juega más partidas para generar tu heatmap de rendimiento.")
            
    except Exception as e:
        st.error(f"Error en Heatmap: {e}")
    
    st.divider()
    col_sync, col_status = st.columns([1, 3])
    with col_sync:
        if st.button("🔄 Sincronizar Rankeds", type="primary", use_container_width=True):
            with st.spinner("Conectando con Riot..."):
                try:
                    # [MODIFICADO] Usamos la variable global API_KEY cargada desde .env
                    client = LoLClient(API_KEY, st.session_state.region)
                    db = MatchDatabase()
                    matches = client.get_recent_matches(st.session_state.riot_id, limit=5, queue=420)
                    
                    new_count = 0
                    for m in matches:
                        if db.save_match(m): 
                            new_count += 1
                    
                    if matches:
                        st.session_state.last_match_data = matches[0]
                        st.session_state.last_match_id = matches[0]['game_id']
                    
                    if new_count > 0:
                        st.success(f"✨ {new_count} partidas nuevas.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info("Todo actualizado.")
                    db.close()
                except Exception as e:
                    st.error(f"Error al sincronizar: {str(e)}")

    # FORMULARIO DE ANÁLISIS (La parte subjetiva)
    if st.session_state.last_match_data:
        m = st.session_state.last_match_data
        
        # Validar Constitución (Champion Pool)
        is_otp = m['champion_name'].lower() in main_champs
        
        st.divider()
        st.subheader(f"🔍 Análisis: {m['champion_name']} vs {m['enemy_champion']}")
        
        if not is_otp:
            st.error(f"⚠️ **ALERTA DE CONSTITUCIÓN**: Has jugado {m['champion_name']}, que NO está en tu lista de Mains ({', '.join(main_champs)}). ¡No improvises en Ranked!")

        # Formulario
        db = MatchDatabase()
        saved = db.get_match_by_id(st.session_state.last_match_id) or {}
        db.close()
        
        with st.form("post_game_analysis"):
            c1, c2, c3 = st.columns(3)
            with c1:
                lp = st.number_input("LP Ganados/Perdidos", value=saved.get('lp_change', 0))
            with c2:
                tilt = st.slider("Nivel de Tilt (1=Zen, 5=Rage)", 1, 5, saved.get('tilt_level', 1))
            with c3:
                impact_options = ["Carree (1v9)", "Hice mi trabajo", "Fui Carreado", "Invisible", "Inteé (Perdí la lane)"]
                impact_index = 0
                if saved.get('impact_rating') and saved['impact_rating'] in impact_options:
                    impact_index = impact_options.index(saved['impact_rating'])
                impact = st.selectbox("Tu Impacto", impact_options, index=impact_index)
            
            notes = st.text_area("🧠 Notas de Matchup (Estrategia para la próxima)", 
                               placeholder="Ej: Nivel 1 fuerte, cuidado con su E. Comprar Cortacuras temprano.",
                               value=saved.get('notes', ""))
            
            vod = st.checkbox("📺 VOD Review Realizada", value=bool(saved.get('vod_review', 0)))
            
            # Lógica de cierre automático
            if st.form_submit_button("💾 Guardar Análisis"):
                db = MatchDatabase()
                db.update_match_details(st.session_state.last_match_id, lp, tilt, impact, notes, vod)
                db.close()
                
                st.success("✅ Datos guardados. Cerrando formulario...")
                
                # 1. Esperamos un poquito para que te dé tiempo a leer el mensaje verde
                time.sleep(1.5)
                
                # 2. Borramos los datos de la "última partida" de la memoria temporal
                st.session_state.last_match_data = None
                st.session_state.last_match_id = None
                
                # 3. Forzamos la recarga de la página (ahora se verá limpia)
                st.rerun()

    # HISTORIAL RECIENTE CON EDICIÓN
    st.divider()
    st.subheader("📜 Historial de Partidas")
    db = MatchDatabase()
    recents = db.get_recent_matches(10)
    db.close()
    
    # Función auxiliar para Badges (La mantenemos igual)
    def get_badges(match):
        badges = []
        duration = match.get('game_duration_minutes', 30.0) or 30.0
        cs_min = match.get('cs_min', 0)
        deaths = match.get('deaths', 0)
        
        if cs_min >= 7.5: badges.append("🌾 CS God")
        elif cs_min < 5.0 and duration > 15: badges.append("⚠️ Farm Pobre")
        
        if deaths <= 2: badges.append("🧱 Muralla")
        elif deaths >= 7: badges.append("🤡 Feeder")
            
        if match.get('control_wards', 0) >= 3: badges.append("👁️ Visionary")
        
        kills = match.get('kills', 0)
        assists = match.get('assists', 0)
        safe_deaths = deaths if deaths > 0 else 1
        if (kills + assists) / safe_deaths > 4.0: badges.append("🔥 Carry")
            
        return " | ".join(badges)

    for r in recents:
        # Título del Expander
        color_emoji = "✅" if r['win'] else "❌"
        kda_display = f"{r['kills']}/{r['deaths']}/{r['assists']}"
        expander_title = f"{color_emoji} {r['champion']} vs {r['enemy_champion']} | {kda_display} | {r['date'].strftime('%d-%m %H:%M')}"
        
        with st.expander(expander_title):
            
            # === MODO EDICIÓN (Si le diste al botón editar de esta partida) ===
            if st.session_state.editing_match_id == r['game_id']:
                st.info(f"✍️ Editando partida: {r['champion']} vs {r['enemy_champion']}")
                
                with st.form(key=f"edit_form_{r['game_id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        new_lp = st.number_input("LP Change", value=r['lp_change'] if r['lp_change'] is not None else 0)
                    with c2:
                        new_tilt = st.slider("Tilt", 1, 5, r['tilt_level'] if r['tilt_level'] else 1)
                    with c3:
                        impact_opts = ["Carree (1v9)", "Hice mi trabajo", "Fui Carreado", "Invisible", "Inteé (Perdí la lane)"]
                        curr_impact = r['impact_rating'] if r['impact_rating'] in impact_opts else "Hice mi trabajo"
                        new_impact = st.selectbox("Impacto", impact_opts, index=impact_opts.index(curr_impact))
                    
                    new_notes = st.text_area("Notas", value=r['notes'] if r['notes'] else "")
                    new_vod = st.checkbox("VOD Review", value=bool(r['vod_review']))
                    
                    col_save, col_cancel = st.columns([1, 1])
                    with col_save:
                        if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                            db = MatchDatabase()
                            db.update_match_details(r['game_id'], new_lp, new_tilt, new_impact, new_notes, new_vod)
                            db.close()
                            st.success("Guardado!")
                            time.sleep(0.5)
                            # Cerrar modo edición
                            st.session_state.editing_match_id = None
                            st.rerun()
                            
                    with col_cancel:
                        # Truco: Un form_submit_button secundario actúa como cancelar si no hacemos nada
                        if st.form_submit_button("❌ Cancelar"):
                            st.session_state.editing_match_id = None
                            st.rerun()

            # === MODO VISUALIZACIÓN (Lo normal) ===
            else:
                badges_str = get_badges(r)
                if badges_str:
                    st.caption(f"🏅 Logros: :blue-background[{badges_str}]")
                
                colA, colB, colC = st.columns([2, 2, 1])
                
                with colA:
                    st.markdown(f"**CS/min:** {r['cs_min']}")
                    st.markdown(f"**Wards:** {r['control_wards']}")
                    if r['lp_change']:
                        lp_color = "green" if r['lp_change'] > 0 else "red"
                        st.markdown(f"**LP:** :{lp_color}[{r['lp_change']}]")
                
                with colB:
                    st.markdown(f"**Tilt:** {r['tilt_level']}/5")
                    st.markdown(f"**Impacto:** {r['impact_rating']}")
                    if r['vod_review']: st.markdown("✅ **VOD**")

                with colC:
                    # EL BOTÓN DE EDITAR
                    if st.button("✏️ Editar", key=f"btn_edit_{r['game_id']}"):
                        st.session_state.editing_match_id = r['game_id']
                        st.rerun()

                if r['notes']:
                    st.info(f"📝 {r['notes']}")
                else:
                    st.caption("Sin notas tácticas.")

# --- TAB 2: SCOUT (La Guía de Estrategia) ---
with tab2:
    st.subheader("🔎 Scout de Matchups")
    
    # 1. SECCIÓN NUEVA: DETECTOR DE NEMESIS
    try:
        db = MatchDatabase()
        nemesis_list = db.get_nemesis_list(min_games=2)
        db.close()
        
        if nemesis_list:
            st.markdown("### ⚠️ Tus Pesadillas (Nemesis)")
            st.caption("Rivales contra los que estadísticamente sufres más.")
            
            cols = st.columns(min(len(nemesis_list), 5))
            
            for idx, col in enumerate(cols):
                if idx < len(nemesis_list):
                    n = nemesis_list[idx]
                    
                    wr = int(n['winrate'])
                    wr_color = "red" if wr < 40 else "orange"
                    
                    with col:
                        with st.container(border=True):
                            st.markdown(f"**{n['enemy_champion']}**")
                            st.markdown(f"📉 WR: :{wr_color}[{wr}%]")
                            st.caption(f"Partidas: {n['games']} ({n['wins']}W)")
                            st.markdown(f"💀 Deaths: **{round(n['avg_deaths'], 1)}**")
            
            st.divider()
    except Exception as e:
        st.error(f"Error cargando Nemesis: {e}")

    # 2. SECCIÓN ORIGINAL: BÚSQUEDA MANUAL
    st.markdown("Busca en tu base de conocimiento antes de que empiece la línea.")
    
    col_search1, col_search2 = st.columns(2)
    with col_search1:
        my_champ_search = st.text_input("Yo juego con...", placeholder="Ej: Jax")
    with col_search2:
        enemy_champ_search = st.text_input("Contra...", placeholder="Ej: Renekton")
        
    if my_champ_search or enemy_champ_search:
        db = MatchDatabase()
        results = []
        if my_champ_search and enemy_champ_search:
            results = db.get_matchup_notes(my_champ_search, enemy_champ_search)
        elif enemy_champ_search:
            results = db.get_matches_vs_enemy(f"%{enemy_champ_search}%")
            
        db.close()
        
        if results:
            st.success(f"Encontradas {len(results)} partidas previas.")
            for res in results:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        st.markdown(f"**{res['champion']}** vs **{res['enemy_champion']}**")
                        st.caption(res['date'].strftime('%Y-%m-%d'))
                        result_emoji = "✅" if res['win'] else "❌"
                        st.markdown(f"{result_emoji} {'Ganada' if res['win'] else 'Perdida'}")
                    with c2:
                        if res['notes']:
                            st.info(f"💡 {res['notes']}")
                        else:
                            st.markdown("*Sin notas registradas*")
        else:
            st.warning("No tienes datos previos de este enfrentamiento. ¡Juega con cuidado y anota todo al final!")

# --- TAB 3: CHAMPION POOL ---
with tab3:
    st.subheader("🏆 Rendimiento de Champion Pool")
    try:
        db = MatchDatabase()
        stats = db.get_champion_performance()
        db.close()
        
        if stats:
            df = pd.DataFrame(stats)
            current_patch = "14.24.1"
            df['Icono'] = df['champion'].apply(lambda x: f"https://ddragon.leagueoflegends.com/cdn/{current_patch}/img/champion/{x}.png")
            
            df = df[['Icono', 'champion', 'games_played', 'winrate', 'kda_ratio', 'avg_cs_min']]
            
            st.dataframe(
                df,
                column_config={
                    "Icono": st.column_config.ImageColumn("Champ"),
                    "winrate": st.column_config.ProgressColumn("Winrate", format="%.1f%%", min_value=0, max_value=100),
                    "kda_ratio": st.column_config.NumberColumn("KDA", format="%.2f"),
                    "avg_cs_min": st.column_config.NumberColumn("CS/min", format="%.1f 🌾"),
                },
                hide_index=True,
                use_container_width=True,
                height=500
            )
        else:
            st.info("Aún no hay estadísticas suficientes.")
    except Exception as e:
        st.error(f"Error cargando stats: {e}")