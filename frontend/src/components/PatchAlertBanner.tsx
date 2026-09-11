import { AlertTriangle, Info } from 'lucide-react'
import { usePatchAlert } from '../hooks/usePatchAlert'
import type { PatchChampionInfo } from '../api/client'

function formatWinrate(value: number | null | undefined): string {
  return value == null ? '—' : `${value}%`
}

export default function PatchAlertBanner() {
  const { data, isError } = usePatchAlert()

  // Capa auxiliar: si Data Dragon no está disponible o la petición falla, la página
  // principal no debe enterarse. Lo mismo al cargar: no hay nada que mostrar todavía.
  if (isError || !data) return null

  // Parche recién salido: aún no hay partidas sincronizadas → aviso informativo.
  if (!data.has_current_games) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-purple-800/50 bg-[#14141C] p-3">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-purple-400" />
        <p className="text-[11px] leading-relaxed text-gray-400">
          <span className="font-bold text-purple-300">Parche {data.current_patch} detectado.</span>{' '}
          Todavía no hay partidas sincronizadas en este parche: al sincronizar algunas,
          compararé tu winrate contra el histórico.
        </p>
      </div>
    )
  }

  const affected = data.champions.filter((c) => c.dropped)
  if (affected.length === 0) return null

  const worstDrop = [...affected].sort((a, b) => a.delta_pp! - b.delta_pp!)[0]

  return (
    <div className="rounded-xl border border-amber-700/50 bg-[#14141C] p-3">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] leading-relaxed text-gray-300">
            <span className="font-bold text-amber-300">
              Parche {data.current_patch}
            </span>{' '}
            — tu rendimiento bajó en {affected.length === 1 ? '1 campeón' : `${affected.length} campeones`} del
            pool: {affected.map((c) => c.champion).join(', ')}.{' '}
            {worstDrop && (
              <span className="text-gray-500">
                Peor caída: {worstDrop.champion} ({worstDrop.winrate_current}% vs {worstDrop.winrate_previous}% histórico).
              </span>
            )}
          </p>
        </div>
      </div>
      <div className="ml-7 mt-2 flex flex-wrap gap-1.5">
        {data.champions.map((c) => (
          <ChampionChip key={c.champion} info={c} />
        ))}
      </div>
    </div>
  )
}

function ChampionChip({ info }: { info: PatchChampionInfo }) {
  const dropped = info.dropped
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] ${
        dropped
          ? 'border-amber-700/60 bg-amber-500/10 text-amber-200'
          : 'border-gray-800 bg-[#0D0D12] text-gray-500'
      }`}
    >
      <span>{info.champion}</span>
      <span className="font-mono">{formatWinrate(info.winrate_current)}</span>
      {dropped && (
        <span className="text-amber-400" title="Winrate del parche actual vs histórico">
          ▼
        </span>
      )}
    </span>
  )
}