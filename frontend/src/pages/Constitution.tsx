import { useConstitution } from '../hooks/useConstitution'
import { Shield, ShieldAlert, ShieldCheck, ShieldX, Skull, TrendingDown, Target, Swords } from 'lucide-react'

const STATUS_CONFIG: Record<string, { icon: typeof Shield; color: string; bg: string; border: string; pulse: string }> = {
  'SAFE TO PLAY': {
    icon: ShieldCheck,
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    pulse: '',
  },
  WARNING: {
    icon: ShieldAlert,
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    pulse: '',
  },
  'STOP PLAYING (TILTED)': {
    icon: ShieldX,
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    pulse: 'animate-pulse',
  },
}

const RULE_ICONS: Record<string, typeof Swords> = {
  loss_streak: TrendingDown,
  pool_fidelity: Swords,
  death_limit: Skull,
  cs_farming: Target,
}

const RULE_LABELS: Record<string, string> = {
  loss_streak: 'Racha de Derrotas',
  pool_fidelity: 'Fidelidad al Pool',
  death_limit: 'Límite de Muertes',
  cs_farming: 'Farmeo (CS/min)',
}

export default function ConstitutionPage() {
  const { data: status, isLoading, isError } = useConstitution()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
          <span className="text-xs text-gray-500">Evaluando La Constitución...</span>
        </div>
      </div>
    )
  }

  if (isError || !status) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <ShieldX className="h-12 w-12 text-red-500/50" />
        <p className="mt-3 text-sm text-red-400">Error al evaluar La Constitución</p>
        <p className="mt-1 text-xs text-gray-500">Asegúrate de que el backend esté corriendo.</p>
      </div>
    )
  }

  const cfg = STATUS_CONFIG[status.global_status] ?? STATUS_CONFIG['SAFE TO PLAY']
  const StatusIcon = cfg.icon

  return (
    <div className="space-y-6">
      {/* ═══ HEADER — Veredicto Global ═══ */}
      <div className={`rounded-xl border ${cfg.border} ${cfg.bg} p-6 ${cfg.pulse}`}>
        <div className="flex items-center gap-4">
          <div className={`flex h-14 w-14 items-center justify-center rounded-full ${
            status.global_status === 'STOP PLAYING (TILTED)'
              ? 'bg-red-500/20'
              : status.global_status === 'WARNING'
                ? 'bg-yellow-500/20'
                : 'bg-emerald-500/20'
          }`}>
            <StatusIcon className={`h-8 w-8 ${cfg.color}`} />
          </div>
          <div className="flex-1">
            <h1 className={`text-xl font-black uppercase tracking-wider ${cfg.color}`}>
              {status.global_status === 'NO DATA' ? 'SIN DATOS' : status.global_status}
            </h1>
            <p className="mt-0.5 text-sm text-gray-300">{status.message}</p>
          </div>
        </div>
      </div>

      {/* ═══ STATS BAR ═══ */}
      {status.stats.games_analyzed > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCard label="Partidas" value={String(status.stats.games_analyzed)} />
          <StatCard
            label="Wins"
            value={String(status.stats.wins)}
            color={status.stats.wins > status.stats.losses ? 'text-emerald-400' : 'text-white'}
          />
          <StatCard
            label="Losses"
            value={String(status.stats.losses)}
            color={status.stats.losses > status.stats.wins ? 'text-red-400' : 'text-white'}
          />
          <StatCard label="Muertes Avg" value={status.stats.avg_deaths.toFixed(1)} />
          <StatCard label="CS/min Avg" value={status.stats.avg_cs_min.toFixed(1)} />
        </div>
      )}

      {/* ═══ REGLAS ═══ */}
      <div>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-purple-400">
          ⚖️ Reglas de La Constitución
        </h2>
        <div className="space-y-2">
          {status.rules.map((rule) => {
            const passed = rule.status === 'PASS'
            const isWarning = rule.severity === 'warning' && !passed
            const RuleIcon = RULE_ICONS[rule.rule] ?? Shield

            return (
              <div
                key={rule.rule}
                className={`flex items-start gap-4 rounded-xl border px-4 py-3 transition-colors ${
                  passed
                    ? 'border-emerald-500/20 bg-emerald-500/5'
                    : isWarning
                      ? 'border-yellow-500/20 bg-yellow-500/5'
                      : 'border-red-500/20 bg-red-500/5'
                }`}
              >
                {/* Icon */}
                <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                  passed
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : isWarning
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-red-500/20 text-red-400'
                }`}>
                  {passed ? (
                    <ShieldCheck className="h-4 w-4" />
                  ) : (
                    <RuleIcon className="h-4 w-4" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                      {RULE_LABELS[rule.rule] ?? rule.rule}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-[9px] font-black uppercase ${
                      passed
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : isWarning
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-red-500/20 text-red-400'
                    }`}>
                      {rule.status}
                    </span>
                  </div>
                  <p className={`mt-0.5 text-sm font-medium ${
                    passed ? 'text-gray-300' : isWarning ? 'text-yellow-300' : 'text-red-300'
                  }`}>
                    {rule.message}
                  </p>
                  {rule.detail && (
                    <p className="mt-0.5 text-[11px] text-gray-500">{rule.detail}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ═══ BOTÓN DE PÁNICO ═══ */}
      <div className="rounded-xl border border-gray-800 bg-[#14141C] p-6 text-center">
        <p className="text-[11px] font-bold uppercase tracking-widest text-gray-500">
          ¿Entendido?
        </p>
        <p className="mt-1 text-xs text-gray-600">
          Promete mejorar y vuelve cuando estés listo.
        </p>
        <button className="mt-4 rounded-lg border border-purple-500/30 bg-purple-500/10 px-6 py-3 text-xs font-bold text-purple-400 transition-colors hover:bg-purple-500/20">
          🛡️ Prometo Mejorar
        </button>
      </div>
    </div>
  )
}

function StatCard({ label, value, color = 'text-white' }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-3 text-center">
      <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500">{label}</span>
      <p className={`font-mono text-lg font-black ${color}`}>{value}</p>
    </div>
  )
}
