import streamlit as st
from riot_client import LoLClient
from database import MatchDatabase
from riotwatcher import ApiError
import pandas as pd

st.set_page_config(page_title="LoL Performance Tracker", page_icon="🔥", layout="wide")

# Inicializar estados
if 'api_key' not in st.session_state: st.session_state.api_key = ""
if 'riot_id' not in st.session_state: st.session_state.riot_id = ""
if 'region' not in st.session_state: st.session_state.region = "EUW1"
if 'last_match_data' not in st.session_state: st.session_state.last_match_data = None
if 'last_match_id' not in st.session_state: st.session_state.last_match_id = None
if 'config_saved' not in st.session_state: st.session_state.config_saved = False
if 'matchup_history' not in st.session_state: st.session_state.matchup_history = None

# --- SIDEBAR ---
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
    
    # LA CONSTITUCIÓN
    try:
        db = MatchDatabase()
        last_3 = db.get_recent_matches(3)
        if len(last_3) >= 1:
            wins = sum(1 for m in last_3 if m['win'])
            losses = 0
            for m in last_3:
                if not m['win']: losses += 1
                else: break
            
            if losses >= 2: st.error(f"⛔ STOP: {losses} Derrotas seguidas.")
            elif wins == 3 and len(last_3)==3: st.success("🔥 ON FIRE: 3 Victorias.")
            else: st.info(f"Últimas: {' '.join(['✅' if m['win'] else '❌' for m in last_3])}")
    except: pass

    # SCOUT PRE-GAME
    st.markdown("---")
    st.markdown("### 🔍 Scout Pre-Partida")
    scout_enemy = st.text_input("¿Contra quién vas?", placeholder="Ej: Zed")
    if st.button("Buscar Consejos"):
        if scout_enemy:
            scout_matches = db.get_matches_vs_enemy(scout_enemy)
            if scout_matches:
                wins = sum(1 for m in scout_matches if m['win'])
                total = len(scout_matches)
                st.write(f"**Historial vs {scout_enemy}:** {wins}W - {total-wins}L ({int(wins/total*100)}%)")
                for m in scout_matches[:3]:
                    if m['notes']: st.info(f"📝 ({m['champion']}): {m['notes']}")
            else: st.warning(f"Sin datos vs {scout_enemy}.")
    db.close()

# --- MAIN ---
st.title("🔥 LoL Performance Tracker")

if not st.session_state.config_saved:
    st.warning("⚠️ Configura tu cuenta en la barra lateral.")
    st.stop()

# BOTÓN DE SINCRONIZACIÓN
if st.button("🔄 Sincronizar (Últimas 5)", use_container_width=True, type="primary"):
    with st.spinner("Sincronizando historial..."):
        try:
            client = LoLClient(st.session_state.api_key, st.session_state.region)
            db = MatchDatabase()
            
            matches = client.get_recent_matches(st.session_state.riot_id, limit=5)
            
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
                st.success(f"✨ Se han importado {new_count} partidas nuevas.")
            else:
                st.info("📌 Todo actualizado. No hay partidas nuevas.")
            db.close()
        except Exception as e:
            st.error(f"❌ Error: {e}")

# --- ZONA DE EDICIÓN ACTIVA ---
if st.session_state.last_match_data:
    m = st.session_state.last_match_data
    
    # Header Dinámico para saber qué estamos tocando
    st.markdown(f"### ✏️ Editando: {m['champion_name']} vs {m['enemy_champion']} ({m['date']})")
    
    # Tarjeta Resumen
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Campeón", m['champion_name'])
    c2.metric("KDA", f"{m['kills']}/{m['deaths']}/{m['assists']}")
    c3.metric("Resultado", "Victoria 🏆" if m['win'] else "Derrota 💀")
    c4.metric("Vs", m['enemy_champion'])
    
    if st.session_state.matchup_history:
        history = [h for h in st.session_state.matchup_history if h['date'] != m['date']]
        if history:
            st.info(f"💡 Historial vs {m['enemy_champion']}: {len(history)} partidas previas.")
            if history[0]['notes']: st.warning(f"📝 Nota anterior: {history[0]['notes']}")
    
    st.divider()
    
    # Formulario
    db = MatchDatabase()
    # Recuperamos los datos de LA PARTIDA SELECCIONADA (last_match_id)
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
            
        if st.form_submit_button("💾 Guardar Análisis"):
            db = MatchDatabase()
            db.update_match_details(st.session_state.last_match_id, lp, tilt, impact, notes, vod)
            st.success("✅ Guardado! Sigue editando o selecciona otra partida abajo.")
            # Quitamos el rerun automático aquí para que veas el mensaje de éxito, 
            # o lo dejamos si quieres ver el cambio inmediato en el historial.
            # st.rerun() 

# GRÁFICO
st.divider()
try:
    db = MatchDatabase()
    matches_data = db.get_recent_matches(10)
    if matches_data:
        df = pd.DataFrame(matches_data).iloc[::-1]
        st.subheader("📈 Evolución de Farm (CS/min)")
        st.line_chart(df, x="date", y="cs_min")
    db.close()
except: pass

# --- HISTORIAL INTERACTIVO ---
st.divider()
st.subheader("📜 Historial (Selecciona para editar)")
try:
    db = MatchDatabase()
    recents = db.get_recent_matches(10) # Traemos las últimas 10
    
    if recents:
        for r in recents:
            kda_ratio = ((r['kills'] + r['assists']) / r['deaths']) if r['deaths'] > 0 else (r['kills'] + r['assists'])
            expander_title = f"{'🏆' if r['win'] else '💀'} {r['champion']} ({r['kills']}/{r['deaths']}/{r['assists']}) - vs {r['enemy_champion']} | {r['date']}"
            
            with st.expander(expander_title):
                # Botón de Acción
                # Usamos una clave única (game_id) para que cada botón sea distinto
                if st.button(f"✏️ Editar / Ver Detalles", key=f"btn_{r['game_id']}", use_container_width=True):
                    # AL CLICAR: Actualizamos el estado de la sesión
                    st.session_state.last_match_data = r
                    st.session_state.last_match_id = r['game_id']
                    # Buscamos historial de matchup para la partida seleccionada
                    st.session_state.matchup_history = db.get_matchup_notes(r['champion'], r['enemy_champion'])
                    st.rerun() # Recargamos la página para que el formulario de arriba se actualice
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("KDA", f"{r['kills']}/{r['deaths']}/{r['assists']}", f"{kda_ratio:.2f}")
                c2.metric("CS Total", r['cs_total'], f"{r['cs_min']:.1f}/min")
                c3.metric("Wards", r['control_wards'])
                lp_val = r['lp_change'] if r['lp_change'] is not None else 0
                c4.metric("LP", f"{'+' if lp_val > 0 else ''}{lp_val}", delta_color="normal" if lp_val >=0 else "inverse")
                
                st.divider()
                c1, c2 = st.columns(2)
                c1.markdown(f"**Tilt:** {r['tilt_level']}/5")
                c2.markdown(f"**Impacto:** {r['impact_rating']}")
                if r['notes']: st.info(f"📝 {r['notes']}")
    db.close()
except: pass