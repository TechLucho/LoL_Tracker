import { type ReactNode, useMemo } from 'react'
import { TrendingUp, AlertTriangle, LineChart as LineChartIcon, Eye, Target } from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { useKpiTrends } from '../hooks/useKpiTrends'
import LaningRadarCard from '../components/LaningRadarCard'
import type { TrendPoint } from '../data/types'

// ────────────────────── Andamiaje de gráficas compartido (DRY) ──────────────────────

const CHART_TICK = { fontSize: 10, fill: '#6B7280' } as const
const AXIS_STROKE = '#2A2A35'

function ChartGrid({ vertical = false }: { vertical?: boolean }) {
  return <CartesianGrid strokeDasharray="3 3" stroke={AXIS_STROKE} vertical={vertical} />
}

function TrendXAxis() {
  return (
    <XAxis
      dataKey="timestamp"
      tickFormatter={formatTs}
      tick={CHART_TICK}
      tickLine={false}
      axisLine={{ stroke: AXIS_STROKE }}
      minTickGap={30}
    />
  )
}

function TrendYAxis({
  width = 38,
  domain = ['auto', 'auto'] as [string, string],
}: { width?: number; domain?: [string, string] } = {}) {
  return (
    <YAxis
      tick={CHART_TICK}
      tickLine={false}
      axisLine={false}
      width={width}
      domain={domain}
    />
  )
}

function TooltipShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-700 bg-[#1A1A24] px-3 py-2 shadow-xl">
      <p className="text-[11px] font-bold text-white">{title}</p>
      {children}
    </div>
  )
}

// ────────────────────── Utilidades ──────────────────────

function formatTs(ts: string): string {
  return new Date(ts).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ────────────────────── Métricas ──────────────────────

const METRICS = [
  {
    key: 'cs_min',
    label: 'CS / min',
    color: '#A855F7',
    unit: '',
    fixed: 2,
  },
  {
    key: 'dpm',
    label: 'DPM (Daño / min)',
    color: '#10B981',
    unit: '',
    fixed: 0,
  },
  {
    key: 'kda',
    label: 'KDA',
    color: '#3B82F6',
    unit: '',
    fixed: 2,
  },
] as const

// ────────────────────── Tooltips reutilizables ──────────────────────

interface TooltipPayload {
  active?: boolean
  payload?: Array<{ payload: TrendPoint }>
  metric: (typeof METRICS)[number]
}

function CustomTooltip({ active, payload, metric }: TooltipPayload) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const value = d[metric.key]
  return (
    <TooltipShell title={formatTs(d.timestamp)}>
      <p className="mt-1 font-mono text-xs font-bold" style={{ color: metric.color }}>
        {metric.label}: {value.toFixed(metric.fixed)}
      </p>
    </TooltipShell>
  )
}

function VisionTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: TrendPoint }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const v = d.vision_delta ?? 0
  return (
    <TooltipShell title={formatTs(d.timestamp)}>
      <p
        className={`mt-1 font-mono text-xs font-bold ${
          v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-400'
        }`}
      >
        Δ Visión: {v > 0 ? '+' : ''}
        {v.toFixed(0)}
      </p>
    </TooltipShell>
  )
}

function KpTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: TrendPoint }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const kp = d.kp ?? 0
  return (
    <TooltipShell title={formatTs(d.timestamp)}>
      <p className="mt-1 font-mono text-xs font-bold text-purple-300">
        KP: {(kp * 100).toFixed(0)}%
      </p>
      <p className={`text-[10px] font-bold ${d.win ? 'text-emerald-400' : 'text-red-400'}`}>
        {d.win ? 'VICTORIA' : 'DERROTA'}
      </p>
    </TooltipShell>
  )
}

// ────────────────────── Cards ──────────────────────

function TrendCard({
  metric,
  data,
}: {
  metric: (typeof METRICS)[number]
  data: TrendPoint[]
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: metric.color }}>
          📈 {metric.label}
        </h3>
        <span className="font-mono text-xs font-bold text-gray-400">
          {data.length} partidas
        </span>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`grad-${metric.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={metric.color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={metric.color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <ChartGrid />
            <TrendXAxis />
            <TrendYAxis />
            <Tooltip
              content={<CustomTooltip metric={metric} />}
              cursor={{ stroke: '#4B5563', strokeDasharray: '3 3' }}
            />
            <Area
              type="monotone"
              dataKey={metric.key}
              stroke={metric.color}
              strokeWidth={2}
              fill={`url(#grad-${metric.key})`}
              dot={false}
              activeDot={{ r: 4, fill: metric.color, stroke: '#14141C', strokeWidth: 2 }}
              name={metric.label}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

type WithVision = TrendPoint & { vision_delta: number }

function VisionDeltaCard({ data }: { data: TrendPoint[] }) {
  const points = useMemo(
    () => data.filter((d): d is WithVision => d.vision_delta != null),
    [data],
  )
  const avg = useMemo(
    () => (points.length ? points.reduce((s, p) => s + p.vision_delta, 0) / points.length : null),
    [points],
  )

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-cyan-400">
          🔭 Delta de Visión
        </h3>
        <span className="font-mono text-xs font-bold text-gray-400">
          {points.length} partidas
        </span>
      </div>

      {points.length === 0 ? (
        <div className="flex h-44 flex-col items-center justify-center px-6 text-center">
          <Eye className="h-6 w-6 text-gray-600" />
          <p className="mt-2 text-xs font-medium text-gray-300">Sin datos de visión</p>
          <p className="mt-1 text-[10px] text-gray-500">
            Necesitas partidas sincronizadas con rival de línea directo.
          </p>
        </div>
      ) : (
        <>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <ChartGrid />
                <ReferenceLine y={0} stroke="#4B5563" />
                <TrendXAxis />
                <TrendYAxis />
                <Tooltip
                  content={<VisionTooltip />}
                  cursor={{ fill: 'rgba(75, 85, 99, 0.08)' }}
                />
                <Bar dataKey="vision_delta" radius={[2, 2, 0, 0]}>
                  {points.map((p) => (
                    <Cell
                      key={p.game_id}
                      fill={p.vision_delta >= 0 ? '#06B6D4' : '#EF4444'}
                      fillOpacity={p.vision_delta >= 0 ? 0.85 : 0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[10px] text-gray-500">
            Δ medio:{' '}
            <span
              className={`font-mono font-bold ${
                avg != null && avg >= 0 ? 'text-cyan-400' : 'text-red-400'
              }`}
            >
              {avg != null ? `${avg >= 0 ? '+' : ''}${avg.toFixed(1)}` : '—'}
            </span>{' '}
            <span className="text-gray-600">·</span> sobre 0 ganas la batalla de visión
          </p>
        </>
      )}
    </div>
  )
}

type WithKp = TrendPoint & { kp_pct: number; result: number }

function KpScatterCard({ data }: { data: TrendPoint[] }) {
  const points = useMemo<WithKp[]>(() => {
    const filtered = data.filter((d): d is TrendPoint & { kp: number } => d.kp != null)
    return filtered.map((d, i) => ({
      ...d,
      kp_pct: Number((d.kp * 100).toFixed(1)),
      // Jitter determinista para evitar que los puntos se apilen en las filas V/D.
      result: (d.win ? 1 : 0) + (((i * 7) % 5) - 2) * 0.06,
    }))
  }, [data])

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-purple-400">
          🎯 KP% vs Resultado
        </h3>
        <span className="font-mono text-xs font-bold text-gray-400">
          {points.length} partidas
        </span>
      </div>

      {points.length === 0 ? (
        <div className="flex h-44 flex-col items-center justify-center px-6 text-center">
          <Target className="h-6 w-6 text-gray-600" />
          <p className="mt-2 text-xs font-medium text-gray-300">Sin datos de participación</p>
          <p className="mt-1 text-[10px] text-gray-500">
            Sincroniza partidas para ver en qué rango de KP% ganas.
          </p>
        </div>
      ) : (
        <>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <ChartGrid vertical />
                <ReferenceLine y={0.5} stroke="#374151" strokeDasharray="4 4" />
                <XAxis
                  dataKey="kp_pct"
                  type="number"
                  domain={[0, 100]}
                  tick={CHART_TICK}
                  tickLine={false}
                  axisLine={{ stroke: AXIS_STROKE }}
                  tickFormatter={(v: number) => `${Math.round(v)}%`}
                />
                <YAxis
                  dataKey="result"
                  type="number"
                  domain={[-0.4, 1.4]}
                  ticks={[0, 1]}
                  tickFormatter={(v: number) => (v === 0 ? 'D' : 'V')}
                  tick={CHART_TICK}
                  tickLine={false}
                  axisLine={false}
                  width={30}
                />
                <Tooltip content={<KpTooltip />} cursor={{ stroke: '#4B5563', strokeDasharray: '3 3' }} />
                <Scatter name="Partidas" data={points} fillOpacity={0.85}>
                  {points.map((p) => (
                    <Cell key={p.game_id} fill={p.win ? '#10B981' : '#EF4444'} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[10px] text-gray-500">
            <span className="font-semibold text-emerald-400">V</span> victoria ·{' '}
            <span className="font-semibold text-red-400">D</span> derrota · fíjate en qué rango
            de KP% se concentran tus puntos verdes
          </p>
        </>
      )}
    </div>
  )
}

// ────────────────────── Página ──────────────────────

function Skeleton() {
  return <div className="shimmer h-52 rounded-xl bg-gray-800/30" />
}

export default function TrendsPage() {
  const { data, isLoading, isError } = useKpiTrends(50)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-black uppercase tracking-wider text-purple-400">
          📊 KPIs de Mejora
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Evolución de tus métricas clave partida a partida. ¿Estás mejorando de verdad?
        </p>
      </div>

      {isLoading && (
        <div className="space-y-4">
          <Skeleton />
          <Skeleton />
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center justify-center py-16">
          <AlertTriangle className="h-8 w-8 text-red-500/50" />
          <p className="mt-3 text-sm text-red-400">Error al cargar las tendencias</p>
          <p className="mt-1 text-xs text-gray-500">Asegúrate de que el backend esté corriendo.</p>
        </div>
      )}

      {!isLoading && !isError && data && data.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <TrendingUp className="h-8 w-8 text-gray-600" />
          <p className="mt-3 text-sm font-medium text-gray-300">No hay datos de KPIs todavía</p>
          <p className="mt-1 text-xs text-gray-500">Sincroniza partidas para empezar a medir tu evolución.</p>
        </div>
      )}

      {!isLoading && !isError && data && data.length > 0 && (
        <div className="space-y-4">
          {METRICS.map((m) => (
            <TrendCard key={m.key} metric={m} data={data} />
          ))}
          <VisionDeltaCard data={data} />
          <KpScatterCard data={data} />
          <LaningRadarCard />
          <div className="flex items-center justify-center gap-2 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3 text-[10px] text-gray-500">
            <LineChartIcon className="h-3.5 w-3.5" />
            Pasando el ratón sobre cada gráfica verás el valor exacto de esa partida.
          </div>
        </div>
      )}
    </div>
  )
}
