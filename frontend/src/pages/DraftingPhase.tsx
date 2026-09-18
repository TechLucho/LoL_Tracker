import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Check, Loader2, Rocket, Sparkles, Swords, X } from 'lucide-react'
import { toast } from 'sonner'
import { advanceGameState, draftPick, type GameLiveState, type GameRoom, type RoomRole } from '../api/client'

// MANTENER EN SINCRONÍA con `DRAFT_CATEGORIES` de backend/app/services/live_game.py (Regla 1:
// el backend valida; esta lista solo pinta). El catálogo masivo de categorías llega en el
// Sprint 5.
const DRAFT_CATEGORIES = ['Lore', 'Mecánicas', 'Jugabilidad']

// Animación de revelado del draft antes de lanzar los minijuegos.
const ANIMATION_MS = 1600

function apiErrorDetail(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return `❌ ${detail}`
  }
  return fallback
}

function shuffle<T>(items: T[]): T[] {
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

interface DraftingPhaseProps {
  room: GameRoom
  role: RoomRole
  live: GameLiveState | null
  onLive: (state: GameLiveState) => void
}

export default function DraftingPhase({ room, role, live, onLive }: DraftingPhaseProps) {
  // Fase previa (Sprint 5): las 3 categorías se esconden tras cartas "misterio" y cada jugador
  // revela UNA al elegir. El orden de las cartas es aleatorio por sesión (estética únicamente:
  // la autoridad sigue siendo el backend).
  const [mysteryOrder] = useState(() => shuffle(DRAFT_CATEGORIES))
  const myPick = live?.draft_picks[role]
  const rivalPick = live?.draft_picks[role === 'host' ? 'guest' : 'host']
  const draftComplete = Boolean(live?.draft_picks.host && live?.draft_picks.guest)
  // El draft arranca por el host (LiveSession en el backend); si aún no ha llegado el estado
  // vivo (live null), el turno por defecto es del host (Regla 1).
  const draftTurn = live?.draft_turn ?? 'host'
  const isMyTurn = draftTurn === role

  const pickMutation = useMutation({
    mutationFn: (category: string) => draftPick(room.room_code, category),
    onSuccess: (state) => {
      toast.success(`✅ Elegiste: ${state.draft_picks[role]}`)
      onLive(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo registrar tu elección.')),
  })

  const advanceMutation = useMutation({
    mutationFn: () => advanceGameState(room.room_code, 'minigames'),
    onSuccess: (state) => {
      toast.success('🚀 ¡Draft completado! Empiezan los minijuegos.')
      onLive(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo pasar a minijuegos.')),
  })
  const advanceRef = useRef(advanceMutation)
  advanceRef.current = advanceMutation

  // Revelado: al completarse el draft aparece la animación de "montaje" durante ANIMATION_MS.
  const [animating, setAnimating] = useState(false)
  useEffect(() => {
    if (!draftComplete) {
      setAnimating(false)
      return
    }
    setAnimating(true)
    const t = window.setTimeout(() => setAnimating(false), ANIMATION_MS)
    return () => window.clearTimeout(t)
  }, [draftComplete])

  // Auto-avance (host): cuando ambos eligieron y la animación terminó, salta solo a 'minigames'.
  // El ref evita dispararlo dos veces (StrictMode); si el POST falla, el botón manual hace de retry.
  const advanceFiredRef = useRef(false)
  useEffect(() => {
    if (!draftComplete || animating || role !== 'host' || advanceFiredRef.current) return
    advanceFiredRef.current = true
    advanceRef.current.mutate()
  }, [draftComplete, animating, role])

  // Categoría que quedó descartada (la 3ª no elegida por nadie).
  const discarded = DRAFT_CATEGORIES.filter((c) => c !== myPick && c !== rivalPick)[0]

  const pickedByRole = (category: string): RoomRole | null =>
    myPick === category ? role : rivalPick === category ? (role === 'host' ? 'guest' : 'host') : null

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <h3 className="mb-2 flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
          <Swords className="h-4 w-4" /> Fase de Draft
        </h3>
        <p className="mb-4 text-sm text-text-body">
          Cada uno revela <strong className="text-text-ink">1 de las 3 categorías misteriosas</strong>{' '}
          (sin repetir la del rival). Las dos elegidas alimentan los minijuegos de segundos extra
          (Regla 3); la tercera se descarta.
        </p>

        <div className="grid grid-cols-3 gap-3">
          {mysteryOrder.map((category) => {
            const pickedBy = pickedByRole(category)
            const picked = Boolean(pickedBy)
            return (
              <button
                key={category}
                type="button"
                disabled={!isMyTurn || picked || pickMutation.isPending}
                onClick={() => pickMutation.mutate(category)}
                className={`flex min-h-28 flex-col items-center justify-center gap-2 rounded-xl border p-3 transition-all active:scale-95 disabled:cursor-not-allowed ${
                  picked
                    ? 'border-accent-primary/40 bg-accent-primary/10 shadow-[0_0_16px_rgba(168,85,247,0.15)]'
                    : isMyTurn
                      ? 'border-hairline bg-surface-2 transition-colors hover:border-accent-primary/40 hover:shadow-[0_0_16px_rgba(168,85,247,0.2)] disabled:border-hairline disabled:shadow-none'
                      : 'border-hairline bg-surface-2/50'
                }`}
              >
                {picked ? (
                  <>
                    <Sparkles className="h-6 w-6 text-accent-primary" />
                    <span className="text-sm font-bold text-text-ink">{category}</span>
                    <span className="text-xs font-mono font-bold uppercase tracking-widest text-text-mute">
                      {pickedBy === 'host' ? 'Host' : 'Invitado'}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-4xl font-black leading-none text-text-body">?</span>
                    <span className="text-xs font-mono uppercase tracking-widest text-text-mute">
                      Categoría misteriosa
                    </span>
                  </>
                )}
              </button>
            )
          })}
        </div>

        <p className="mt-3 text-xs text-text-mute">
          {draftComplete
            ? 'Draft completado: las dos categorías elegidas van a los minijuegos.'
            : isMyTurn
              ? 'Toca tu turno: elige una carta sin revelar.'
              : 'Esperando al rival para que elija su carta…'}
        </p>
      </section>

      {!draftComplete && (
        <section className="rounded-xl border border-hairline bg-surface-1 p-6">
          <h4 className="mb-1 text-sm font-bold text-text-ink">
            {isMyTurn ? '🎯 Es tu turno, elige categoría' : '⏳ Esperando a que el Rival elija…'}
          </h4>
          <p className="mb-4 text-xs text-text-mute">
            {isMyTurn
              ? 'Pulsa una de las cartas misteriosas. No puedes repetir la categoría del rival.'
              : 'El Draft es por turnos alternos: el rival revelará una categoría y después juegas tú.'}
          </p>
        </section>
      )}

      {draftComplete && (
        <section className="rounded-xl border border-hairline bg-surface-1 p-6">
          <div
            className={`rounded-lg border p-4 transition-colors ${
              animating
                ? 'border-accent-primary/40 bg-accent-primary/10'
                : 'border-emerald-500/30 bg-emerald-500/15'
            }`}
          >
            <p
              className={`flex items-center gap-2 text-sm font-bold ${
                animating ? 'text-accent-primary' : 'text-emerald-400'
              }`}
            >
              {animating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Montando los minijuegos…
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" /> Minijuegos definidos
                </>
              )}
            </p>
            <ul className="mt-3 space-y-2">
              {[myPick, rivalPick].map((category) => (
                <li
                  key={category}
                  className="flex items-center gap-3 rounded-lg border border-hairline/50 bg-surface-2 px-3 py-2"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent-primary/15 text-accent-primary">
                    <Swords className="h-3.5 w-3.5" />
                  </span>
                  <span className="text-sm font-medium text-text-ink">{category}</span>
                </li>
              ))}
              <li className="flex items-center gap-3 rounded-lg border border-hairline/50 bg-surface-2/50 px-3 py-2 opacity-50">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-2 text-text-mute">
                  <X className="h-3.5 w-3.5" />
                </span>
                <span className="text-sm text-text-body line-through">{discarded}</span>
              </li>
            </ul>
          </div>
        </section>
      )}

      {draftComplete && !animating && (
        <section className="rounded-xl border border-hairline bg-surface-1 p-6">
          {role === 'host' ? (
            <>
              <button
                type="button"
                disabled={advanceMutation.isPending}
                onClick={() => advanceMutation.mutate()}
                className="flex w-full items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute disabled:shadow-none"
              >
                {advanceMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Rocket className="h-4 w-4" />
                )}
                {advanceMutation.isPending ? 'Avanzando…' : 'Comenzar Minijuegos'}
              </button>
              <p className="mt-3 text-center text-xs text-text-mute">
                {advanceMutation.isError
                  ? 'El avance automático falló: pulsa el botón para reintentarlo.'
                  : 'Se lanza automáticamente; el botón sirve de reintento si algo falla.'}
              </p>
            </>
          ) : (
            <p className="text-center text-sm text-text-body">
              ⏳ Esperando a que el Host inicie los minijuegos…
            </p>
          )}
        </section>
      )}
    </div>
  )
}