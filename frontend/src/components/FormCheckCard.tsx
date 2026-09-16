import { ArrowUp, ArrowDown, Minus, BarChart3 } from 'lucide-react'
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
    <div className="flex items-center justify-between border-b border-hairline/50 py-2 last:border-0">
      <span className="text-xs font-medium text-text-body">{metric.name}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-text-mute line-through">
          {fmt(metric.previous)}{metric.unit}
        </span>
        <span className="text-xs text-text-mute">→</span>
        <span className="font-mono text-xs font-bold text-white">
          {fmt(metric.current)}{metric.unit}
        </span>
        <span className={`flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-bold ${
          trend === 'up'
            ? 'bg-emerald-500/15 text-emerald-400'
            : trend === 'down'
            ? 'bg-red-500/15 text-red-400'
            : 'bg-surface-2 text-text-mute'
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
    <div className="rounded-xl border border-hairline bg-surface-1 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-accent-primary">
          📋 Form Check
        </h3>
        <span className="rounded-full bg-accent-primary/10 px-2 py-0.5 text-xs font-bold text-accent-primary">
          LAST 5 vs PREV 5
        </span>
      </div>

      {!groups ? (
        <div className="flex flex-col items-center gap-1.5 py-6">
          <BarChart3 className="h-5 w-5 text-text-mute" />
          <p className="text-xs text-text-mute">
            Necesitas al menos 8 partidas sincronizadas para comparar tu forma.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {/* Improving */}
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
            <div className="mb-2 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-xs">✓</span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                Improving
              </h4>
            </div>
            {groups.improving.length === 0 ? (
              <p className="py-1 text-xs italic text-text-mute">Nada destacable al alza</p>
            ) : (
              groups.improving.map((m) => <MetricRow key={m.name} metric={m} />)
            )}
          </div>

          {/* Slipping */}
          <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
            <div className="mb-2 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/20 text-xs">!</span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-red-400">
                Slipping
              </h4>
            </div>
            {groups.slipping.length === 0 ? (
              <p className="py-1 text-xs italic text-text-mute">Nada en caída</p>
            ) : (
              groups.slipping.map((m) => <MetricRow key={m.name} metric={m} />)
            )}
          </div>

          {/* Steady */}
          <div className="rounded-lg border border-hairline/50 bg-surface-2/20 p-3">
            <div className="mb-2 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface-2 text-xs">—</span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-text-mute">
                Steady
              </h4>
            </div>
            {groups.steady.length === 0 ? (
              <p className="py-1 text-xs italic text-text-mute">Todo se está moviendo</p>
            ) : (
              groups.steady.map((m) => <MetricRow key={m.name} metric={m} />)
            )}
          </div>
        </div>
      )}
    </div>
  )
}
