import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  getRoscoSnapshot,
  roscoAnswer,
  roscoTimeout,
  type GameRoom,
  type RoomRole,
  type RoscoLetter,
  type RoscoLetterStatus,
  type RoscoState,
} from '../api/client'
import { useRoscoClock } from '../hooks/useRoscoClock'

// 26 letras repartidas en 360º → una cada ~13.85º. La A arranca arriba (`-90`).
const ROSCO_STEP_DEG = 360 / 26
const LETTER_COUNT = 26

// ── resiliencia anti-limbo ────────────────────────────────────────────────────
// Los POST answer/timeout se reintentan SOLO cuando el fallo es de transporte (sin respuesta
// HTTP: red caída, uvicorn reiniciado con --reload, etc.). Un 4xx con `detail` es una decisión
// del árbitro y NO se reintenta (sí es accionable); un 5xx cuenta como transitorio (p. ej. el
// pool reabriéndose tras un reboot) y entra en la misma cesta.
const RETRY_MAX_ATTEMPTS = 3
const RETRY_BASE_MS = 750
const RETRY_MAX_BACKOFF_MS = 8000
// Watchdog: si el estado vivo no cambia durante demasiado rato (`STALL_THRESHOLD_MS`), el
// frontend pide el snapshot al árbitro (GET idempotente) para desenterrar la partida. Con
// uvicorn --reload el proceso local muere y `_sessions` se borra: sin este perro guardián el
// rival "idle" se quedaría congelado para siempre porque ningún broadcast vuelve a llegar.
const STALL_THRESHOLD_MS = 6000
const STALL_CHECK_MS = 2000

function isTransportError(err: unknown): boolean {
  if (!isAxiosError(err)) return false
  if (err.response === undefined) return true
  return (err.response.status ?? 0) >= 500
}

function apiErrorDetail(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return `❌ ${detail}`
  }
  return fallback
}

function countStatus(letters: RoscoLetter[], target: RoscoLetterStatus): number {
  return letters.filter((l) => l.status === target).length
}

// Letras no activas: color por estado (pendiente gris, acierto verde, fallo rojo).
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
  // El backend es la verdad del turno: el reloj corre SOLO si es tu turno y la partida vive.
  const inTurn = !isFinished && currentTurn === role

  // La "letra activa" la manda el BACKEND: es el puntero circular (`current_letter`) del jugador
  // EN TURNO. Avanza tras cada respuesta (acierto/fallo/pasapalabra) saltando las ya resueltas y
  // da la vuelta al abecedario hasta agotar las pendientes (Regla 2).
  const boardPlayer = currentTurn ? rosco?.players[currentTurn] ?? null : null
  const activeLetter = boardPlayer?.current_letter
    ? boardPlayer.letters.find((l) => l.letter === boardPlayer.current_letter) ?? null
    : null

  const [answer, setAnswer] = useState('')
  // Autofocus programático (el autoFocus nativo falla al re-renderizar turnos).
  const inputRef = useRef<HTMLInputElement>(null)

  // Re-sincronización con el árbitro: si el backend rechaza una respuesta (letra ya resuelta,
  // turno cambiado o partida cerrada sin `game_over`) este frontend puede haberse quedado atrás
  // al perder un broadcast Realtime. Pido la foto actual del árbitro y la aplico para
  // desatascar la pantalla sin que el jugador tenga que recargar la pestaña.
  const resync = () => {
    getRoscoSnapshot(room.room_code)
      .then(onRosco)
      .catch(() => {
        /* si la red tampoco responde, nos quedamos con el toast de error original */
      })
  }

  // Versión estable de `resync` para intervalos/watchdogs: se reasigna en cada render por lo
  // que el efecto no necesita re-suscribirse (y el linter no se queja de deps).
  const resyncRef = useRef(resync)
  resyncRef.current = resync

  // ── mutaciones ──────────────────────────────────────────────────────────────

  const timeoutMutation = useMutation({
    mutationFn: () => roscoTimeout(room.room_code),
    // Regla anti-limbo: reintenta SOLO fallos de transporte (sin respuesta HTTP). Si el primer
    // intento llegó al servidor y solo se perdió la respuesta, el reintento devuelve un 400 con
    // `detail` (no transporte) → onError → resync() → snapshot real del árbitro.
    retry: (failureCount, err) => failureCount < RETRY_MAX_ATTEMPTS && isTransportError(err),
    retryDelay: (attempt) => Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_BACKOFF_MS),
    onSuccess: (state) => {
      // `current_turn` None = el backend ya había cerrado la partida (reloj desincronizado):
      // mostramos el cierre, no el mensaje de participación agotada.
      if (state.current_turn === null) {
        toast('🏁 El Rosco ha terminado.', { duration: 8000 })
      } else {
        toast.error('⏱ Se agotó tu tiempo: terminaste tu participación en el Rosco.', { duration: 8000 })
      }
      onRosco(state)
    },
    onError: (err) => {
      toast.error(apiErrorDetail(err, 'No se pudo notificar el fin del turno.'))
      resync()
    },
  })

  const clock = useRoscoClock({
    active: inTurn,
    initialRemaining: me?.time_remaining ?? 0,
    // El cerrojo de un único disparo vive DENTRO del hook (useRef): garantiza que el POST
    // /timeout se emite una vez por turno, aunque el intervalo se limpie y se remonte.
    onExpire: () => timeoutMutation.mutate(),
  })

  // Regla 3 (hard-fix del deadlock): a 0 segundos el turno muere VISUALMENTE al instante,
  // aunque el backend aún no haya confirmado el timeout. Bloquea la UI (nada de escribir con el
  // reloj vacío) mientras llega la rotación del servidor.
  const timedOut = inTurn && clock <= 0
  const isMyTurn = inTurn && !timedOut

  const answerMutation = useMutation({
    mutationFn: (vars: { letter: string; answer: string }) =>
      roscoAnswer(room.room_code, {
        letter: vars.letter,
        answer: vars.answer,
        // Regla 4: el reloj lo lleva el frontend y se reporta en cada respuesta para el
        // desempate por tiempo restante.
        time_remaining: clock,
      }),
    // Regla anti-limbo: reintenta SOLO fallos de transporte (sin respuesta HTTP). Si el primer
    // intento llegó al servidor y solo se perdió la respuesta, el reintento devuelve un 400 con
    // `detail` (no transporte) → onError → resync() → snapshot real del árbitro.
    retry: (failureCount, err) => failureCount < RETRY_MAX_ATTEMPTS && isTransportError(err),
    retryDelay: (attempt) => Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_BACKOFF_MS),
    onSuccess: (state, vars) => {
      // Partida ya cerrada (una respuesta tardía de un reloj desincronizado): suerte al final.
      if (state.current_turn === null) {
        toast('🏁 El Rosco ha terminado.', { duration: 8000 })
        onRosco(state)
        return
      }
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
    onError: (err) => {
      toast.error(apiErrorDetail(err, 'No se pudo registrar la respuesta.'))
      resync()
    },
  })

  // ── efectos ─────────────────────────────────────────────────────────────────

  // Limpia el input al cambiar la letra activa o al recuperar/perder el turno. El cerrojo del
  // timeout vive en useRoscoClock (se rearma él solo en cada activación del reloj).
  useEffect(() => {
    setAnswer('')
  }, [activeLetter?.letter, isMyTurn])

  // El input se autoenfoca durante tu turno para que puedas jugar con el teclado sin ratón.
  // Histórico de la heurística: un `focus()` síncrono en el efecto corre ANTES de que el
  // navegador pinte el nodo (StrictMode y re-mounts) y no hace nada; con un `setTimeout` de 10ms
  // fallaba al RECUPERAR el turno tras un cambio (fallo o pasapalabra), porque React tarda más en
  // re-montar el `<form>`. La solución reintenta el foco en cada frame de animación (rAF = el DOM
  // ya está pintado) hasta confirmar que el input es el foco activo, con un último intento de
  // seguridad a 150ms. El cleanup cancela todo si el turno muere antes de que se dispare.
  useEffect(() => {
    if (!isMyTurn) return
    let cancelled = false
    let attempts = 0
    const MAX_ATTEMPTS = 12

    let rafId = 0
    const focusRetry = () => {
      if (cancelled || attempts >= MAX_ATTEMPTS) return
      attempts += 1
      const el = inputRef.current
      if (el) {
        el.focus()
        if (document.activeElement === el) return
      }
      rafId = requestAnimationFrame(focusRetry)
    }

    rafId = requestAnimationFrame(focusRetry)
    const safetyTimer = window.setTimeout(focusRetry, 150)
    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      clearTimeout(safetyTimer)
    }
  }, [isMyTurn, activeLetter?.letter])

  // ── watchdog anti-limbo ─────────────────────────────────────────────────────
  // El estado solo llega por broadcasts Realtime + respuestas REST (Regla 1). Un reinicio de
  // uvicorn con --reload mata `_sessions` en memoria y elimina el rosco en curso: el rival que
  // está esperando su turno (idle) no tiene ninguna mutación pendiente que reintentar y ningún
  // broadcast volverá a llegar → partida congelada. Este perro guardián solo interviene cuando
  // NO llega estado: si pasan STALL_THRESHOLD_MS sin un `rosco` nuevo, pide el snapshot al
  // árbitro y lo aplica (GET idempotente). Durante el juego normal los eventos son constantes y
  // el watchdog nunca dispara; en cuanto la partida cierra (`isFinished`) deja de molestar.
  const lastRoscoUpdateRef = useRef(Date.now())
  useEffect(() => {
    lastRoscoUpdateRef.current = Date.now()
  }, [rosco])

  useEffect(() => {
    if (isFinished) return
    const id = window.setInterval(() => {
      if (Date.now() - lastRoscoUpdateRef.current >= STALL_THRESHOLD_MS) resyncRef.current()
    }, STALL_CHECK_MS)
    return () => window.clearInterval(id)
  }, [room.room_code, room.status, isFinished])

  // ── acciones ────────────────────────────────────────────────────────────────

  // A los 0s el turno está muerto (`timedOut` ya forzó isMyTurn=false): bloquea input y
  // botones de forma estricta mientras el backend confirma el timeout y pasa el turno al rival.
  const busy = answerMutation.isPending || timeoutMutation.isPending || timedOut

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
    const danger = seconds < 10 // rojo bajo 10s (incluye el 0 tras agotarse, Regla 3)
    return (
      <div
        className={`rounded-xl border p-4 text-center ${
          active ? 'border-accent-primary/40 bg-accent-primary/10' : 'border-hairline bg-surface-1'
        }`}
      >
        <p className="mb-1 text-xs font-mono font-bold uppercase tracking-widest text-text-mute">
          {roleName(r)}
          {active ? ' · en turno' : ''}
        </p>
        <p
          className={`font-mono text-5xl font-black tabular-nums tracking-tight sm:text-6xl ${
            danger ? 'text-red-400' : active ? 'text-accent-primary' : 'text-text-ink'
          }`}
        >
          {Math.max(0, Math.ceil(seconds))}
        </p>
        <p className="mt-1 text-xs font-mono text-text-mute">
          seg · {countStatus(letters, 'success')}/{letters.length || LETTER_COUNT} aciertos
        </p>
      </div>
    )
  }

  const mySeconds = inTurn ? clock : me?.time_remaining ?? 0
  const sortedLetters = [...(boardPlayer?.letters ?? [])].sort((a, b) =>
    a.letter.localeCompare(b.letter),
  )

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-2 gap-4">
        {scoreCard(role, me, mySeconds, isMyTurn)}
        {scoreCard(rival, rivalPlayer, rivalPlayer?.time_remaining ?? 0, currentTurn === rival)}
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
            <h3 className="mb-4 text-center text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
              Rosco de {currentTurn ? roleName(currentTurn) : '—'}
            </h3>

            {/* Anillo real: 26 letras en órbita (ángulo = i · 360/26) con el texto siempre derecho. */}
            <div className="overflow-x-auto">
            <div className="relative mx-auto h-[26rem] w-[26rem] [--rosco-radius:11rem] sm:h-[32rem] sm:w-[32rem] sm:[--rosco-radius:14rem]">
              {sortedLetters.map((l, i) => {
                const angle = i * ROSCO_STEP_DEG - 90
                const isActive = isMyTurn && activeLetter?.letter === l.letter
                return (
                  <div
                    key={l.letter}
                    className="absolute left-1/2 top-1/2"
                    style={{
                      transform: `translate(-50%, -50%) rotate(${angle}deg) translate(var(--rosco-radius)) rotate(${-angle}deg)`,
                    }}
                  >
                    <span
                      className={`flex h-9 w-9 items-center justify-center rounded-xl border font-mono text-sm font-bold transition-all duration-150 sm:h-11 sm:w-11 sm:text-base ${
                        isActive
                          ? 'z-10 scale-125 border-accent-primary bg-accent-primary/20 text-accent-primary ring-4 ring-accent-primary/70 shadow-[0_0_22px_rgba(168,85,247,0.85)]'
                          : STATUS_CLASS[l.status]
                      }`}
                    >
                      {l.letter}
                    </span>
                  </div>
                )
              })}

              {/* Pregunta en el centro absoluto del anillo. */}
              <div className="absolute inset-0 flex flex-col items-center justify-center px-16 text-center">
                <span className="font-mono text-4xl font-black text-accent-primary sm:text-5xl">
                  {activeLetter?.letter ?? '—'}
                </span>
                <p className="mt-2 text-sm font-semibold leading-snug text-text-ink sm:text-base">
                  {activeLetter?.question ??
                    (isMyTurn ? 'Sin preguntas pendientes.' : 'El rival no tiene preguntas pendientes.')}
                </p>
              </div>
            </div>
            </div>
          </section>

          {isMyTurn ? (
            <section className="rounded-xl border border-accent-primary/30 bg-accent-primary/5 p-6">
              <form onSubmit={submitAnswer} className="flex flex-col gap-3 sm:flex-row">
                <input
                  ref={inputRef}
                  type="text"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={busy}
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
              <p className="flex items-center justify-center gap-2 text-sm text-text-body">
                <Loader2 className="h-4 w-4 animate-spin text-accent-primary" />
                {timedOut
                  ? '⏱ Tu tiempo se agotó: pasando el turno al rival…'
                  : '⏳ Turno del Rival… esperando su respuesta.'}
              </p>
            </section>
          )}
        </>
      )}
    </div>
  )
}
