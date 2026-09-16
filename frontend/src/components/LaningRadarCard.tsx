import { Radar } from 'lucide-react'
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar as RechartsRadar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts'
import { useLaningStats } from '../hooks/useLaningStats'
import type { LaningSummary } from '../api/client'

// Escalas diferentes (oro en cientos/miles, XP en miles, CS en unidades): cada métrica se
// normaliza a un valor 0..1 donde 0.5 = duelo parejo a los 15:00. El CAP fija dónde llega el
// vértice al borde ("ventaja enorme") y dónde se hunde al centro ("te mataron la lane").
const LANING_METRICS = [
  { key: 'avg_gd15', label: 'Oro', emoji: '🪙', cap: 2000, fixed: 0, color: '#F59E0B' },
  { key: 'avg_xpd15', label: 'Exp.', emoji: '⚡', cap: 2000, fixed: 0, color: '#A855F7' },
  { key: 'avg_csd15', label: 'CS', emoji: '⚔️', cap: 25, fixed: 1, color: '#06B6D4' },
] as const

type LaningMetric = (typeof LANING_METRICS)[number]

function normalized(raw: number | null | undefined, cap: number): number {
  if (raw == null) return 0.5 // sin dato = neutral, no inventar ventaja ni desventaja
  const ratio = Math.max(-1, Math.min(1, raw / cap))
  return 0.5 + 0.5 * ratio
}

function signed(value: number | null | undefined, fixed: number): string {
  if (value == null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(fixed)}`
}

export default function LaningRadarCard() {
  const { data, isLoading, isError } = useLaningStats(50)

  return (
    <div className="rounded-xl border border-hairline bg-surface-1 p-6">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-amber-400">
          🔺 Triángulo del Laning
        </h3>
        <span className="font-mono text-xs font-bold text-text-mute">
          {data ? `${data.games_analyzed} partidas` : '—'}
        </span>
      </div>

      {isLoading ? (
        <div className="h-44 animate-pulse rounded-lg bg-surface-2/30" />
      ) : isError || !data || data.games_analyzed === 0 ? (
        <div className="flex h-44 flex-col items-center justify-center px-6 text-center">
          <Radar className="h-6 w-6 text-text-mute" />
          <p className="mt-2 text-xs font-medium text-text-body">Sin datos de laning todavía</p>
          <p className="mt-1 text-xs text-text-mute">
            Se añaden al sincronizar partidas de 15+ minutos con rival de línea (Timeline de
            Riot). Al hacerlo, este triángulo medirá tu early game.
          </p>
        </div>
      ) : (
        <ChartBody data={data} />
      )}
    </div>
  )
}

function ChartBody({ data }: { data: LaningSummary }) {
  const chartData = LANING_METRICS.map((m) => ({
    metric: m.label,
    value: normalized(data[m.key], m.cap),
  }))

  return (
    <>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="52%" outerRadius="72%" data={chartData}>
            <PolarGrid stroke="#2A2A35" />
            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: '#9CA3AF' }} />
            <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
            <RechartsRadar
              dataKey="value"
              stroke="#A855F7"
              fill="#A855F7"
              fillOpacity={0.25}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <Readout data={data} />
    </>
  )
}

function Readout({ data }: { data: LaningSummary }) {
  return (
    <>
      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-mute">
        {LANING_METRICS.map((m: LaningMetric) => {
          const raw = data[m.key]
          const positive = raw != null && raw > 0
          const negative = raw != null && raw < 0
          return (
            <span key={m.key} className="inline-flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: m.color }} />
              <span>{m.emoji} {m.label}:</span>{' '}
              <span
                className={`font-mono font-bold ${
                  positive ? 'text-emerald-400' : negative ? 'text-red-400' : 'text-text-mute'
                }`}
              >
                {signed(raw, m.fixed)}
              </span>
            </span>
          )
        })}
        <span className="text-text-mute">·</span>
        <span>0 = duelo parejo a los 15:00</span>
      </p>
      <p className="mt-1 text-xs leading-relaxed text-text-mute">
        Cada vértice compara tu minuto 15 contra tu rival directo (misma línea, otro equipo): pegado al centro pierdes la lane, hacia fuera la ganas.
      </p>
    </>
  )
}