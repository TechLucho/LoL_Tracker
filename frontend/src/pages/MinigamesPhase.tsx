import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Loader2, Sparkles, Timer, Trophy } from 'lucide-react'
import { toast } from 'sonner'
import { advanceGameState, submitScore, type GameLiveState, type GameRoom, type RoomRole } from '../api/client'

// Puntos simulados que concede el botón mock de "acertar pregunta" (Sprint 3). El backend
// convierte puntos → segundos (Regla 3: 1 punto = 1 segundo) en servicios/live_game.py.
const MOCK_ACERTAR_POINTS = 3

const OTHER: Record<RoomRole, RoomRole> = { host: 'guest', guest: 'host' }

function apiErrorDetail(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return `❌ ${detail}`
  }
  return fallback
}

interface MinigamesPhaseProps {
  room: GameRoom
  role: RoomRole
  live: GameLiveState | null
  onLive: (state: GameLiveState) => void
}

export default function MinigamesPhase({ room, role, live, onLive }: MinigamesPhaseProps) {
  const rival = OTHER[role]
  const myBank = live?.time_banks[role] ?? 100
  const rivalBank = live?.time_banks[rival] ?? 100
  const myCategory = live?.draft_picks[role] ?? '—'
  const rivalCategory = live?.draft_picks[rival] ?? '—'

  const scoreMutation = useMutation({
    mutationFn: () => submitScore(room.room_code, MOCK_ACERTAR_POINTS),
    onSuccess: (state) => {
      toast.success(`✅ ¡Acertaste! +${MOCK_ACERTAR_POINTS}s para tu banco.`)
      onLive(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo sumar el punto.')),
  })

  const advanceMutation = useMutation({
    mutationFn: () => advanceGameState(room.room_code, 'rosco'),
    onSuccess: (state) => {
      toast.success('🏆 ¡Minijuegos terminados! La ronda del Rosco decide al campeón.')
      onLive(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo pasar al Rosco.')),
  })

  const bankCard = (label: string, seconds: number, highlight: boolean) => (
    <div
      className={`rounded-xl border p-5 text-center ${
        highlight
          ? 'border-accent-primary/40 bg-accent-primary/10'
          : 'border-hairline bg-surface-1'
      }`}
    >
      <p className="mb-1 text-xs font-mono font-bold uppercase tracking-widest text-text-mute">{label}</p>
      <p className={`font-mono text-4xl font-black tracking-tight ${highlight ? 'text-accent-primary' : 'text-text-ink'}`}>
        {Math.round(seconds)}
        <span className="ml-1 text-sm font-bold text-text-mute">s</span>
      </p>
    </div>
  )

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <h3 className="mb-2 flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
          <Timer className="h-4 w-4" /> Minijuegos — Banco de Tiempo (Regla 3)
        </h3>
        <p className="mb-4 text-sm text-text-body">
          Cada jugador arranca con <strong className="text-text-ink">100 segundos</strong> base y
          solo suma los segundos que <strong className="text-text-ink">él mismo</strong> gana en
          los minijuegos. Categorías: <strong className="text-text-ink">{myCategory}</strong>{' '}
          (tuyas) vs <strong className="text-text-ink">{rivalCategory}</strong> (del rival).
        </p>

        <div className="grid grid-cols-2 gap-4">
          {bankCard('Tú', myBank, true)}
          {bankCard(`Rival (${rival === 'host' ? 'host' : 'invitado'})`, rivalBank, false)}
        </div>
        <p className="mt-3 text-center text-xs text-text-mute">
          El banco de 100s + lo acumulado alimenta tu reloj continuo de la ronda final del Rosco
          (Regla 3).
        </p>
      </section>

      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <h4 className="mb-2 text-sm font-bold text-text-ink">🎮 Minijuego mock (Sprint 3)</h4>
        <p className="mb-4 text-xs text-text-mute">
          Interfaz provisional para probar la suma de segundos: cada clic envía{' '}
          <strong className="text-text-body">{MOCK_ACERTAR_POINTS} puntos</strong> al backend, que
          los valida y los convierte en segundos para tu banco individual.
        </p>
        <button
          type="button"
          disabled={scoreMutation.isPending}
          onClick={() => scoreMutation.mutate()}
          className="flex items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute disabled:shadow-none"
        >
          {scoreMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {scoreMutation.isPending ? 'Enviando…' : `Acertar Pregunta (+${MOCK_ACERTAR_POINTS}s)`}
        </button>
      </section>

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
                <Trophy className="h-4 w-4" />
              )}
              {advanceMutation.isPending ? 'Avanzando…' : 'Terminar Minijuegos → El Rosco'}
            </button>
            <p className="mt-3 text-center text-xs text-text-mute">
              Al pulsarlo empieza El Rosco: la ronda alfabética que decide al campeón.
            </p>
          </>
        ) : (
          <p className="text-center text-sm text-text-body">
            ⏳ Esperando a que el Host inicie El Rosco…
          </p>
        )}
      </section>
    </div>
  )
}