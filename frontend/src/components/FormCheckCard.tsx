import { ArrowUp, ArrowDown, Minus } from 'lucide-react'
import type { FormCheckMetric, UIMatch } from '../data/types'
import { computeFormCheck, metricTrend } from '../data/insights'

function fmt(n: number): string {
  return n >= 100 ? Math.round(n).toString() : n.toFixed(1)
}

function MetricRow({ metric }: { metric: FormCheckMetric }) {
  const trend = metricTrend(metric)
  const deltaPct =
    metric.previous === 0 ? 0 : ((metric.current - metric.previous) / metric.previous) * 100
  const absDelta = Math.abs(deltaPct).toFixed(0)

  return (
    <div className="flex items-center justify-between border-b border-white/5 py-2 last:border-0">
      <span className="text-xs font-medium text-gray-300">{metric.name}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-gray-500 line-through">
          {fmt(metric.previous)}{metric.unit}
        </span>
        <span className="text-[10px] text-gray-600">→</span>
        <span className="font-mono text-xs font-bold text-white">
          {fmt(metric.current)}{metric.unit}
        </span>
        <span className={`flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
          trend === 'up'
            ? 'bg-emerald-500/15 text-emerald-400'
            : trend === 'down'
            ? 'bg-red-500/15 text-red-400'
            : 'bg-gray-500/15 text-gray-400'
        }`}>
          {trend === 'up' ? <ArrowUp className="h-2.5 w-2.5" /> : trend === 'down' ? <ArrowDown className="h-2.5 w-2.5" /> : <Minus className="h-2.5 w-2.5" />}
          {absDelta}%
        </span>
      </div>
    </div>
  )
}

interface FormCheckCardProps {
  matches: UIMatch[]
}

export default function FormCheckCard({ matches }: FormCheckCardProps) {
  // Comparación real: últimas 5 partidas vs las 5 anteriores del historial sincronizado.
  const groups = computeFormCheck(matches)

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-purple-400">
          📋 Form Check
        </h3>
        <span className="rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] font-bold text-purple-300">
          LAST 5 vs PREV 5
        </span>
      </div>

      {!groups ? (
        <p className="py-6 text-center text-xs text-gray-500">
          Necesitas al menos 8 partidas sincronizadas para comparar tu forma.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {/* Improving */}
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
            <div className="mb-2 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-[10px]">✓</span>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                Improving
              </h4>
            </div>
            {groups.improving.length === 0 ? (
              <p className="py-1 text-[10px] italic text-gray-600">Nada destacable al alza</p>
            ) : (
              groups.improving.map((m) => <MetricRow key={m.name} metric={m} />)
            )}
          </div>

          {/* Slipping */}
          <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
            <div className="mb-2 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/20 text-[10px]">!</span>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-red-400">
                Slipping
              </h4>
            </div>
            {groups.slipping.length === 0 ? (
              <p className="py-1 text-[10px] italic text-gray-600">Nada en caída</p>
            ) : (
              groups.slipping.map((m) => <MetricRow key={m.name} metric={m} />)
            )}
          </div>

          {/* Steady */}
          <div className="rounded-lg border border-gray-700/50 bg-gray-800/20 p-3">
            <div className="mb-2 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gray-500/20 text-[10px]">—</span>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                Steady
              </h4>
            </div>
            {groups.steady.length === 0 ? (
              <p className="py-1 text-[10px] italic text-gray-600">Todo se está moviendo</p>
            ) : (
              groups.steady.map((m) => <MetricRow key={m.name} metric={m} />)
            )}
          </div>
        </div>
      )}
    </div>
  )
}
