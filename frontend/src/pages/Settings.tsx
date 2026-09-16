import { useState, useEffect, useRef } from 'react'
import { Save, X, Shield, Target, AlertTriangle, Check, Swords } from 'lucide-react'
import { useSettings, useUpdateSettings, useLinkRiot } from '../hooks/useSettings'
import { useHealth } from '../hooks/useHealth'
import { toast } from 'sonner'
import { isAxiosError } from 'axios'
import { DDragon } from '../data/constants'
import { useChampionList, useIcons } from '../hooks/useMetadata'

const REGION_FALLBACK = ['EUW1', 'NA1', 'KR', 'JP1']

export default function SettingsPage() {
  const { data: settings, isLoading } = useSettings()
  const updateMutation = useUpdateSettings()
  const linkRiotMutation = useLinkRiot()
  const { data: health } = useHealth()

  // Metadatos servidos y cacheados por el backend (/api/metadata/champions): antes esta página
  // descargaba champion.json de Data Dragon directamente, con el parche hardcodeado en el cliente.
  const champions = useChampionList()
  const icons = useIcons()

  const [pool, setPool] = useState<string[]>([])
  const [riotId, setRiotId] = useState('')
  const [riotRegion, setRiotRegion] = useState('EUW1')
  const [targetCs, setTargetCs] = useState('7.5')
  const [maxDeaths, setMaxDeaths] = useState('4')
  const [targetDpm, setTargetDpm] = useState('500')
  const [targetKp, setTargetKp] = useState('50')
  const [targetVision, setTargetVision] = useState('20')
  const [search, setSearch] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'success' | 'error'>('idle')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Populate form when settings load
  useEffect(() => {
    if (settings) {
      setPool(settings.champion_pool)
      setRiotId(settings.riot_id)
      setRiotRegion(settings.riot_region)
      setTargetCs(String(settings.target_cs_min))
      setMaxDeaths(String(Math.round(settings.max_deaths)))
      setTargetDpm(String(settings.target_dpm ?? 500))
      setTargetKp(String(settings.target_kp_percent ?? 50))
      setTargetVision(String(settings.target_vision_score ?? 20))
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

  const handleLinkRiot = () => {
    if (!riotId.includes('#')) {
      toast.error('Formato del Riot ID: usa "Nombre#TAG" (ej. Lucho#EUW)')
      return
    }
    linkRiotMutation.mutate(
      { riot_id: riotId.trim(), region: riotRegion },
      {
        onSuccess: () => toast.success('✅ Riot ID actualizado'),
        onError: (err) => {
          const detail = isAxiosError(err)
            ? (err.response?.data as { detail?: string } | undefined)?.detail
            : undefined
          toast.error(detail ? `❌ ${detail}` : '❌ No se pudo vincular la cuenta Riot.')
        },
      },
    )
  }

  const handleSave = () => {
    const cs = parseFloat(targetCs)
    const deaths = parseInt(maxDeaths, 10)
    const dpm = parseInt(targetDpm, 10)
    const kp = parseInt(targetKp, 10)
    const vision = parseInt(targetVision, 10)
    if (isNaN(cs) || cs <= 0 || cs > 20) return
    if (isNaN(deaths) || deaths <= 0 || deaths > 20) return
    if (isNaN(dpm) || dpm <= 0 || dpm > 3000) return
    if (isNaN(kp) || kp <= 0 || kp > 100) return
    if (isNaN(vision) || vision <= 0 || vision > 200) return
    if (pool.length === 0) return

    setSaveState('idle')
    updateMutation.mutate(
      {
        champion_pool: pool,
        target_cs_min: cs,
        max_deaths: deaths,
        target_dpm: dpm,
        target_kp_percent: kp,
        target_vision_score: vision,
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
        <div className="shimmer h-6 w-48 rounded bg-surface-1" />
        <div className="shimmer h-40 rounded-xl bg-surface-1" />
        <div className="shimmer h-32 rounded-xl bg-surface-1" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-2 text-lg font-bold text-text-ink">
          <Shield className="h-5 w-5 text-accent-primary" />
          Configuración
        </h1>
        <p className="mt-1 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
          La base de La Constitución
        </p>
        <p className="mt-1 text-sm text-text-mute">
          Define tu pool, tus objetivos de rendimiento y tu cuenta Riot.
        </p>
      </div>

      {/* Riot Account Card */}
      <div className="rounded-xl border border-hairline bg-surface-1 p-6">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-text-ink">
              <Swords className="h-5 w-5 text-accent-primary" />
              Cuenta Riot
            </h2>
            <p className="mt-0.5 text-xs text-text-mute">
              Tu Riot ID alimenta el sync de partidas. La región debe ser la de tu servidor de colas.
            </p>
          </div>

          {/* API health indicator */}
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-hairline bg-canvas px-3 py-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                health?.status === 'ok' ? 'bg-emerald-400' : health ? 'bg-amber-400' : 'bg-text-mute'
              }`}
            />
            <span className="text-xs font-bold uppercase tracking-wider text-text-body">
              {health?.status === 'ok'
                ? 'API OK'
                : health
                  ? 'Degradada'
                  : 'Consultando...'}
            </span>
          </div>
        </div>

        {/* Current linkage */}
        {settings?.riot_id ? (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
            <Check className="h-4 w-4 shrink-0 text-emerald-400" />
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-bold text-text-ink">{settings.riot_id}</span>
              <span className="font-mono text-xs text-text-mute">{settings.riot_region}</span>
            </div>
          </div>
        ) : (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-hairline bg-canvas px-4 py-3">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <p className="text-xs text-text-mute">
              Sin cuenta vinculada. Conéctala para que la app pueda sincronizar tus partidas.
            </p>
          </div>
        )}

        {/* Edit form */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_130px_auto]">
          <label className="block">
            <span className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
              Riot ID
            </span>
            <input
              type="text"
              value={riotId}
              onChange={(e) => setRiotId(e.target.value)}
              placeholder="Nombre#TAG"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 text-sm text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
              Región
            </span>
            <select
              value={riotRegion}
              onChange={(e) => setRiotRegion(e.target.value)}
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
            >
              {(settings?.regions ?? REGION_FALLBACK).map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end">
            <button
              type="button"
              onClick={handleLinkRiot}
              disabled={linkRiotMutation.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute"
            >
              <Swords className={`h-3.5 w-3.5 ${linkRiotMutation.isPending ? 'animate-spin' : ''}`} />
              {linkRiotMutation.isPending ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </div>
      </div>

      {/* Champion Pool Card */}
      <div className="rounded-xl border border-hairline bg-surface-1 p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-text-ink">
              <span className="text-base">🎯</span>
              Champion Pool
            </h2>
            <p className="mt-0.5 text-xs text-text-mute">
              Máximo 3 campeones. La Constitución no te deja jugar lo que quieras.
            </p>
          </div>
          <span className="rounded-md bg-accent-primary/15 px-2 py-0.5 text-xs font-bold text-accent-primary">
            {pool.length}/3
          </span>
        </div>

        {/* Selected Champions */}
        {pool.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {pool.map((name) => (
              <div
                key={name}
                className="flex items-center gap-2 rounded-lg border border-accent-primary/30 bg-accent-primary/10 px-2.5 py-1.5"
              >
                <img
                  src={icons.champion(name).url}
                  alt={name}
                  title={name}
                  className="h-7 w-7 rounded-md border border-hairline"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                  }}
                />
                <span className="text-sm font-semibold text-text-ink">{name}</span>
                <button
                  onClick={() => removeChampion(name)}
                  className="ml-1 rounded-full p-1.5 text-text-mute transition-colors hover:bg-red-500/20 hover:text-red-400"
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
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50"
            />

            {/* Dropdown */}
            {showDropdown && filtered.length > 0 && (
              <div className="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-hairline bg-surface-1 shadow-xl">
                {filtered.slice(0, 12).map((c) => (
                  <button
                    key={c.id}
                    onClick={() => addChampion(c.name)}
                    className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm transition-colors hover:bg-surface-2"
                  >
                    <img
                      src={c.image}
                      alt={c.name}
                      className="h-6 w-6 rounded border border-hairline"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = DDragon.champion('Teemo')
                      }}
                    />
                    <span className="font-medium text-text-ink">{c.name}</span>
                  </button>
                ))}
              </div>
            )}

            {showDropdown && search.length > 0 && filtered.length === 0 && (
              <div className="absolute z-50 mt-1 w-full rounded-lg border border-hairline bg-surface-1 px-3 py-4 text-center shadow-xl">
                <span className="text-xs text-text-mute">
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
      <div className="rounded-xl border border-hairline bg-surface-1 p-6">
        <div className="mb-4">
            <h2 className="flex items-center gap-2 text-base font-bold text-text-ink">
              <span className="text-base">📊</span>
              Discipline OKRs
            </h2>
            <p className="mt-0.5 text-xs text-text-mute">
              Los límites que te impone La Constitución. Si los incumples, la app te lo hará saber.
            </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {/* Target CS/min */}
          <div>
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
                Target CS/min
              </label>
            <input
              type="number"
              value={targetCs}
              onChange={(e) => setTargetCs(e.target.value)}
              min="1"
              max="20"
              step="0.5"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
            />
            <p className="mt-1.5 text-xs text-text-mute">
              Si tu media baja de este valor, se marcará como <span className="text-orange-400">Slipping</span>.
            </p>
          </div>

          {/* Max Deaths */}
          <div>
              <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
                Max Deaths / Game
              </label>
            <input
              type="number"
              value={maxDeaths}
              onChange={(e) => setMaxDeaths(e.target.value)}
              min="1"
              max="20"
              step="1"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
            />
            <p className="mt-1.5 text-xs text-text-mute">
              Si superas este tope, la app activará la alerta de <span className="text-red-400"> tilt</span>.
            </p>
          </div>

          {/* Target DPM */}
          <div>
            <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
              Target DPM
            </label>
            <input
              type="number"
              value={targetDpm}
              onChange={(e) => setTargetDpm(e.target.value)}
              min="0"
              max="3000"
              step="50"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
            />
            <p className="mt-1.5 text-xs text-text-mute">
              Daño por minuto objetivo. Apunta a tu rol (lanes 550-650, jungla ~500).
            </p>
          </div>

          {/* Target KP% */}
          <div>
            <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
              Target KP%
            </label>
            <input
              type="number"
              value={targetKp}
              onChange={(e) => setTargetKp(e.target.value)}
              min="0"
              max="100"
              step="5"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
            />
            <p className="mt-1.5 text-xs text-text-mute">
              Participación en asesinatos objetivo. Rol de impacto (support/jungla) arriba del 60%.
            </p>
          </div>

          {/* Target Vision Score */}
          <div>
            <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-body">
              Target Vision Score
            </label>
            <input
              type="number"
              value={targetVision}
              onChange={(e) => setTargetVision(e.target.value)}
              min="0"
              max="200"
              step="5"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm text-text-ink outline-none transition-colors focus:border-accent-primary/50"
            />
            <p className="mt-1.5 text-xs text-text-mute">
              Puntuación de visión media por partida. Wardear un cuadrante y prioriza pink wards.
            </p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface-1 px-5 py-3">
        <div className="text-xs text-text-mute">
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
            className={`flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-bold transition-all active:scale-95 ${
              updateMutation.isPending
                ? 'cursor-not-allowed bg-surface-2 text-text-mute'
                : 'bg-accent-primary text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] hover:bg-accent-primary/90'
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
