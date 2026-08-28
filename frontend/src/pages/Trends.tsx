import { TrendingUp, AlertTriangle, LineChart as LineChartIcon } from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { useKpiTrends } from '../hooks/useKpiTrends'
import type { TrendPoint } from '../data/types'

// Formato de fecha local amigable para el tooltip y el eje X.
function formatTs(ts: string): string {
  return new Date(ts).toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const METRICS = [
  {
    key: 'cs_min',
    label: 'CS / min',
    color: '#A855F7', // púrpura
    unit: '',
    fixed: 2,
  },
  {
    key: 'dpm',
    label: 'DPM (Daño / min)',
    color: '#10B981', // verde
    unit: '',
    fixed: 0,
  },
  {
    key: 'kda',
    label: 'KDA',
    color: '#3B82F6', // azul
    unit: '',
    fixed: 2,
  },
] as const

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
    <div className="rounded-lg border border-gray-700 bg-[#1A1A24] px-3 py-2 shadow-xl">
      <p className="text-[11px] font-bold text-white">{formatTs(d.timestamp)}</p>
      <p className="mt-1 font-mono text-xs font-bold" style={{ color: metric.color }}>
        {metric.label}: {value.toFixed(metric.fixed)}
      </p>
    </div>
  )
}

function TrendCard({
  metric,
  data,
}: {
  metric: (typeof METRICS)[number]
  data: TrendPoint[]
}) {
  const key = metric.key
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
            <CartesianGrid strokeDasharray="3 3" stroke="#2A2A35" vertical={false} />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTs}
              tick={{ fontSize: 10, fill: '#6B7280' }}
              tickLine={false}
              axisLine={{ stroke: '#2A2A35' }}
              minTickGap={30}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#6B7280' }}
              tickLine={false}
              axisLine={false}
              width={38}
              domain={['auto', 'auto']}
            />
            <Tooltip
              content={<CustomTooltip metric={metric} />}
              cursor={{ stroke: '#4B5563', strokeDasharray: '3 3' }}
            />
            <Area
              type="monotone"
              dataKey={key}
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
          <div className="flex items-center justify-center gap-2 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3 text-[10px] text-gray-500">
            <LineChartIcon className="h-3.5 w-3.5" />
            Pasando el ratón sobre cada gráfica verás el valor exacto de esa partida.
          </div>
        </div>
      )}
    </div>
  )
}
