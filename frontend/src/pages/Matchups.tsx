import { useState, useMemo, useRef, useEffect } from 'react'
import { Save, ScrollText, Swords, AlertTriangle, Loader2 } from 'lucide-react'
import { useChampionList, useIcons } from '../hooks/useMetadata'
import { useMatchupStats, useMatchupNotes, useUpdateMatchupNotes } from '../hooks/useMatchups'
import { DDragon } from '../data/constants'

// Selector de campeón con buscador, icono y dropdown (reutiliza la caché de /api/metadata).
function ChampionSelect({
  label,
  value,
  onChange,
  image,
}: {
  label: string
  value: string | null
  onChange: (name: string | null) => void
  image: string
}) {
  const champions = useChampionList()
  const [search, setSearch] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setShowDropdown(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = useMemo(
    () =>
      search.trim()
        ? champions.filter((c) =>
            c.name.toLowerCase().includes(search.toLowerCase()),
          )
        : champions,
    [champions, search],
  )

  const clear = () => {
    onChange(null)
    setSearch('')
    setShowDropdown(false)
  }

  return (
    <div className="relative" ref={ref}>
      <span className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-secondary">
        {label}
      </span>

      {value ? (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5">
          <img
            src={image}
            alt={value}
            className="h-9 w-9 rounded-lg border border-gray-700"
            onError={(e) => {
              (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
            }}
          />
          <div className="min-w-0 flex-1">
            <span className="block truncate text-sm font-bold text-text-primary">{value}</span>
            <button
              type="button"
              onClick={clear}
              className="mt-0.5 text-xs text-text-muted transition-colors hover:text-red-400"
            >
              Cambiar campeón
            </button>
          </div>
        </div>
      ) : (
        <div className="relative">
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setShowDropdown(e.target.value.length > 0)
            }}
            onFocus={() => {
              if (search.length > 0) setShowDropdown(true)
            }}
            placeholder="Busca un campeón..."
            className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50"
          />

          {showDropdown && (
            <div className="absolute z-50 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-border bg-card shadow-xl">
              {filtered.length === 0 && (
                <div className="px-3 py-4 text-center text-xs text-text-muted">
                  {champions.length === 0
                    ? 'Cargando campeones desde el backend...'
                    : `No se encontró "${search}"`}
                </div>
              )}
              {filtered.slice(0, 12).map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => {
                    onChange(c.name)
                    setSearch('')
                    setShowDropdown(false)
                  }}
                  className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm transition-colors hover:bg-card-hover"
                >
                  <img
                    src={c.image}
                    alt={c.name}
                    className="h-6 w-6 rounded border border-gray-700"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                    }}
                  />
                  <span className="font-medium text-text-primary">{c.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function MatchupsPage() {
  const [userChamp, setUserChamp] = useState<string | null>(null)
  const [enemyChamp, setEnemyChamp] = useState<string | null>(null)
  const [draftNotes, setDraftNotes] = useState('')

  const icons = useIcons()
  const bothSelected = Boolean(userChamp && enemyChamp)

  const { data: stats, isLoading: statsLoading } = useMatchupStats(userChamp, enemyChamp)
  const { data: notes, isLoading: notesLoading } = useMatchupNotes(userChamp, enemyChamp)
  const updateNotes = useUpdateMatchupNotes(userChamp ?? '', enemyChamp ?? '')

  // Carga las notas guardadas al cambiar de cruce (o cuando llegan).
  const loadedRef = useRef<string>('')
  useEffect(() => {
    const key = `${userChamp ?? ''}|${enemyChamp ?? ''}`
    if (loadedRef.current !== key) {
      loadedRef.current = key
      setDraftNotes(notes?.notes ?? '')
    }
  }, [userChamp, enemyChamp, notes])

  const dirty = notes?.notes !== draftNotes && bothSelected

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <h2 className="flex items-center gap-2 text-lg font-black uppercase tracking-wider text-purple-400">
          <Swords className="h-5 w-5 text-accent-purple" />
          Matchups
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Elige dos campeones (Tú vs Enemigo) y revisa tus números en ese cruce, con un bloc de
          notas persistente por emparejamiento.
        </p>
      </div>

      {/* Selectores */}
      <div className="grid grid-cols-1 gap-4 rounded-xl border border-border bg-card p-5 sm:grid-cols-2">
        <ChampionSelect
          label="Tu campeón"
          value={userChamp}
          onChange={setUserChamp}
          image={userChamp ? icons.champion(userChamp).url : ''}
        />
        <ChampionSelect
          label="Campeón enemigo"
          value={enemyChamp}
          onChange={setEnemyChamp}
          image={enemyChamp ? icons.champion(enemyChamp).url : ''}
        />
      </div>

      {/* Estadísticas */}
      {bothSelected && (
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-base font-bold text-text-primary">
              <span className="text-base">📊</span>
              {userChamp} vs {enemyChamp}
            </h3>
            {statsLoading && <Loader2 className="h-4 w-4 animate-spin text-text-muted" />}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatBox label="Partidas" value={String(stats?.games_played ?? 0)} />
            <StatBox label="W / L" value={stats ? `${stats.wins}W – ${stats.losses}L` : '–'} />
            <StatBox
              label="Winrate"
              value={stats ? `${stats.winrate.toFixed(1)}%` : '–'}
              accent={stats && stats.winrate >= 50 ? 'text-emerald-400' : 'text-red-400'}
            />
            <StatBox
              label="KDA medio"
              value={stats ? stats.kda_ratio.toFixed(2) : '–'}
              sub={stats ? `${stats.avg_kills}/${stats.avg_deaths}/${stats.avg_assists}` : undefined}
            />
          </div>
        </div>
      )}

      {/* Bloc de notas */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-base font-bold text-text-primary">
            <ScrollText className="h-4 w-4 text-accent-purple" />
            Notas del emparejamiento
          </h3>
          {notes?.updated_at && (
            <span className="text-[11px] text-text-muted">
              Última edición: {new Date(notes.updated_at).toLocaleString()}
            </span>
          )}
        </div>

        {!bothSelected ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background px-4 py-10 text-center">
            <AlertTriangle className="h-6 w-6 text-text-muted" />
            <p className="mt-2 text-sm text-text-muted">
              Selecciona ambos campeones para leer o escribir las notas del emparejamiento.
            </p>
          </div>
        ) : notesLoading ? (
          <div className="shimmer h-40 rounded-lg bg-background" />
        ) : (
          <>
            <textarea
              value={draftNotes}
              onChange={(e) => setDraftNotes(e.target.value)}
              placeholder="Apuntes de estrategia para este cruce: cuándo agredir, cómo jugar la línea, cuándo dodge..."
              rows={8}
              className="w-full resize-y rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-text-primary placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50"
            />
            <div className="mt-3 flex items-center justify-between">
              <p className="text-[11px] text-text-muted">
                {stats && stats.games_played === 0 ? (
                  '0 partidas registradas en este cruce — las notas se guardan igualmente.'
                ) : (
                  `Guardado: ${dirty ? 'hay cambios sin guardar' : 'al día'}`
                )}
              </p>
              <button
                type="button"
                disabled={updateNotes.isPending}
                onClick={() => {
                  if (userChamp && enemyChamp) updateNotes.mutate(draftNotes)
                }}
                className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-bold transition-all active:scale-95 ${
                  updateNotes.isPending
                    ? 'cursor-not-allowed bg-gray-800 text-gray-500'
                    : 'bg-accent-purple text-white shadow-lg shadow-accent-purple/20 hover:bg-accent-purple-dim'
                }`}
              >
                {updateNotes.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5" />
                )}
                {updateNotes.isPending ? 'Guardando...' : 'Guardar notas'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function StatBox({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: string
}) {
  return (
    <div className="rounded-lg border border-border bg-background px-4 py-3 text-center">
      <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{label}</span>
      <p className={`mt-1 font-mono text-xl font-black ${accent ?? 'text-text-primary'}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[10px] text-text-muted">{sub}</p>}
    </div>
  )
}
