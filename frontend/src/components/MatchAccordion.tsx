import { useState } from 'react'
import { AlertTriangle, ArrowUp, CheckCircle2, Database, Loader2, XCircle } from 'lucide-react'
import type { UIMatch, UIParticipant, MatchReviewUpdate } from '../data/types'
import { IMPACT_RATINGS, TILT_LEVELS, DDragon } from '../data/constants'
import { computeOkrResults } from '../data/okr'
import { useIcons } from '../hooks/useMetadata'
import { useSettings } from '../hooks/useSettings'
import { useScoutOpponent } from '../hooks/useScoutOpponent'

function SpellIcon({ id }: { id: number }) {
  const icons = useIcons()
  const spell = icons.spell(id)
  if (!spell) return null
  return (
    <img
      src={spell.url}
      alt={spell.name ?? 'Hechizo'}
      title={spell.name}
      className="h-[15px] w-[15px] rounded-sm border border-hairline"
    />
  )
}

function ItemBox({ id }: { id: number }) {
  const icons = useIcons()
  const item = icons.item(id)
  return (
    <div
      className="flex h-5 w-5 shrink-0 items-center justify-center overflow-hidden rounded-sm border border-hairline/80 bg-surface-2"
      title={item?.name || undefined}
    >
      {item && (
        <img
          src={item.url}
          alt={item.name ?? ''}
          className="h-full w-full"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
      )}
    </div>
  )
}

// Grid de cada jugador: [campeón+spells] [nombre] [items+trinket] [KDA/CS] [barra daño] [rating].
const PLAYER_GRID =
  'grid grid-cols-[auto_minmax(120px,180px)_auto_minmax(140px,auto)_minmax(150px,1fr)_48px] items-center gap-x-3'

function PlayerRow({
  player,
  isYou,
  maxDamage,
  duration,
}: {
  player: UIParticipant
  isYou: boolean
  maxDamage: number
  duration: number
}) {
  const icons = useIcons()
  const kdaRatio = player.deaths === 0 ? null : (player.kills + player.assists) / player.deaths
  const kdaLabel = kdaRatio === null ? 'Perfect' : kdaRatio.toFixed(2)
  const kdaColor =
    kdaRatio === null || kdaRatio >= 4
      ? 'text-emerald-400'
      : kdaRatio >= 2.5
        ? 'text-text-body'
        : kdaRatio >= 1.5
          ? 'text-yellow-400'
          : 'text-red-400'
  const csPerMin = player.cs / Math.max(duration, 1)
  const damagePct = maxDamage > 0 ? Math.round((player.total_damage / maxDamage) * 100) : 0
  const champIcon = icons.champion(player.champion_name)

  return (
    <div
      className={`${PLAYER_GRID} min-w-[720px] rounded-md px-3 py-2 ${
        isYou
          ? 'bg-accent-primary/[0.08] ring-1 ring-accent-primary/40'
          : player.team_id === 100
            ? 'bg-blue-500/[0.04]'
            : 'bg-red-500/[0.04]'
      }`}
    >
      {/* Col 1: Campeón + Summoner Spells apilados al lado */}
      <div className="flex items-center gap-1.5">
        <img
          src={champIcon.url}
          alt={player.champion_name}
          title={champIcon.name}
          className="h-9 w-9 rounded-md border border-hairline"
          onError={(e) => {
            (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
          }}
        />
        <div className="flex flex-col gap-0.5">
          {player.summoner_spells.slice(0, 2).map((id, i) => (
            <SpellIcon key={`${id}-${i}`} id={id} />
          ))}
        </div>
      </div>

      {/* Col 2: Jugador (Riot ID) */}
      <div className="min-w-0">
        <span
          className={`block truncate text-sm font-semibold ${isYou ? 'text-accent-primary' : 'text-gray-200'}`}
          title={player.player_name}
        >
          {player.player_name}
        </span>
        <span className="block truncate text-xs text-text-mute">{player.champion_name}</span>
      </div>

      {/* Col 3: Items (6 juntos) + Trinket separado */}
      <div className="flex items-center gap-0.5">
        {player.items.slice(0, 6).map((id, i) => (
          <ItemBox key={`item-${i}`} id={id} />
        ))}
        <div className="ml-2">
          <ItemBox id={player.items[6] ?? 0} />
        </div>
      </div>

      {/* Col 4: Stats base */}
      <div>
        <span className="font-mono text-base font-bold text-white">
          {player.kills}/{player.deaths}/{player.assists}
        </span>
        <p className="font-mono text-xs leading-tight">
          <span className={kdaColor}>{kdaLabel} KDA</span>
          <span className="text-text-mute"> · {csPerMin.toFixed(1)} cs/m</span>
        </p>
      </div>

      {/* Col 5: Barra de daño (relativa al máximo de la partida) */}
      <div className="min-w-[130px]">
        <p className="text-right font-mono text-xs leading-none text-text-mute">
          {player.total_damage.toLocaleString()}
        </p>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-surface-2">
          <div
            className={`h-full rounded ${player.team_id === 100 ? 'bg-blue-500' : 'bg-red-500'}`}
            style={{ width: `${damagePct}%` }}
          />
        </div>
      </div>

      {/* Col 6: Rating universal (calculado en backend) */}
      <div className="text-center">
        <span
          className={`font-mono text-xl font-black leading-none ${
            player.rating >= 80
              ? 'text-orange-400'
              : player.rating >= 60
                ? 'text-emerald-400'
                : player.rating >= 40
                  ? 'text-text-body'
                  : 'text-red-400'
          }`}
        >
          {player.rating.toFixed(1)}
        </span>
      </div>
    </div>
  )
}

function OkrStrip({ match, me }: { match: UIMatch; me: UIParticipant }) {
  const { data: settings } = useSettings()
  if (!settings) return null

  const results = computeOkrResults(me, match, {
    target_dpm: settings.target_dpm,
    target_kp_percent: settings.target_kp_percent,
    target_vision_score: settings.target_vision_score,
  })

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-hairline bg-surface-1 px-3 py-2">
      <span className="text-xs font-bold uppercase tracking-wider text-accent-primary">🎯 OKR</span>
      {results.map((item) => (
        <span
          key={item.label}
          className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold ${
            item.met ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
          }`}
        >
          {item.met ? <CheckCircle2 className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />}
          {item.label} {item.current}/{item.target}
        </span>
      ))}
    </div>
  )
}

function computeEloFactors(me: UIParticipant, match: UIMatch) {
  const duration = Math.max(match.game_duration_minutes, 1)
  const positive: { factor: string; value: string; detail: string }[] = []
  const negative: { factor: string; value: string; detail: string }[] = []

  const kda = me.deaths === 0 ? 99 : (me.kills + me.assists) / me.deaths
  if (kda >= 5) {
    positive.push({ factor: 'Exceptional KDA', value: `+${(kda * 1.5).toFixed(1)}`, detail: `${me.kills}/${me.deaths}/${me.assists} (${kda.toFixed(2)} ratio)` })
  } else if (kda >= 3) {
    positive.push({ factor: 'Good KDA', value: `+${(kda * 0.8).toFixed(1)}`, detail: `${me.kills}/${me.deaths}/${me.assists} (${kda.toFixed(2)} ratio)` })
  } else if (kda < 1.5) {
    negative.push({ factor: 'Poor KDA', value: `${(-5 + kda).toFixed(1)}`, detail: `${me.kills}/${me.deaths}/${me.assists} (${kda.toFixed(2)} ratio)` })
  }

  const csMin = me.cs / duration
  if (csMin >= 8.5) {
    positive.push({ factor: 'Excellent CS/min', value: `+${((csMin - 7) * 2).toFixed(1)}`, detail: `${csMin.toFixed(1)} CS/min (${me.cs} total)` })
  } else if (csMin >= 7) {
    positive.push({ factor: 'Above Average CS', value: `+${((csMin - 7) * 1.5).toFixed(1)}`, detail: `${csMin.toFixed(1)} CS/min` })
  } else if (csMin < 6) {
    negative.push({ factor: 'Low CS/min', value: `${-((7 - csMin) * 2).toFixed(1)}`, detail: `${csMin.toFixed(1)} CS/min (target: 7.5)` })
  }

  const team = match.participants?.filter((p) => p.team_id === me.team_id) ?? []
  const teamKills = team.reduce((s, p) => s + p.kills, 0)
  const kp = teamKills > 0 ? (me.kills + me.assists) / teamKills : 0
  if (kp >= 0.65) {
    positive.push({ factor: 'High Kill Participation', value: `+${((kp - 0.5) * 15).toFixed(1)}`, detail: `${(kp * 100).toFixed(0)}% of team kills` })
  } else if (kp < 0.4) {
    negative.push({ factor: 'Low Kill Participation', value: `${-((0.5 - kp) * 10).toFixed(1)}`, detail: `${(kp * 100).toFixed(0)}% of team kills` })
  }

  if (me.deaths <= 2 && match.win) {
    positive.push({ factor: 'Clean Game (Low Deaths)', value: '+3.0', detail: `Only ${me.deaths} deaths in a win` })
  } else if (me.deaths >= 6) {
    negative.push({ factor: 'High Deaths', value: `${-((me.deaths - 3) * 2).toFixed(1)}`, detail: `${me.deaths} deaths this game` })
  }

  const visionMin = me.vision_score / duration
  if (visionMin >= 1.5) {
    positive.push({ factor: 'Strong Vision Control', value: '+2.0', detail: `${visionMin.toFixed(1)} vision score/min` })
  }

  if (match.control_wards >= 3) {
    positive.push({ factor: 'Objective Control', value: `+${(match.control_wards * 0.5).toFixed(1)}`, detail: `${match.control_wards} control wards placed` })
  }

  const dpm = me.total_damage / duration
  if (dpm >= 700) {
    positive.push({ factor: 'High Damage Output', value: '+3.5', detail: `${Math.round(dpm)} DPM` })
  } else if (dpm < 400) {
    negative.push({ factor: 'Low Damage Output', value: '-2.0', detail: `${Math.round(dpm)} DPM` })
  }

  if (match.win) {
    positive.push({ factor: 'Victory Bonus', value: '+15.0', detail: 'Win' })
  } else {
    negative.push({ factor: 'Defeat Penalty', value: '-15.0', detail: 'Loss' })
  }

  return { positive, negative }
}

function ScoutView({ match }: { match: UIMatch }) {
  // El tab ya está abierto, así que la query corre (enabled=true aquí; el resto del accordion
  // no llama a este hook, no hay llamadas a Riot por match de la tabla).
  const { data, isLoading, isError, error } = useScoutOpponent(match.game_id, true)
  const icons = useIcons()

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-hairline bg-surface-1 px-4 py-10 text-center">
        <Loader2 className="h-5 w-5 animate-spin text-text-mute" />
        <p className="text-xs text-text-mute">Consultando maestrías del rival en Riot...</p>
      </div>
    )
  }

  if (isError || !data) {
    const detail = error && typeof error === 'object' && 'response' in error
      ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : undefined
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/[0.04] px-4 py-10 text-center">
        <AlertTriangle className="h-5 w-5 text-red-400" />
        <p className="text-xs text-text-mute">
          {detail ?? 'No se pudo escoutear al rival. ¿La API key de Riot sigue válida?'}
        </p>
      </div>
    )
  }

  const top = data.top_champions ?? []
  const otp = data.opponent_champion && top[0]?.champion === data.opponent_champion
  const firstTime = top.length > 0 && data.opponent_champion
    && !top.some((c) => c.champion === data.opponent_champion)

  return (
    <div className="space-y-3">
      {/* Cabecera del rival */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-hairline bg-surface-1 px-3 py-2.5">
        <div className="min-w-0">
          <div className="truncate text-sm font-bold text-white">
            {data.opponent_name || 'Rival de línea'}
            {data.opponent_champion && (
              <span className="ml-2 font-mono text-xs font-semibold text-accent-primary">
                jugó {data.opponent_champion}
              </span>
            )}
          </div>
          {data.opponent_role && (
            <span className="text-xs text-text-mute">Rol: {data.opponent_role}</span>
          )}
        </div>
        <span
          className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wider ${
            data.cached
              ? 'bg-surface-2 text-text-mute'
              : 'bg-emerald-500/10 text-emerald-400'
          }`}
          title={data.cached ? 'Servido desde la caché de DB (sin golpear a Riot)' : 'Llamada fresca a Riot'}
        >
          {data.cached ? '🕓 Con caché' : '⚡ Datos frescos'}
        </span>
      </div>

      {/* Contenido */}
      {data.note ? (
        <div className="rounded-lg border border-blue-500/20 bg-blue-500/[0.04] px-4 py-6 text-center">
          <p className="text-xs text-text-mute">{data.note}</p>
        </div>
      ) : top.length === 0 ? (
        <div className="rounded-lg border border-dashed border-hairline bg-surface-1 px-4 py-8 text-center">
          <p className="text-xs text-text-mute">Sin maestrías para este rival.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {top.map((c, i) => (
              <div
                key={c.champion_key}
                className={`rounded-lg border p-3 text-center ${
                  i === 0
                    ? 'border-accent-primary/40 bg-accent-primary/[0.06]'
                    : 'border-hairline bg-surface-2'
                }`}
              >
                <img
                  src={icons.champion(c.champion).url}
                  alt={c.champion}
                  title={icons.champion(c.champion).name}
                  className="mx-auto mb-1.5 h-12 w-12 rounded-lg border border-hairline"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                  }}
                />
                <p className="truncate text-sm font-bold text-white">
                  {i === 0 && <span className="mr-1">👑</span>}
                  {c.champion}
                </p>
                <p className="font-mono text-xs text-text-mute">
                  M{c.mastery_level} · {c.points.toLocaleString()} pts
                </p>
              </div>
            ))}
          </div>

          {/* Veredicto: ¿OTP o first time? */}
          <div className="rounded-lg border border-hairline bg-surface-1 px-3 py-2.5 text-xs leading-relaxed text-text-mute">
            {otp ? (
              <span>
                ⚠️ <b className="text-orange-400">{data.opponent_name || 'El rival'}</b> se jugó{' '}
                <b className="text-white">{data.opponent_champion}</b>, su campeón con más maestrías:{' '}
                <b className="text-orange-400">OTP confirmado</b>.
              </span>
            ) : firstTime ? (
              <span>
                📝 {data.opponent_champion} <b className="text-white">no está entre sus 3 campeones dominados</b>:
                es un posible first time (o un counter específico).
              </span>
            ) : (
              <span>
                🎯 {data.opponent_champion} sí está entre sus campeones jugados — el dato empieza a ser fiable.
              </span>
            )}
          </div>
        </>
      )}
    </div>
  )
}

interface Props {
  match: UIMatch
  onReviewSave: (gameId: string, data: MatchReviewUpdate) => void
  isSaving: boolean
}

export default function MatchAccordion({ match, onReviewSave, isSaving }: Props) {
  const [activeTab, setActiveTab] = useState<'match' | 'stats' | 'elo' | 'review' | 'scout'>('match')
  const [isEditing, setIsEditing] = useState(false)

  // Form state
  const [lpChange, setLpChange] = useState(match.lp_change?.toString() ?? '')
  const [tiltLevel, setTiltLevel] = useState(match.tilt_level ?? 0)
  const [impactRating, setImpactRating] = useState(match.impact_rating ?? '')
  const [notes, setNotes] = useState(match.notes ?? '')
  const [vodReview, setVodReview] = useState(match.vod_review ?? false)

  const hasReview = match.lp_change !== null || match.tilt_level !== null || match.impact_rating !== null || match.notes !== null || match.vod_review

  const players = match.participants ?? []
  const blueTeam = players.filter((p) => p.team_id === 100)
  const redTeam = players.filter((p) => p.team_id === 200)
  const duration = Math.max(match.game_duration_minutes, 1)

  // "Yo" dentro de los 10: mientras el backend no exponga nuestro puuid en /api/config,
  // localizamos por campeón (única partida del usuario en cada fila de la tabla).
  const me = players.find((p) => p.champion_name.toLowerCase() === match.champion.toLowerCase())
  const isMe = (p: UIParticipant) => p === me

  // Daño máximo de LOS 10 jugadores de ESTA partida: base de las barras relativas.
  const maxDamage = Math.max(1, ...players.map((p) => p.total_damage))

  const tabs = [
    { key: 'match' as const, label: '⚔️ Match' },
    { key: 'stats' as const, label: '📊 Full Stats' },
    { key: 'elo' as const, label: '📈 ELO / Notes' },
    { key: 'scout' as const, label: '🔎 Escout' },
    { key: 'review' as const, label: hasReview ? '✅ Review' : '📝 Review' },
  ]

  const handleSave = () => {
    const data: MatchReviewUpdate = {
      lp_change: lpChange !== '' ? parseInt(lpChange, 10) : null,
      tilt_level: tiltLevel > 0 ? tiltLevel : null,
      impact_rating: impactRating || null,
      notes: notes.trim() || null,
      vod_review: vodReview,
    }
    onReviewSave(match.game_id, data)
  }

  // Línea base global del rol (viene del backend por participante): la comparativa de Full Stats.
  // Las filas legacy sin participants no llevan `expected_stats`, y entonces se pintan igual.
  const exp = me?.expected_stats ?? null
  const beatBaseline = (real: number, target: number | undefined): boolean =>
    target !== undefined && real >= target

  const stats: {
    label: string
    value: string
    sub: string
    color: string
    expected?: string
    beat?: boolean
  }[] = (() => {
    if (!me) {
      return [
        { label: 'KDA', value: `${match.kills}/${match.deaths}/${match.assists}`, sub: `${match.kda_ratio.toFixed(2)} ratio`, color: 'text-white' },
        { label: 'CS/min', value: match.cs_min.toFixed(1), sub: `${match.cs_total} total CS`, color: 'text-white' },
        { label: 'KP%', value: `${(match.kill_participation * 100).toFixed(0)}%`, sub: 'Kill Participation', color: 'text-accent-primary' },
        { label: 'DPM', value: `${match.dpm}`, sub: 'Estimated DPM', color: 'text-white' },
        { label: 'Control Wards', value: `${match.control_wards}`, sub: 'Placed', color: 'text-white' },
        { label: 'Duration', value: match.duration_display, sub: 'Game length', color: 'text-white' },
        { label: 'Role', value: match.role, sub: match.enemy_champion !== 'Unknown' ? `vs ${match.enemy_champion}` : '', color: 'text-white' },
        { label: 'Queue', value: match.queue_id === 420 ? 'Ranked' : match.queue_id === 400 ? 'Normal' : 'Other', sub: `ID: ${match.queue_id ?? 'N/A'}`, color: 'text-white' },
      ]
    }
    return [
      { label: 'KDA', value: `${me.kills}/${me.deaths}/${me.assists}`, sub: match.kda_ratio === 99 ? 'Perfect' : `${match.kda_ratio.toFixed(2)} ratio`, color: match.kda_ratio >= 5 ? 'text-emerald-400' : match.kda_ratio >= 3 ? 'text-white' : 'text-red-400' },
      // Métricas contra la ladder: valor real destacado + línea base del rol en gris (Exp: …)
      {
        label: 'CS/min',
        value: match.cs_min.toFixed(1),
        sub: `${match.cs_total} total CS`,
        color: match.cs_min >= 7.5 ? 'text-emerald-400' : match.cs_min >= 6 ? 'text-white' : 'text-orange-400',
        expected: exp ? `Exp: ${exp.cs_per_min.toFixed(1)}` : undefined,
        beat: beatBaseline(match.cs_min, exp?.cs_per_min),
      },
      {
        label: 'KP%',
        value: `${(match.kill_participation * 100).toFixed(0)}%`,
        sub: 'Kill Participation',
        color: match.kill_participation >= 0.6 ? 'text-accent-primary' : 'text-text-body',
        expected: exp ? `Exp: ${(exp.kill_participation * 100).toFixed(0)}%` : undefined,
        beat: beatBaseline(match.kill_participation, exp?.kill_participation),
      },
      {
        label: 'DPM',
        value: `${match.dpm}`,
        sub: 'Damage Per Minute',
        color: match.dpm >= 700 ? 'text-orange-400' : match.dpm >= 500 ? 'text-white' : 'text-text-mute',
        expected: exp ? `Exp: ${exp.dpm}` : undefined,
        beat: beatBaseline(match.dpm, exp?.dpm),
      },
      {
        label: 'Vision/min',
        value: (me.vision_score / duration).toFixed(1),
        sub: `Score: ${me.vision_score} · Wards: ${match.control_wards}`,
        color: me.vision_score / duration >= 1.5 ? 'text-emerald-400' : 'text-white',
        expected: exp ? `Exp: ${(exp.vision_score / duration).toFixed(1)}` : undefined,
        beat: beatBaseline(me.vision_score, exp?.vision_score),
      },
      { label: 'Gold/min', value: Math.round(me.gold_earned / duration).toString(), sub: `${me.gold_earned.toLocaleString()} total gold`, color: 'text-yellow-400' },
      { label: 'Dmg Taken/min', value: Math.round(me.total_damage_taken / duration).toString(), sub: `${(me.total_damage_taken / 1000).toFixed(1)}k total taken`, color: 'text-white' },
      { label: 'Dmg Dealt', value: `${(me.total_damage / 1000).toFixed(1)}k`, sub: `${Math.round(me.total_damage / duration)} DPM to champs`, color: match.dpm >= 700 ? 'text-orange-400' : 'text-white' },
    ]
  })()

  const elo = (() => {
    return me ? computeEloFactors(me, match) : { positive: [], negative: [] }
  })()
  const positiveNet = elo.positive.reduce((s, f) => s + parseFloat(f.value), 0)
  const negativeNet = elo.negative.reduce((s, f) => s + parseFloat(f.value), 0)

  return (
    <div>
      {/* Tab Bar */}
      <div className="mb-3 flex gap-1 rounded-lg bg-canvas p-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
              activeTab === tab.key
                ? 'bg-accent-primary text-white shadow-[0_0_24px_rgba(168,85,247,0.35)]'
                : 'text-text-mute hover:text-text-body'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* OKR strip: validación instantánea contra objetivos en cada partida */}
      {me && <OkrStrip match={match} me={me} />}

      {/* Match View */}
      {activeTab === 'match' && (
        <div className="space-y-4">
          {players.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-hairline bg-surface-1 px-4 py-10 text-center">
              <Database className="mb-1 h-6 w-6 text-text-mute" />
              <p className="text-sm font-semibold text-text-mute">
                Datos detallados no disponibles para esta partida (Legacy)
              </p>
              <p className="text-xs text-text-mute">
                Sincronizada antes de guardar el detalle por participante.
              </p>
            </div>
          ) : (
            ([
              {
                label: 'BLUE SIDE',
                players: blueTeam,
                header: 'bg-blue-500/10',
                dot: 'bg-blue-400',
                text: 'text-blue-400',
              },
              {
                label: 'RED SIDE',
                players: redTeam,
                header: 'bg-red-500/10',
                dot: 'bg-red-400',
                text: 'text-red-400',
              },
            ]).map((side) => (
              <div key={side.label}>
                <div className={`mb-2 flex items-center gap-2 rounded-md px-2.5 py-1.5 ${side.header}`}>
                  <span className={`h-2 w-2 rounded-full ${side.dot}`} />
                  <span className={`text-xs font-bold ${side.text}`}>
                    {side.label}
                    {side.players.length > 0 && side.players[0].win ? ' — VICTORY' : ''}
                  </span>
                  <span className="ml-auto font-mono text-xs text-text-mute">
                    {side.players.reduce((s, p) => s + p.kills, 0)} kills
                  </span>
                </div>
                <div className="space-y-1 overflow-x-auto pb-0.5">
                  {side.players.map((p, i) => (
                    <PlayerRow
                      key={p.puuid || `${side.label}-${i}`}
                      player={p}
                      isYou={isMe(p)}
                      maxDamage={maxDamage}
                      duration={duration}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
          <div className="text-center text-xs text-text-mute">
            {match.champion} vs {match.enemy_champion} · {match.duration_display} · {match.game_id}
          </div>
        </div>
      )}

      {/* Full Stats View */}
      {activeTab === 'stats' && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-lg border border-hairline bg-surface-2 p-3">
              <span className="text-xs font-bold uppercase tracking-wider text-text-mute">{s.label}</span>
              <p className={`font-mono text-xl font-black ${s.color}`}>
                {s.value}
                {s.beat && (
                  <ArrowUp className="ml-1 inline-block h-3.5 w-3.5 text-emerald-400" />
                )}
              </p>
              <span className="text-xs text-text-mute">{s.sub}</span>
              {s.expected && (
                <span className="mt-1 block border-t border-hairline pt-1 text-xs text-text-mute">
                  {s.expected}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Scout del Rival View */}
      {activeTab === 'scout' && <ScoutView match={match} />}

      {/* ELO / Notes View */}
      {activeTab === 'elo' && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
            <h4 className="mb-3 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-emerald-400">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-xs">▲</span>
              Gave You Points
            </h4>
            {elo.positive.length === 0 ? (
                <p className="text-xs text-text-mute italic">No positive factors this game</p>
            ) : (
              <>
                <div className="space-y-2">
                  {elo.positive.map((f) => (
                    <div key={f.factor} className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-medium text-text-body">{f.factor}</span>
                        <span className="block text-xs text-text-mute">{f.detail}</span>
                      </div>
                      <span className="font-mono text-sm font-bold text-emerald-400">{f.value}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 border-t border-emerald-500/10 pt-2 text-right">
                  <span className="text-xs text-text-mute">Net: </span>
                  <span className="font-mono text-sm font-black text-emerald-400">+{positiveNet.toFixed(1)} pts</span>
                </div>
              </>
            )}
          </div>
          <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
            <h4 className="mb-3 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-red-400">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-red-500/20 text-xs">▼</span>
              Cost You Points
            </h4>
            {elo.negative.length === 0 ? (
                <p className="text-xs text-text-mute italic">No negative factors this game</p>
            ) : (
              <>
                <div className="space-y-2">
                  {elo.negative.map((f) => (
                    <div key={f.factor} className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-medium text-text-body">{f.factor}</span>
                        <span className="block text-xs text-text-mute">{f.detail}</span>
                      </div>
                      <span className="font-mono text-sm font-bold text-red-400">{f.value}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 border-t border-red-500/10 pt-2 text-right">
                  <span className="text-xs text-text-mute">Net: </span>
                  <span className="font-mono text-sm font-black text-red-400">{negativeNet.toFixed(1)} pts</span>
                </div>
              </>
            )}
          </div>
          <div className="md:col-span-2 rounded-lg border border-hairline bg-surface-2 p-3 text-center">
            <span className="text-xs font-bold uppercase tracking-wider text-text-mute">Estimated Rating Impact</span>
            <p className={`font-mono text-2xl font-black ${(positiveNet + negativeNet) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {(positiveNet + negativeNet) >= 0 ? '+' : ''}{(positiveNet + negativeNet).toFixed(1)} pts
            </p>
            <span className="text-xs text-text-mute">Based on performance metrics vs baselines</span>
          </div>
        </div>
      )}

      {/* Review Tab */}
      {activeTab === 'review' && (
        <div className="space-y-4">
          {/* Read-only view when review exists and not editing */}
          {hasReview && !isEditing ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-accent-primary">Post-Game Review</h4>
                <button
                  onClick={() => setIsEditing(true)}
                  className="rounded-md border border-hairline px-3 py-1.5 text-xs font-semibold text-text-body transition-colors hover:border-accent-primary/50 hover:text-accent-primary"
                >
                  Editar
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {match.lp_change !== null && (
                  <div className="rounded-lg border border-hairline bg-surface-2 p-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-text-mute">LP Change</span>
                    <p className={`font-mono text-xl font-black ${match.lp_change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {match.lp_change >= 0 ? '+' : ''}{match.lp_change}
                    </p>
                  </div>
                )}
                {match.tilt_level !== null && match.tilt_level > 0 && (
                  <div className="rounded-lg border border-hairline bg-surface-2 p-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-text-mute">Tilt</span>
                    <p className={`text-xl font-black ${TILT_LEVELS[match.tilt_level - 1]?.textColor ?? 'text-white'}`}>
                      {match.tilt_level}/5
                    </p>
                    <span className="text-xs text-text-mute">{TILT_LEVELS[match.tilt_level - 1]?.label}</span>
                  </div>
                )}
                {match.impact_rating && (
                  <div className="rounded-lg border border-hairline bg-surface-2 p-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-text-mute">Impact</span>
                    <p className="text-sm font-bold text-white">{match.impact_rating}</p>
                  </div>
                )}
                {match.vod_review && (
                  <div className="rounded-lg border border-hairline bg-surface-2 p-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-text-mute">VOD Review</span>
                    <p className="text-lg text-emerald-400">✅</p>
                  </div>
                )}
              </div>
              {match.notes && (
                <div className="rounded-lg border border-hairline bg-surface-2 p-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-text-mute">Notes</span>
                  <p className="mt-1 text-sm text-text-body whitespace-pre-wrap">{match.notes}</p>
                </div>
              )}
            </div>
          ) : (
            /* Editable form */
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-accent-primary">
                  {hasReview ? 'Editar Review' : 'Post-Game Review'}
                </h4>
                {hasReview && (
                  <button
                    onClick={() => setIsEditing(false)}
                    className="rounded-md px-3 py-1.5 text-xs font-semibold text-text-mute hover:text-text-body"
                  >
                    Cancelar
                  </button>
                )}
              </div>

              {!hasReview && (
                <p className="text-xs text-text-mute">
                  Registra cómo te sentiste en esta partida. Esto alimenta el sistema de anti-tilt.
                </p>
              )}

              {/* LP Change */}
              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-mute">
                  LP Change
                </label>
                <input
                  type="number"
                  value={lpChange}
                  onChange={(e) => setLpChange(e.target.value)}
                  placeholder="ej: +21 o -15"
                  className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm text-white placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
                />
              </div>

              {/* Tilt Level */}
              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-mute">
                  Tilt Level
                </label>
                <div className="flex gap-1.5">
                  {TILT_LEVELS.map((level) => (
                    <button
                      key={level.value}
                      onClick={() => setTiltLevel(tiltLevel === level.value ? 0 : level.value)}
                      className={`flex flex-1 flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-xs font-semibold transition-all ${
                        tiltLevel === level.value
                          ? `border-current ${level.textColor} bg-current/10`
                          : 'border-hairline bg-canvas text-text-mute hover:border-accent-primary/40'
                      }`}
                    >
                      <span className={`h-3 w-3 rounded-full ${level.color} ${tiltLevel === level.value ? 'opacity-100' : 'opacity-30'}`} />
                      {level.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Impact Rating */}
              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-mute">
                  Impact Rating
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {IMPACT_RATINGS.map((rating) => (
                    <button
                      key={rating.value}
                      onClick={() => setImpactRating(impactRating === rating.value ? '' : rating.value)}
                      className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                        impactRating === rating.value
                          ? `border-current ${rating.color} bg-current/10`
                          : 'border-hairline bg-canvas text-text-mute hover:border-accent-primary/40'
                      }`}
                    >
                      <span className="mr-1">{rating.emoji}</span>
                      {rating.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-mute">
                  Notas
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="¿Qué aprendí? ¿Qué hice bien? ¿Qué puedo mejorar?"
                  rows={4}
                  className="w-full resize-none rounded-lg border border-hairline bg-canvas px-3 py-2.5 text-sm text-white placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
                />
              </div>

              {/* VOD Review */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setVodReview(!vodReview)}
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    vodReview ? 'bg-accent-primary' : 'bg-surface-2'
                  }`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                    vodReview ? 'left-[22px]' : 'left-0.5'
                  }`} />
                </button>
                <span className="text-xs font-semibold text-text-body">VOD Review</span>
                {vodReview && <span className="text-xs text-accent-primary">✅ Visto</span>}
              </div>

              {/* Save */}
              <button
                onClick={handleSave}
                disabled={isSaving}
                className={`w-full rounded-lg px-4 py-2.5 text-sm font-bold transition-all active:scale-[0.98] ${
                  isSaving
                    ? 'cursor-not-allowed bg-surface-2 text-text-mute'
                    : 'bg-accent-primary text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] hover:bg-accent-primary/90'
                }`}
              >
                {isSaving ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-text-mute border-t-transparent" />
                    Guardando...
                  </span>
                ) : hasReview ? (
                  'Actualizar Review'
                ) : (
                  'Guardar Review'
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
