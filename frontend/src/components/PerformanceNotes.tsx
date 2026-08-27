import { LineChart } from 'lucide-react'
import type { UIMatch } from '../data/types'
import { computePerformanceNotes } from '../data/insights'

interface Props {
  matches: UIMatch[]
}

export default function PerformanceNotes({ matches }: Props) {
  // Insights reales: winrate tras rachas y por franja horaria, sobre partidas sincronizadas.
  // (Los antiguos "BO3/BO5" venían de mock.ts: eso no existe en solo queue.)
  const notes = computePerformanceNotes(matches)

  return (
    <div className="rounded-xl border border-gray-800 bg-[#14141C] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-purple-400">
          🧠 Performance Notes
        </h3>
        <span className="text-[10px] text-gray-500">Patrones sobre tus partidas sincronizadas</span>
      </div>

      {notes.length === 0 ? (
        <div className="flex flex-col items-center gap-1.5 py-6">
          <LineChart className="h-5 w-5 text-gray-600" />
          <p className="text-xs text-gray-500">
            Sincroniza partidas para detectar patrones de rendimiento.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {notes.map((note) => {
            const isPositive = note.comparison > 0
            const isAboveAvg = note.winrate >= 60
            const isBelowAvg = note.winrate < 50
            return (
              <div
                key={note.label}
                className={`flex flex-col rounded-lg border p-3 transition-all hover:scale-[1.02] ${
                  isAboveAvg
                    ? 'border-emerald-500/20 bg-emerald-500/5'
                    : isBelowAvg
                    ? 'border-red-500/20 bg-red-500/5'
                    : 'border-gray-700/50 bg-gray-800/20'
                }`}
              >
                <span className="mb-1 text-[9px] font-bold uppercase tracking-widest text-gray-500">
                  {note.label}
                </span>
                <span className={`font-mono text-4xl font-black leading-none ${
                  isAboveAvg ? 'text-emerald-400' : isBelowAvg ? 'text-red-400' : 'text-gray-300'
                }`}>
                  {note.winrate.toFixed(0)}
                  <span className="text-lg">%</span>
                </span>
                <p className="mt-1.5 text-[10px] leading-tight text-gray-500">
                  {note.coaching}
                </p>
                <div className="mt-auto flex items-center justify-between pt-2">
                  <span className="text-[9px] text-gray-600">
                    {note.games} games
                  </span>
                  <span className={`text-[10px] font-bold ${
                    isPositive ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {isPositive ? '+' : ''}{note.comparison.toFixed(1)}% vs avg
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
