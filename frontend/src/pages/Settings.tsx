import { useState, useEffect, useRef } from 'react'
import { Save, X, Shield, Target, AlertTriangle, Check } from 'lucide-react'
import { useSettings, useUpdateSettings } from '../hooks/useSettings'
import { DDragon } from '../data/constants'
import { useChampionList, useIcons } from '../hooks/useMetadata'

export default function SettingsPage() {
  const { data: settings, isLoading } = useSettings()
  const updateMutation = useUpdateSettings()

  // Metadatos servidos y cacheados por el backend (/api/metadata/champions): antes esta página
  // descargaba champion.json de Data Dragon directamente, con el parche hardcodeado en el cliente.
  const champions = useChampionList()
  const icons = useIcons()

  const [pool, setPool] = useState<string[]>([])
  const [targetCs, setTargetCs] = useState('7.5')
  const [maxDeaths, setMaxDeaths] = useState('4')
  const [search, setSearch] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'success' | 'error'>('idle')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Populate form when settings load
  useEffect(() => {
    if (settings) {
      setPool(settings.champion_pool)
      setTargetCs(String(settings.target_cs_min))
      setMaxDeaths(String(Math.round(settings.max_deaths)))
    }
  }, [settings])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = search.trim()
    ? champions.filter(
        (c) =>
          c.name.toLowerCase().includes(search.toLowerCase()) &&
          !pool.some((p) => p.toLowerCase() === c.name.toLowerCase()),
      )
    : []

  const addChampion = (name: string) => {
    if (pool.length >= 3) return
    if (pool.some((p) => p.toLowerCase() === name.toLowerCase())) return
    setPool([...pool, name])
    setSearch('')
    setShowDropdown(false)
  }

  const removeChampion = (name: string) => {
    setPool(pool.filter((p) => p !== name))
  }

  const handleSave = () => {
    const cs = parseFloat(targetCs)
    const deaths = parseInt(maxDeaths, 10)
    if (isNaN(cs) || cs <= 0 || cs > 20) return
    if (isNaN(deaths) || deaths <= 0 || deaths > 20) return
    if (pool.length === 0) return

    setSaveState('idle')
    updateMutation.mutate(
      {
        champion_pool: pool,
        target_cs_min: cs,
        max_deaths: deaths,
      },
      {
        onSuccess: () => {
          setSaveState('success')
          setTimeout(() => setSaveState('idle'), 3000)
        },
        onError: () => {
          setSaveState('error')
          setTimeout(() => setSaveState('idle'), 3000)
        },
      },
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="shimmer h-6 w-48 rounded bg-card" />
        <div className="shimmer h-40 rounded-xl bg-card" />
        <div className="shimmer h-32 rounded-xl bg-card" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-2 text-lg font-bold text-text-primary">
          <Shield className="h-5 w-5 text-accent-purple" />
          Configuración
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          La base de La Constitución. Define tu pool y tus objetivos de rendimiento.
        </p>
      </div>

      {/* Champion Pool Card */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-text-primary">
              <span className="text-base">🎯</span>
              Champion Pool
            </h2>
            <p className="mt-0.5 text-xs text-text-muted">
              Máximo 3 campeones. La Constitución no te deja jugar lo que quieras.
            </p>
          </div>
          <span className="rounded-md bg-accent-purple/15 px-2 py-0.5 text-xs font-bold text-accent-purple">
            {pool.length}/3
          </span>
        </div>

        {/* Selected Champions */}
        {pool.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {pool.map((name) => (
              <div
                key={name}
                className="flex items-center gap-2 rounded-lg border border-accent-purple/30 bg-accent-purple/10 px-2.5 py-1.5"
              >
                <img
                  src={icons.champion(name).url}
                  alt={name}
                  title={name}
                  className="h-7 w-7 rounded-md border border-gray-700"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                  }}
                />
                <span className="text-sm font-semibold text-text-primary">{name}</span>
                <button
                  onClick={() => removeChampion(name)}
                  className="ml-1 rounded-full p-1.5 text-text-muted transition-colors hover:bg-red-500/20 hover:text-red-400"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Pool full warning */}
        {pool.length >= 3 && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-orange-500/20 bg-orange-500/5 px-3 py-2">
            <AlertTriangle className="h-3.5 w-3.5 text-orange-400" />
            <span className="text-xs text-orange-300">
              Pool completo. Elimina un campeón antes de añadir otro.
            </span>
          </div>
        )}

        {/* Search Input */}
        {pool.length < 3 && (
          <div className="relative" ref={dropdownRef}>
            <input
              ref={inputRef}
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
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50"
            />

            {/* Dropdown */}
            {showDropdown && filtered.length > 0 && (
              <div className="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-border bg-card shadow-xl">
                {filtered.slice(0, 12).map((c) => (
                  <button
                    key={c.id}
                    onClick={() => addChampion(c.name)}
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

            {showDropdown && search.length > 0 && filtered.length === 0 && (
              <div className="absolute z-50 mt-1 w-full rounded-lg border border-border bg-card px-3 py-4 text-center shadow-xl">
                <span className="text-xs text-text-muted">
                  {champions.length === 0
                    ? 'Cargando campeones desde el backend...'
                    : `No se encontró "${search}"`}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Discipline OKRs Card */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4">
            <h2 className="flex items-center gap-2 text-base font-bold text-text-primary">
              <span className="text-base">📊</span>
              Discipline OKRs
            </h2>
            <p className="mt-0.5 text-xs text-text-muted">
              Los límites que te impone La Constitución. Si los incumples, la app te lo hará saber.
            </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {/* Target CS/min */}
          <div>
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-secondary">
                Target CS/min
              </label>
            <input
              type="number"
              value={targetCs}
              onChange={(e) => setTargetCs(e.target.value)}
              min="1"
              max="20"
              step="0.5"
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 font-mono text-sm text-text-primary outline-none transition-colors focus:border-accent-purple/50"
            />
            <p className="mt-1.5 text-[11px] text-text-muted">
              Si tu media baja de este valor, se marcará como <span className="text-orange-400">Slipping</span>.
            </p>
          </div>

          {/* Max Deaths */}
          <div>
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-secondary">
                Max Deaths / Game
              </label>
            <input
              type="number"
              value={maxDeaths}
              onChange={(e) => setMaxDeaths(e.target.value)}
              min="1"
              max="20"
              step="1"
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 font-mono text-sm text-text-primary outline-none transition-colors focus:border-accent-purple/50"
            />
            <p className="mt-1.5 text-[11px] text-text-muted">
              Si superas este tope, la app activará la alerta de <span className="text-red-400"> tilt</span>.
            </p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex items-center justify-between rounded-xl border border-border bg-card px-5 py-3">
        <div className="text-xs text-text-muted">
          {settings?.updated_at && (
            <span>Última guardado: {new Date(settings.updated_at).toLocaleString()}</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Feedback */}
          {saveState === 'success' && (
            <span className="flex items-center gap-1 text-xs font-medium text-emerald-400">
              <Check className="h-3.5 w-3.5" /> Guardado
            </span>
          )}
          {saveState === 'error' && (
            <span className="flex items-center gap-1 text-xs font-medium text-red-400">
              <AlertTriangle className="h-3.5 w-3.5" /> Error al guardar
            </span>
          )}

          <button
            onClick={handleSave}
            disabled={updateMutation.isPending || pool.length === 0}
            className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-bold transition-all active:scale-95 ${
              updateMutation.isPending
                ? 'cursor-not-allowed bg-gray-800 text-gray-500'
                : 'bg-accent-purple text-white shadow-lg shadow-accent-purple/20 hover:bg-accent-purple-dim'
            }`}
          >
            <Target className={`h-3.5 w-3.5 ${updateMutation.isPending ? 'animate-spin' : ''}`} />
            <Save className="h-3.5 w-3.5" />
            {updateMutation.isPending ? 'Guardando...' : 'Guardar Cambios'}
          </button>
        </div>
      </div>
    </div>
  )
}
