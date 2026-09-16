import { useEffect, useRef, useState } from 'react'
import type { RealtimeChannel } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'
import type { GameLiveState, GameRoom } from '../api/client'

// ─── Constantes ───────────────────────────────────────────────────────────────
// Regla 6 (CHECKLIST 2026-09-13): grace period estricto de 60 segundos.
export const GRACE_PERIOD_SECONDS = 60
const GRACE_TICK_MS = 250

// ─── Tipos ────────────────────────────────────────────────────────────────────

export type RoomRole = 'host' | 'guest'

interface PresenceProfile {
  userId: string
  role: RoomRole
}

export type ForfeitReason = 'guest_abandoned' | 'host_gone'

export interface ForfeitResult {
  loserRole: RoomRole
  reason: ForfeitReason
}

export type RoomLinkStatus =
  | 'connecting'
  | 'waiting'
  | 'ready'
  | 'paused'
  | 'closed'

// ─── Estado expuesto ──────────────────────────────────────────────────────────

/** Evento de broadcast que el backend (árbitro) difunde a la sala. */
export interface GameBroadcast {
  event: 'state' | 'draft' | 'score'
  payload: GameLiveState
}

export interface UseGameRoomState {
  status: RoomLinkStatus
  connectionError: boolean
  /** Presence de cada rol (null si no se ha visto aún al jugador). */
  presence: Record<RoomRole, PresenceProfile | null>
  /** `true` cuando ambos jugadores están online y listos. */
  playersReady: boolean
  /** Regla 6: la partida está pausada esperando reconexión. */
  paused: boolean
  /** Rol del jugador que se desconectó. */
  absentRole: RoomRole | null
  /** Segundos restantes del grace period (60 → 0). */
  graceRemaining: number | null
  /** Resultado de la expiración del grace period. */
  forfeit: ForfeitResult | null
  /** Último evento de estado vivo emitido por el backend (nulo si aún no llegó ninguno). */
  lastBroadcast: GameBroadcast | null
}

// ─── Opciones ─────────────────────────────────────────────────────────────────

interface UseGameRoomOptions {
  room: GameRoom | null
  currentUserId: string | null
  role: RoomRole | null
  onForfeit?: (result: ForfeitResult) => void
  /** Se dispara con cada broadcast de estado vivo emitido por el backend (árbitro). */
  onBroadcast?: (broadcast: GameBroadcast) => void
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useGameRoom({
  room,
  currentUserId,
  role,
  onForfeit,
  onBroadcast,
}: UseGameRoomOptions): UseGameRoomState {
  const [subscribed, setSubscribed] = useState(false)
  const [connectionError, setConnectionError] = useState(false)
  const [presence, setPresence] = useState<Record<RoomRole, PresenceProfile | null>>({
    host: null,
    guest: null,
  })
  const [paused, setPaused] = useState(false)
  const [absentRole, setAbsentRole] = useState<RoomRole | null>(null)
  const [graceRemaining, setGraceRemaining] = useState<number | null>(null)
  const [forfeit, setForfeit] = useState<ForfeitResult | null>(null)
  const [lastBroadcast, setLastBroadcast] = useState<GameBroadcast | null>(null)

  // refs — actualizados por las funciones internas sin causar re-subscription
  const roleRef = useRef(role)
  roleRef.current = role
  const onForfeitRef = useRef(onForfeit)
  onForfeitRef.current = onForfeit
  const onBroadcastRef = useRef(onBroadcast)
  onBroadcastRef.current = onBroadcast
  const forfeitedRef = useRef(false)
  const sessionStartedRef = useRef(false)
  const graceEndsAtRef = useRef<number | null>(null)

  useEffect(() => {
    const code = room?.room_code
    if (!code || !currentUserId || !role) return

    // Reset estado entre suscripciones (cambio de sala / re-suscripción en StrictMode).
    setSubscribed(false)
    setConnectionError(false)
    setPresence({ host: null, guest: null })
    setPaused(false)
    setAbsentRole(null)
    setGraceRemaining(null)
    setForfeit(null)
    setLastBroadcast(null)
    forfeitedRef.current = false
    sessionStartedRef.current = false
    graceEndsAtRef.current = null

    const channel: RealtimeChannel = supabase.channel(`room:${code}`)
    let disposed = false
    let graceTimer: ReturnType<typeof setInterval> | null = null

    // ── presencia ──────────────────────────────────────────────────────────────

    function readPresence(): Record<RoomRole, PresenceProfile | null> {
      const profiles: Record<RoomRole, PresenceProfile | null> = { host: null, guest: null }
      for (const list of Object.values(channel.presenceState())) {
        for (const item of list) {
          const p = item as unknown as PresenceProfile
          if (p?.role === 'host' || p?.role === 'guest') {
            profiles[p.role] = { userId: p.userId, role: p.role }
          }
        }
      }
      if (!disposed) setPresence(profiles)
      return profiles
    }

    // ── grace period helpers ───────────────────────────────────────────────────

    function clearGraceTimer(): void {
      if (graceTimer !== null) {
        clearInterval(graceTimer)
        graceTimer = null
      }
      graceEndsAtRef.current = null
      setGraceRemaining(null)
      setAbsentRole(null)
      setPaused(false)
    }

    function startGrace(missing: RoomRole): void {
      if (!sessionStartedRef.current || forfeitedRef.current) return
      if (graceEndsAtRef.current !== null) return // ya en curso
      graceEndsAtRef.current = Date.now() + GRACE_PERIOD_SECONDS * 1000
      setGraceRemaining(GRACE_PERIOD_SECONDS)
      setAbsentRole(missing)
      setPaused(true)

      // arrancar ticker
      graceTimer = setInterval(() => {
        const endsAt = graceEndsAtRef.current
        if (endsAt === null) { clearGraceTimer(); return }
        const remaining = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000))
        setGraceRemaining(remaining)
        if (remaining > 0) return

        // ── expiración → forfeit ────────────────────────────────────────────
        clearInterval(graceTimer!)
        graceTimer = null
        if (forfeitedRef.current) return
        forfeitedRef.current = true

        const profiles = readPresence()
        const otherRole: RoomRole = roleRef.current === 'host' ? 'guest' : 'host'
        const loserRole: RoomRole = profiles.host ? 'guest' : profiles.guest ? 'host' : otherRole

        const result: ForfeitResult = {
          loserRole,
          reason: loserRole === 'host' ? 'host_gone' : 'guest_abandoned',
        }
        clearGraceTimer() // limpia estados de pausa
        setForfeit(result)
        onForfeitRef.current?.(result)
      }, GRACE_TICK_MS)
    }

    function evaluate(profiles: Record<RoomRole, PresenceProfile | null>): void {
      if (forfeitedRef.current) return
      const bothPresent = Boolean(profiles.host && profiles.guest)

      if (bothPresent) {
        sessionStartedRef.current = true
        clearGraceTimer()
        return
      }

      // Alguien falta → iniciar grace period si la sesión ya había comenzado.
      const missing: RoomRole | null = profiles.host ? 'guest' : profiles.guest ? 'host' : null
      if (missing) startGrace(missing)
    }

    // ── suscripción ────────────────────────────────────────────────────────────

    channel
      .on('presence', { event: 'sync' }, () => { evaluate(readPresence()) })
      .on('presence', { event: 'join' }, () => { evaluate(readPresence()) })
      .on('presence', { event: 'leave' }, () => { evaluate(readPresence()) })
      .on('system', { event: 'error' }, () => { setConnectionError(true) })
      // Estado vivo difundido por el backend (árbitro, Regla 1): el cliente es "tonto" y solo
      // pinta lo que llega. Los broadcasts de Realtime llegan aquí con la forma
      // `{ topic, event, payload }`, donde `payload` es el GameLiveState del backend.
      .on('broadcast', { event: 'state' }, (message: { payload: GameLiveState }) => {
        const broadcast: GameBroadcast = { event: 'state', payload: message.payload }
        if (!disposed) setLastBroadcast(broadcast)
        onBroadcastRef.current?.(broadcast)
      })
      .on('broadcast', { event: 'draft' }, (message: { payload: GameLiveState }) => {
        const broadcast: GameBroadcast = { event: 'draft', payload: message.payload }
        if (!disposed) setLastBroadcast(broadcast)
        onBroadcastRef.current?.(broadcast)
      })
      .on('broadcast', { event: 'score' }, (message: { payload: GameLiveState }) => {
        const broadcast: GameBroadcast = { event: 'score', payload: message.payload }
        if (!disposed) setLastBroadcast(broadcast)
        onBroadcastRef.current?.(broadcast)
      })
      .subscribe((status) => {
        if (disposed) return
        if (status === 'SUBSCRIBED') {
          setSubscribed(true)
          setConnectionError(false)
          void channel.track({ userId: currentUserId, role } satisfies PresenceProfile)
        } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
          setConnectionError(true)
        }
      })

    return () => {
      disposed = true
      clearGraceTimer()
      void channel.untrack().then(() => channel.unsubscribe())
    }
  }, [room?.room_code, currentUserId, role])

  // ── valores derivados ──────────────────────────────────────────────────────

  const playersReady = Boolean(presence.host && presence.guest)
  const status: RoomLinkStatus = forfeit
    ? 'closed'
    : paused
      ? 'paused'
      : connectionError
        ? 'connecting'
        : !subscribed
          ? 'connecting'
          : playersReady
            ? 'ready'
            : 'waiting'

  return {
    status,
    connectionError,
    presence,
    playersReady,
    paused,
    absentRole,
    graceRemaining,
    forfeit,
    lastBroadcast,
  }
}
