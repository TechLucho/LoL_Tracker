import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  roscoAnswer,
  roscoTimeout,
  type GameRoom,
  type RoomRole,
  type RoscoLetter,
  type RoscoLetterStatus,
  type RoscoState,
} from '../api/client'
import { useRoscoClock } from '../hooks/useRoscoClock'

function apiErrorDetail(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return `❌ ${detail}`
  }
  return fallback
}

function fmtClock(totalSeconds: number): string {
  const safe = Math.max(0, totalSeconds)
  const m = Math.floor(safe / 60)
  const s = Math.floor(safe % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function countStatus(letters: RoscoLetter[], target: RoscoLetterStatus): number {
  return letters.filter((l) => l.status === target).length
}

const STATUS_CLASS: Record<RoscoLetterStatus, string> = {
  pending: 'border-hairline bg-surface-2 text-text-mute',
  success: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-400',
  failed: 'border-red-500/40 bg-red-500/15 text-red-400',
}

interface RoscoPhaseProps {
  room: GameRoom
  role: RoomRole
  rosco: RoscoState | null
  onRosco: (state: RoscoState) => void
}

export default function RoscoPhase({ room, role, rosco, onRosco }: RoscoPhaseProps) {
  const rival: RoomRole = role === 'host' ? 'guest' : 'host'
  const roleName = (r: RoomRole) => (r === role ? 'Tú' : r === 'host' ? 'Host' : 'Invitado')

  const me = rosco?.players[role] ?? null
  const rivalPlayer = rosco?.players[rival] ?? null
  const currentTurn = rosco?.current_turn ?? null
  const isFinished = Boolean(rosco && currentTurn === null)
  const isMyTurn = !isFinished && currentTurn === role

  // La "letra activa" es la primera pendiente del jugador EN TURNO: como los aciertos la marcan
  // `success`, tras cada acierto la activa avanza sola a la siguiente letra.
  const boardPlayer = currentTurn ? rosco?.players[currentTurn] ?? null : null
  const activeLetter = boardPlayer?.letters.find((l) => l.status === 'pending') ?? null

  const [answer, setAnswer] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // ── mutaciones ──────────────────────────────────────────────────────────────

  const timeoutMutation = useMutation({
    mutationFn: () => roscoTimeout(room.room_code),
    onSuccess: (state) => {
      toast.error('⏱ Se agotó tu tiempo: terminaste tu participación en el Rosco.', { duration: 8000 })
      onRosco(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo notificar el fin del turno.')),
  })

  const clock = useRoscoClock({
    active: isMyTurn,
    initialRemaining: me?.time_remaining ?? 0,
    onExpire: () => {
      if (!timeoutMutation.isPending) timeoutMutation.mutate()
    },
  })

  const answerMutation = useMutation({
    mutationFn: (vars: { letter: string; answer: string }) =>
      roscoAnswer(room.room_code, {
        letter: vars.letter,
        answer: vars.answer,
        // Regla 4: el reloj lo lleva el frontend y se reporta en cada respuesta para el
        // desempate por tiempo restante.
        time_remaining: clock,
      }),
    onSuccess: (state, vars) => {
      const result = state.players[role]?.letters.find((l) => l.letter === vars.letter)?.status
      if (result === 'success') {
        toast.success(
          state.current_turn === role ? '✅ ¡Acierto! Sigues tú.' : '✅ ¡Acierto! Resolviste tus letras.',
        )
      } else if (result === 'failed') {
        toast.error('❌ Fallo. Turno del rival.')
      } else {
        toast('🔄 Pasapalabra. Turno del rival.')
      }
      onRosco(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo registrar la respuesta.')),
  })

  // ── efectos ─────────────────────────────────────────────────────────────────

  // Limpia el input al cambiar la letra activa o al recuperar/perder el turno.
  useEffect(() => {
    setAnswer('')
  }, [activeLetter?.letter, isMyTurn])

  // El input se autoenfoca durante tu turno para que puedas jugar con el teclado sin ratón.
  useEffect(() => {
    if (isMyTurn) inputRef.current?.focus()
  }, [isMyTurn, activeLetter?.letter])

  // ── acciones ────────────────────────────────────────────────────────────────

  const busy = answerMutation.isPending || timeoutMutation.isPending

  const submitAnswer = (e: FormEvent) => {
    e.preventDefault()
    if (!activeLetter || !isMyTurn || busy) return
    answerMutation.mutate({ letter: activeLetter.letter, answer })
  }

  const passLetter = () => {
    if (!activeLetter || !isMyTurn || busy) return
    answerMutation.mutate({ letter: activeLetter.letter, answer: '' })
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    // Espacio = pasapalabra SOLO con el input vacío (si hay texto, escribe un espacio normal).
    if (e.key === ' ' && answer.length === 0) {
      e.preventDefault()
      passLetter()
    }
  }

  // ── marcadores ──────────────────────────────────────────────────────────────

  const scoreCard = (r: RoomRole, player: typeof me, seconds: number, active: boolean) => {
    const letters = player?.letters ?? []
    return (
      <div
        className={`rounded-xl border p-4 ${
          active ? 'border-accent-primary/40 bg-accent-primary/10' : 'border-hairline bg-surface-1'
        }`}
      >
        <p className="mb-2 flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-text-mute">
          {roleName(r)}
          {active && <span className="text-accent-primary">● en turno</span>}
        </p>
        <p className="font-mono text-3xl font-black tracking-tight text-text-ink">
          {countStatus(letters, 'success')}
          <span className="ml-1 text-sm font-bold text-text-mute">/ {letters.length || 26}</span>
        </p>
        <p
          className={`mt-1 font-mono text-sm font-bold ${
            seconds <= 0 ? 'text-red-400' : active ? 'text-accent-primary' : 'text-text-body'
          }`}
        >
          ⏱ {seconds <= 0 ? 'Sin tiempo' : fmtClock(seconds)}
        </p>
      </div>
    )
  }

  const mySeconds = isMyTurn ? clock : me?.time_remaining ?? 0
  const sortedLetters = [...(boardPlayer?.letters ?? [])].sort((a, b) =>
    a.letter.localeCompare(b.letter),
  )

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
          Marcador — El Rosco
        </h3>
        <div className="grid grid-cols-2 gap-4">
          {scoreCard(role, me, mySeconds, isMyTurn)}
          {scoreCard(rival, rivalPlayer, rivalPlayer?.time_remaining ?? 0, currentTurn === rival)}
        </div>
      </section>

      {isFinished ? (
        <section
          className={`rounded-xl border p-6 text-center ${
            rosco?.draw
              ? 'border-amber-500/30 bg-amber-500/15'
              : rosco?.winner === role
                ? 'border-emerald-500/30 bg-emerald-500/15'
                : 'border-red-500/30 bg-red-500/15'
          }`}
        >
          <p className="mb-2 text-2xl font-black tracking-tight text-text-ink">
            {rosco?.draw ? '🤝 ¡Empate!' : rosco?.winner === role ? '🏆 ¡Ganaste!' : '😞 Perdiste'}
          </p>
          <p className="text-sm text-text-body">
            {roleName('host')}: {countStatus(rosco?.players.host?.letters ?? [], 'success')} aciertos ·{' '}
            {roleName('guest')}: {countStatus(rosco?.players.guest?.letters ?? [], 'success')} aciertos
          </p>
          <p className="mt-1 text-xs text-text-mute">Desempate por tiempo restante (Regla 4).</p>
        </section>
      ) : (
        <>
          <section className="rounded-xl border border-hairline bg-surface-1 p-6">
            <h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
              Rosco de {currentTurn ? roleName(currentTurn) : '—'}
            </h3>
            <div className="flex flex-wrap justify-center gap-1.5">
              {sortedLetters.map((l) => {
                const isActive = isMyTurn && activeLetter?.letter === l.letter
                return (
                  <span
                    key={l.letter}
                    className={`flex h-8 w-8 items-center justify-center rounded-md border font-mono text-sm font-bold transition-colors ${
                      STATUS_CLASS[l.status]
                    } ${isActive ? 'ring-2 ring-accent-primary/70' : ''}`}
                  >
                    {l.letter}
                  </span>
                )
              })}
            </div>
          </section>

          {isMyTurn ? (
            <section className="rounded-xl border border-accent-primary/30 bg-accent-primary/5 p-6">
              <h3 className="mb-1 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
                Letra {activeLetter?.letter ?? '—'}
              </h3>
              <p className="mb-4 text-lg font-semibold text-text-ink">
                {activeLetter?.question ?? 'Sin preguntas pendientes.'}
              </p>

              <form onSubmit={submitAnswer} className="flex flex-col gap-3 sm:flex-row">
                <input
                  ref={inputRef}
                  type="text"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={handleKeyDown}
                  autoFocus
                  placeholder="Escribe tu respuesta… (Espacio = pasapalabra)"
                  aria-label="Respuesta del Rosco"
                  className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 text-sm text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50 sm:flex-1"
                />
                <button
                  type="submit"
                  disabled={!activeLetter || busy}
                  className="flex items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute disabled:shadow-none"
                >
                  {answerMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {answerMutation.isPending ? 'Enviando…' : 'Responder (Enter)'}
                </button>
                <button
                  type="button"
                  onClick={passLetter}
                  disabled={!activeLetter || busy}
                  className="rounded-full border border-hairline bg-transparent px-6 py-2.5 text-sm font-semibold text-text-body transition-colors hover:bg-surface-2 hover:text-text-ink disabled:cursor-not-allowed disabled:text-text-mute/60"
                >
                  Pasapalabra (Espacio)
                </button>
              </form>
            </section>
          ) : (
            <section className="rounded-xl border border-hairline bg-surface-1 p-6">
              <h3 className="mb-1 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
                Letra {activeLetter?.letter ?? '—'}
              </h3>
              <p className="mb-4 text-lg font-semibold text-text-ink">
                {activeLetter?.question ?? 'El rival no tiene preguntas pendientes.'}
              </p>
              <p className="flex items-center gap-2 text-sm text-text-body">
                <Loader2 className="h-4 w-4 animate-spin text-accent-primary" />
                ⏳ Turno del Rival… esperando su respuesta.
              </p>
            </section>
          )}
        </>
      )}
    </div>
  )
}
