import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Copy, DoorClosed, Loader2, Plus, Rocket } from 'lucide-react'
import { toast } from 'sonner'
import {
  advanceGameState,
  createGameRoom,
  joinGameRoom,
  type GameLiveState,
  type GameRoom,
} from '../api/client'
import { useAuth } from '../hooks/useAuth'
import {
  GRACE_PERIOD_SECONDS,
  useGameRoom,
  type ForfeitResult,
  type RoomRole,
} from '../hooks/useGameRoom'
import DraftingPhase from './DraftingPhase'
import MinigamesPhase from './MinigamesPhase'

function apiErrorDetail(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return `❌ ${detail}`
  }
  return fallback
}

function fmtCounter(totalSeconds: number): string {
  const m = Math.floor(Math.max(0, totalSeconds) / 60)
  const s = Math.max(0, totalSeconds) % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

const ROOM_STATUS_LABEL: Record<GameRoom['status'], string> = {
  lobby: 'Sala creada — esperando rival',
  drafting: 'Drafting por empezar',
  minigames: 'Minijuegos',
  rosco: 'El Rosco',
  finished: 'Partida terminada',
}

export default function RoscoLobby() {
  const { user } = useAuth()
  const userId = user?.id ?? null
  const [room, setRoom] = useState<GameRoom | null>(null)
  const [joinCode, setJoinCode] = useState('')
  const [live, setLive] = useState<GameLiveState | null>(null)

  const leaveRoom = () => setRoom(null)

  // El backend es el árbitro (Regla 1): su estado vivo (status, draft, bancos) llega tanto en
  // las respuestas REST como en los broadcasts Realtime; ambos caminos lo aplican igual.
  const applyLive = (state: GameLiveState) => {
    setLive(state)
    setRoom((r) => (r && r.status !== state.status ? { ...r, status: state.status } : r))
  }

  // ── acciones REST ───────────────────────────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: createGameRoom,
    onSuccess: (created) => {
      setRoom(created)
      toast.success(`✅ Sala ${created.room_code} creada. Comparte el código con tu rival.`)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo crear la sala.')),
  })

  const joinMutation = useMutation({
    mutationFn: (code: string) => joinGameRoom(code),
    onSuccess: (joined) => {
      setRoom(joined)
      toast.success(`✅ Te uniste a la sala ${joined.room_code}.`)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo unir a la sala.')),
  })

  const handleJoin = (e: FormEvent) => {
    e.preventDefault()
    if (joinCode.length !== 6) {
      toast.error('⚠️ El código de sala tiene 6 letras (ej. ABCDEF).')
      return
    }
    joinMutation.mutate(joinCode)
  }

  // lobby → drafting es decisión DEL HOST (el join ya no avanza de fase): lo dispara este botón.
  const advanceToDraftMutation = useMutation({
    mutationFn: () => advanceGameState(room?.room_code ?? '', 'drafting'),
    onSuccess: (state) => {
      toast.success('🚀 ¡Empieza el Drafting!')
      applyLive(state)
    },
    onError: (err) => toast.error(apiErrorDetail(err, 'No se pudo iniciar el Drafting.')),
  })

  // ── canal Supabase Realtime de la sala ──────────────────────────────────────

  const myRole: RoomRole | null =
    room && userId ? (room.host_id === userId ? 'host' : 'guest') : null

  const realtime = useGameRoom({
    room,
    currentUserId: userId,
    role: myRole,
    onForfeit: (result: ForfeitResult) => {
      if (result.loserRole === myRole) {
        toast.error('⚠️ Se agotó el grace period: pierdes por abandono.', { duration: 8000 })
      } else if (result.reason === 'host_gone') {
        toast.error('🏳️ El host desapareció: la sala se cierra y fuiste expulsado del juego.', {
          duration: 8000,
        })
      } else {
        toast.error('🚪 El invitado se desconectó y no volvió: ganas por abandono.', {
          duration: 8000,
        })
      }
    },
    onBroadcast: (broadcast) => applyLive(broadcast.payload),
  })

  // ── pantalla de inicio (crear / unirse) ─────────────────────────────────────

  if (!room) {
    return (
      <div className="mx-auto max-w-xl space-y-6">
        <header className="space-y-1">
          <h2 className="text-lg font-black uppercase tracking-wider text-accent-primary">
            🎮 El Rosco — Multijugador
          </h2>
          <p className="text-sm text-text-mute">
            Salas privadas por código de 6 letras. Compite en minijuegos y decide la victoria en
            la ronda alfabética final.
          </p>
        </header>

        <section className="rounded-xl border border-hairline bg-surface-1 p-6">
          <h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
            Crear Sala
          </h3>
          <p className="mb-4 text-sm text-text-body">
            Crea una sala y comparte el código de 6 letras con tu rival para que entre.
          </p>
          <button
            type="button"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="flex items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute disabled:shadow-none"
          >
            {createMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            {createMutation.isPending ? 'Creando…' : 'Crear Sala'}
          </button>
        </section>

        <section className="rounded-xl border border-hairline bg-surface-1 p-6">
          <h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
            Unirse a Sala
          </h3>
          <form onSubmit={handleJoin} className="flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={joinCode}
              onChange={(e) =>
                setJoinCode(e.target.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 6))
              }
              placeholder="CÓDIGO · 6 LETRAS"
              aria-label="Código de sala"
              className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm uppercase tracking-widest text-text-ink placeholder-text-mute outline-none transition-colors focus:border-accent-primary/50 sm:flex-1"
            />
            <button
              type="submit"
              disabled={joinMutation.isPending}
              className="flex items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute disabled:shadow-none"
            >
              {joinMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <DoorClosed className="h-4 w-4" />
              )}
              Entrar
            </button>
          </form>
        </section>
      </div>
    )
  }

  // ── pantalla de sala (presencia + grace period + fases) ─────────────────────

  const { status, connectionError, presence, playersReady, paused, absentRole, graceRemaining, forfeit } = realtime
  const canCopy = typeof navigator !== 'undefined' && Boolean(navigator.clipboard)

  const copyCode = () => {
    if (!canCopy) return
    void navigator.clipboard.writeText(room.room_code).then(
      () => toast.success('📋 Código copiado'),
      () => {},
    )
  }

  const playerRow = (roleKey: RoomRole, label: string) => {
    const present = Boolean(presence[roleKey])
    const isMe = myRole === roleKey
    return (
      <li className="flex items-center gap-3 py-2">
        <span
          className={`h-2 w-2 rounded-full transition-colors ${
            present ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-surface-2'
          }`}
        />
        <span className="text-sm font-medium text-text-ink">
          {label}
          {isMe ? ' (tú)' : ''}
        </span>
        <span className="ml-auto text-xs text-text-mute">
          {present ? 'Conectado' : 'Desconectado'}
        </span>
      </li>
    )
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-black uppercase tracking-wider text-accent-primary">
          🎮 El Rosco
        </h2>
        <span className="rounded-full bg-surface-2 px-3 py-1 text-xs font-mono font-bold uppercase tracking-widest text-text-body">
          {ROOM_STATUS_LABEL[room.status]}
        </span>
      </header>

      {/* Código compartible */}
      <section className="rounded-xl border border-hairline bg-surface-1 p-6">
        <h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
          Código de la Sala
        </h3>
        <div className="flex items-center justify-center gap-4 rounded-lg border border-hairline/50 bg-surface-2 p-5">
          <span className="font-mono text-4xl font-black tracking-[0.3em] text-text-ink">
            {room.room_code}
          </span>
          {canCopy && (
            <button
              type="button"
              onClick={copyCode}
              aria-label="Copiar código"
              className="rounded-lg border border-hairline bg-transparent p-2 text-text-body transition-colors hover:bg-canvas hover:text-text-ink"
            >
              <Copy className="h-4 w-4" />
            </button>
          )}
        </div>
      </section>

      {/* Banners globales (Regla 6 + estado de la conexión) */}
      {connectionError && (
        <section className="rounded-xl border border-amber-500/30 bg-amber-500/15 p-4">
          <p className="text-sm font-semibold text-amber-400">
            ⚠️ Canal de tiempo real no disponible (Supabase Realtime). La sala sigue operativa por
            API; revisa la conexión a internet.
          </p>
        </section>
      )}

      {forfeit && (
        <section className="rounded-xl border border-red-500/30 bg-red-500/15 p-5">
          <p className="mb-1 text-sm font-bold text-red-400">
            {forfeit.loserRole === myRole
              ? '⚠️ Se agotó el grace period: pierdes por abandono.'
              : forfeit.reason === 'host_gone'
                ? '🏳️ El host desapareció: la sala se cierra y el invitado queda expulsado.'
                : '🚪 El invitado abandonó la sala: el host gana por incomparecencia.'}
          </p>
          <p className="mb-4 text-xs text-text-mute">
            El resultado se registrará por el árbitro del backend (Sprint 4).
          </p>
          <button
            type="button"
            onClick={leaveRoom}
            className="rounded-lg border border-hairline bg-transparent px-4 py-2 text-sm font-semibold text-text-ink transition-colors hover:bg-surface-2"
          >
            Volver al lobby
          </button>
        </section>
      )}

      {paused && !forfeit && (
        <section className="rounded-xl border border-amber-500/30 bg-amber-500/15 p-5">
          <p className="text-sm font-semibold text-amber-400">
            ⏸ Partida pausada — el {absentRole === 'host' ? 'host' : 'invitado'} se desconectó.
          </p>
          <p className="mt-2 font-mono text-4xl font-black tracking-widest text-text-ink">
            {fmtCounter(graceRemaining ?? GRACE_PERIOD_SECONDS)}
          </p>
          <p className="mt-1 text-xs text-text-mute">
            Reconexión en curso… si agota el tiempo, el desconectado pierde por abandono.
          </p>
        </section>
      )}

      {/* Lobby: presencia del rival mientras la sala espera al invitado */}
      {room.status === 'lobby' && (
        <>
          <section className="rounded-xl border border-hairline bg-surface-1 p-6">
            <h3 className="mb-2 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
              Jugadores
            </h3>
            <ul className="divide-y divide-hairline/50">
              {playerRow('host', 'Host')}
              {playerRow('guest', 'Invitado')}
            </ul>
          </section>

          {playersReady && !paused && !forfeit && (
            <section className="space-y-4 rounded-xl border border-emerald-500/30 bg-emerald-500/15 p-4">
              <p className="text-sm font-bold text-emerald-400">✅ ¡Rival conectado! Sala lista.</p>
              {myRole === 'host' ? (
                <button
                  type="button"
                  onClick={() => advanceToDraftMutation.mutate()}
                  disabled={advanceToDraftMutation.isPending}
                  className="flex w-full items-center justify-center gap-2 rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-mute disabled:shadow-none"
                >
                  {advanceToDraftMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Rocket className="h-4 w-4" />
                  )}
                  {advanceToDraftMutation.isPending ? 'Iniciando…' : 'Pasar a Fase de Drafting'}
                </button>
              ) : (
                <p className="text-sm text-text-body">
                  ⏳ El host iniciará el Drafting cuando ambos estéis conectados.
                </p>
              )}
            </section>
          )}

          {status === 'waiting' && !paused && !forfeit && !connectionError && (
            <section className="rounded-xl border border-hairline bg-surface-1 p-4">
              <p className="flex items-center gap-2 text-sm text-text-body">
                <Loader2 className="h-4 w-4 animate-spin text-accent-primary" />
                Esperando al rival para sincronizar la sala…
              </p>
            </section>
          )}
        </>
      )}

      {/* Fases de la partida (el status llega por REST + broadcast Realtime) */}
      {room.status === 'drafting' && myRole && (
        <DraftingPhase room={room} role={myRole} live={live} onLive={applyLive} />
      )}

      {room.status === 'minigames' && myRole && (
        <MinigamesPhase room={room} role={myRole} live={live} onLive={applyLive} />
      )}

      {(room.status === 'rosco' || room.status === 'finished') && (
        <section className="rounded-xl border border-hairline bg-surface-1 p-6 text-center">
          <h3 className="mb-2 text-sm font-bold text-text-ink">
            {room.status === 'rosco' ? '🧩 El Rosco (Sprint 4)' : '🏁 Partida terminada'}
          </h3>
          <p className="text-xs text-text-mute">
            {room.status === 'rosco'
              ? 'La ronda alfabética que decide al campeón llega en el Sprint 4.'
              : 'Gracias por jugar. El resultado final se registrará cuando exista la máquina de estados del Rosco.'}
          </p>
        </section>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={leaveRoom}
          className="rounded-lg border border-hairline bg-transparent px-4 py-2 text-sm font-semibold text-text-mute transition-colors hover:bg-surface-2 hover:text-text-ink"
        >
          Abandonar sala
        </button>
      </div>
    </div>
  )
}