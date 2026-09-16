import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Check, Loader2, Rocket, Swords } from 'lucide-react'
import { toast } from 'sonner'
import { advanceGameState, draftPick, type GameLiveState, type GameRoom, type RoomRole } from '../api/client'

// MANTENER EN SINCRONÍA con `DRAFT_CATEGORIES` de backend/app/services/live_game.py (Regla 1:
// el backend valida; esta lista solo pinta). El catálogo masivo de categorías llega en el
// Sprint 5.
const DRAFT_CATEGORIES = ['Lore', 'Mecánicas', 'Jugabilidad']

function apiErrorDetail(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return `❌ ${detail}`
  }
  return fallback
}

interface DraftingPhaseProps {
  room: GameRoom
  role: RoomRole
  live: GameLiveState | null
  onLive: (state: GameLiveState) => void
}

export default function DraftingPhase({ room, role, live, onLive }: DraftingPhaseProps) {
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

  const pickRow = (label: string, category: string | undefined, picked: boolean) => {
    return (
      <li className="flex items-center gap-3 py-2">
        <span
          className={`flex h-5 w-5 items-center justify-center rounded-full ${
            picked ? 'bg-emerald-400/15 text-emerald-400' : 'bg-surface-2 text-text-mute'
          }`}
        >
          {picked ? <Check className="h-3 w-3" /> : <span className="h-1.5 w-1.5 rounded-full bg-text-mute/50" />}
        </span>
        <span className="text-sm font-medium text-text-ink">{label}</span>
        <span className="ml-auto text-xs text-text-body">
          {category ?? 'Pendiente de elegir'}
        </span>
      </li>
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <h3 className="mb-2 flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
          <Swords className="h-4 w-4" /> Fase de Draft
        </h3>
        <p className="mb-4 text-sm text-text-body">
          Alternáis turnos para elegir cada uno <strong className="text-text-ink">1 categoría</strong>.
          Estas dos categorías alimentan los minijuegos de segundos extra (Regla 3).
        </p>

        <ul className="divide-y divide-hairline/50">
          {pickRow('Tú', myPick, Boolean(myPick))}
          {pickRow('Rival', rivalPick, Boolean(rivalPick))}
        </ul>

        {draftComplete && (
          <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/15 p-3">
            <p className="text-sm font-bold text-emerald-400">
              ✅ Draft completado ({live?.draft_picks.host} / {live?.draft_picks.guest})
            </p>
          </div>
        )}
      </section>

      {!draftComplete && (
        <section className="rounded-xl border border-hairline bg-surface-1 p-6">
          <h4 className="mb-1 text-sm font-bold text-text-ink">
            {isMyTurn ? '🎯 Es tu turno, elige categoría' : '⏳ Esperando a que el Rival elija…'}
          </h4>
          <p className="mb-4 text-xs text-text-mute">
            {isMyTurn
              ? 'Elige una categoría de la lista (no puedes repetir la del rival).'
              : 'El Draft es por turnos alternos: toca esperar y ver qué elige el rival.'}
          </p>
          <div className="flex flex-wrap gap-3">
            {DRAFT_CATEGORIES.map((category) => {
              const taken = Boolean(live?.draft_picks.host === category || live?.draft_picks.guest === category)
              return (
                <button
                  key={category}
                  type="button"
                  disabled={!isMyTurn || taken || pickMutation.isPending}
                  onClick={() => pickMutation.mutate(category)}
                  className={`rounded-full px-5 py-2 text-sm font-semibold transition-all active:scale-95 disabled:cursor-not-allowed ${
                    taken
                      ? 'border border-hairline bg-surface-2 text-text-mute/60 line-through'
                      : isMyTurn
                        ? 'bg-accent-primary/10 text-accent-primary shadow-[0_0_16px_rgba(168,85,247,0.25)] hover:bg-accent-primary/20 disabled:bg-surface-2 disabled:text-text-mute'
                        : 'border border-hairline bg-transparent text-text-mute'
                  }`}
                >
                  {taken && <Check className="mr-1.5 inline h-3 w-3" />}
                  {category}
                </button>
              )
            })}
          </div>
        </section>
      )}

      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <button
          type="button"
          disabled={!draftComplete || advanceMutation.isPending}
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
          {draftComplete
            ? 'Se habilita con ambas categorías elegidas. Al pulsarlo, ambos pasaréis a la fase de minijuegos.'
            : 'Se habilita cuando Tú y el rival hayáis elegido vuestra categoría.'}
        </p>
      </section>
    </div>
  )
}