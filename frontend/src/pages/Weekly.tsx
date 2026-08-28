import { Calendar, CalendarX, Trophy, AlertTriangle, Medal } from 'lucide-react'
import type { ReactNode } from 'react'
import { useWeeklyReport } from '../hooks/useWeeklyReport'
import { useIcons } from '../hooks/useMetadata'

function formatPeriod(start: string, end: string): string {
  const s = new Date(start)
  const e = new Date(end)
  const fmt = (d: Date) =>
    d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
  return `${fmt(s)} — ${fmt(e)}`
}

function winrateColor(wr: number): string {
  if (wr >= 60) return 'text-emerald-400'
  if (wr >= 50) return 'text-yellow-400'
  return 'text-red-400'
}

function ChampionAvatar({ champion, size }: { champion: string; size: 'lg' | 'md' }) {
  const icons = useIcons()
  const info = icons.champion(champion)
  return (
    <img
      src={info.url}
      alt={champion}
      title={info.name}
      className={`rounded-xl border border-gray-700 ${
        size === 'lg' ? 'h-16 w-16' : 'h-12 w-12'
      }`}
      onError={(e) => {
        // Fallback: DDragon resolver ya cae a una imagen por defecto; nada que hacer aquí.
        e.currentTarget.style.opacity = '0.4'
      }}
    />
  )
}

function BigStatCard({
  label,
  value,
  sub,
  accent,
  valueClass = 'text-white',
}: {
  label: string
  value: ReactNode
  sub?: string
  accent?: string
  valueClass?: string
}) {
  return (
    <div className={`rounded-xl border p-5 ${accent ?? 'border-gray-800 bg-[#14141C]'}`}>
      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500">{label}</p>
      <p className={`mt-2 font-mono text-4xl font-black leading-none ${valueClass}`}>{value}</p>
      {sub && <p className="mt-2 text-xs text-gray-500">{sub}</p>}
    </div>
  )
}

export default function WeeklyPage() {
  const { data, isLoading, isError } = useWeeklyReport()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-black uppercase tracking-wider text-purple-400">
          <Calendar className="h-5 w-5" /> Reporte Semanal
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Tu rendimiento de los últimos 7 días, de un vistazo.
        </p>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="shimmer h-32 rounded-xl bg-gray-800/30" />
          ))}
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center justify-center py-16">
          <AlertTriangle className="h-8 w-8 text-red-500/50" />
          <p className="mt-3 text-sm text-red-400">Error al cargar el reporte semanal</p>
          <p className="mt-1 text-xs text-gray-500">Asegúrate de que el backend esté corriendo.</p>
        </div>
      )}

      {!isLoading && !isError && data && data.total_games === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <CalendarX className="h-8 w-8 text-gray-600" />
          <p className="mt-3 text-sm font-medium text-gray-300">No hay actividad reciente</p>
          <p className="mt-1 text-xs text-gray-500">
            Juega algunas partidas esta semana para generar tu reporte.
          </p>
        </div>
      )}

      {!isLoading && !isError && data && data.total_games > 0 && (
        <>
          {/* Periodo */}
          <div className="flex items-center gap-2 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3">
            <Calendar className="h-4 w-4 text-purple-400" />
            <span className="text-sm font-bold text-white">Semana del {formatPeriod(data.period_start, data.period_end)}</span>
          </div>

          {/* Métricas clave */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <BigStatCard
              label="Winrate semanal"
              value={`${data.winrate.toFixed(0)}%`}
              sub={`${data.wins}V – ${data.losses}D`}
              valueClass={winrateColor(data.winrate)}
              accent="border-purple-500/30 bg-purple-500/5"
            />
            <BigStatCard
              label="Partidas"
              value={data.total_games}
              sub="últimos 7 días"
            />
            <BigStatCard
              label="KDA medio"
              value={data.avg_kda.toFixed(2)}
              sub="(K+A) / muertes"
            />
            <BigStatCard
              label="Racha"
              value={data.wins >= data.losses ? 'Positiva' : 'Negativa'}
              sub={`basada en ${data.total_games} partidas`}
              valueClass={data.wins >= data.losses ? 'text-emerald-400' : 'text-red-400'}
            />
          </div>

          {/* Campeón más jugado + Mejor partida */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data.most_played && (
              <div className="flex items-center gap-4 rounded-xl border border-gray-800 bg-[#14141C] p-5">
                <ChampionAvatar champion={data.most_played.champion} size="lg" />
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500">
                    🏆 Campeón más jugado
                  </p>
                  <p className="mt-1 truncate text-lg font-black text-white">
                    {data.most_played.champion}
                  </p>
                  <p className="mt-1 text-xs text-gray-400">
                    {data.most_played.games} partidas · {data.most_played.wins}V -
                    {data.most_played.games - data.most_played.wins}D
                  </p>
                </div>
              </div>
            )}

            {data.best_match && (
              <div className="flex items-center gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5">
                <ChampionAvatar champion={data.best_match.champion} size="lg" />
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-400">
                    <Trophy className="mr-1 inline h-3.5 w-3.5" /> Mejor partida
                  </p>
                  <p className="mt-1 truncate text-lg font-black text-white">
                    {data.best_match.champion}
                  </p>
                  <p className="mt-1 font-mono text-xs text-gray-300">
                    KDA {data.best_match.kills}/{data.best_match.deaths}/{data.best_match.assists}
                    <span className="mx-1 text-gray-600">·</span>
                    <span className="font-bold text-emerald-400">
                      Rating {data.best_match.rating.toFixed(1)}
                    </span>
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-center gap-2 rounded-xl border border-gray-800 bg-[#14141C] px-4 py-3 text-[10px] text-gray-500">
            <Medal className="h-3.5 w-3.5" />
            El rating de la mejor partida usa la puntuación objetiva 0-100 calculada por el backend.
          </div>
        </>
      )}
    </div>
  )
}
