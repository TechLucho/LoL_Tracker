import { TrendingUp } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useLpTrend } from '../hooks/useLpTrend'

interface TooltipPayload {
  active?: boolean
  payload?: Array<{ payload: { game_id: string; champion: string; lp_change: number | null; lp_cumulative: number; has_lp: boolean; win: boolean } }>
}

function CustomTooltip({ active, payload }: TooltipPayload) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-gray-700 bg-[#1A1A24] px-3 py-2 shadow-xl">
      <p className="text-[11px] font-bold text-white">{d.champion}</p>
      <div className="mt-1 flex items-center gap-2">
        <span className={`font-mono text-xs font-bold ${d.lp_change != null && d.lp_change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {d.has_lp ? `${d.lp_change! >= 0 ? '+' : ''}${d.lp_change}` : 'Sin LP'}
        </span>
        {d.has_lp && (
          <span className="text-[10px] text-gray-500">
            ({d.lp_cumulative >= 0 ? '+' : ''}{d.lp_cumulative} acuml.)
          </span>
        )}
      </div>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="shimmer h-32 rounded-lg bg-gray-800/30" />
  )
}

export default function RatingTrend() {
  const { data, isLoading, isError } = useLpTrend(30)

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-purple-400">
          📈 LP Acumulado
        </h3>
        {data && data.length > 0 && (
          <span className={`font-mono text-xs font-bold ${
            (data[data.length - 1]?.lp_cumulative ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {(data[data.length - 1]?.lp_cumulative ?? 0) >= 0 ? '+' : ''}
            {data[data.length - 1]?.lp_cumulative ?? 0} LP
          </span>
        )}
      </div>

      {isLoading && <Skeleton />}

      {isError && (
        <div className="flex h-32 items-center justify-center">
          <p className="text-[11px] text-gray-500">No hay datos de LP todavía</p>
        </div>
      )}

      {!isLoading && !isError && data && data.length === 0 && (
        <div className="flex h-32 flex-col items-center justify-center gap-1.5">
          <TrendingUp className="h-5 w-5 text-gray-600" />
          <p className="text-[11px] text-gray-500">Registra tu primer LP para ver la tendencia</p>
        </div>
      )}

      {!isLoading && !isError && data && data.length > 0 && (
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="lpGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={(data[data.length - 1]?.lp_cumulative ?? 0) >= 0 ? '#10B981' : '#EF4444'}
                    stopOpacity={0.3}
                  />
                  <stop
                    offset="100%"
                    stopColor={(data[data.length - 1]?.lp_cumulative ?? 0) >= 0 ? '#10B981' : '#EF4444'}
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <XAxis dataKey="game_id" hide />
              <YAxis hide />
              <Tooltip content={<CustomTooltip />} cursor={false} />
              <Area
                type="monotone"
                dataKey="lp_cumulative"
                stroke={(data[data.length - 1]?.lp_cumulative ?? 0) >= 0 ? '#10B981' : '#EF4444'}
                strokeWidth={2}
                fill="url(#lpGrad)"
                dot={false}
                activeDot={{
                  r: 4,
                  fill: (data[data.length - 1]?.lp_cumulative ?? 0) >= 0 ? '#10B981' : '#EF4444',
                  stroke: '#14141C',
                  strokeWidth: 2,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
