import { Trophy, Swords, Flame, Target, Zap, Skull } from 'lucide-react'
import type { UIMatch } from '../data/types'
import { computeRecords } from '../data/insights'

const iconMap: Record<string, React.ReactNode> = {
  trophy: <Trophy className="h-4 w-4 text-yellow-400" />,
  swords: <Swords className="h-4 w-4 text-red-400" />,
  flame: <Flame className="h-4 w-4 text-orange-400" />,
  target: <Target className="h-4 w-4 text-accent-primary" />,
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
    <div className="rounded-xl border border-hairline bg-surface-1 p-6">
      <h3 className="mb-3 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary">
        🏆 Records
      </h3>
      {records.length === 0 ? (
        <div className="flex flex-col items-center gap-1.5 py-4">
          <Trophy className="h-5 w-5 text-text-mute" />
          <p className="text-xs text-text-mute">
            Sincroniza partidas para empezar a registrar récords.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {records.map((r) => (
            <div
              key={r.label}
              className="flex items-center justify-between rounded-lg border border-hairline/50 bg-canvas px-3 py-2 transition-colors hover:bg-surface-2"
            >
              <div className="flex items-center gap-2">
                {iconMap[r.icon]}
                <span className="text-xs text-text-mute">{r.label}</span>
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
