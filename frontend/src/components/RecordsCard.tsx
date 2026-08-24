import { Trophy, Swords, Flame, Target, Zap, Skull } from 'lucide-react'
import type { UIMatch } from '../data/types'
import { computeRecords } from '../data/insights'

const iconMap: Record<string, React.ReactNode> = {
  trophy: <Trophy className="h-4 w-4 text-yellow-400" />,
  swords: <Swords className="h-4 w-4 text-red-400" />,
  flame: <Flame className="h-4 w-4 text-orange-400" />,
  target: <Target className="h-4 w-4 text-purple-400" />,
  zap: <Zap className="h-4 w-4 text-yellow-300" />,
  skull: <Skull className="h-4 w-4 text-red-500" />,
}

interface Props {
  matches: UIMatch[]
}

export default function RecordsCard({ matches }: Props) {
  // Récords calculados sobre el historial sincronizado; vacío si aún no hay partidas.
  const records = computeRecords(matches)

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-purple-400">
        🏆 Records
      </h3>
      {records.length === 0 ? (
        <p className="text-[11px] text-gray-500">
          Sincroniza partidas para empezar a registrar récords.
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {records.map((r) => (
            <div
              key={r.label}
              className="flex items-center justify-between rounded-lg border border-gray-800/50 bg-[#0D0D12] px-3 py-2 transition-colors hover:bg-[#1A1A24]"
            >
              <div className="flex items-center gap-2">
                {iconMap[r.icon]}
                <span className="text-[11px] text-gray-400">{r.label}</span>
              </div>
              <span className="font-mono text-sm font-bold text-white">
                {r.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
