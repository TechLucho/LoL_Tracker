import { useEffect, useRef, useState } from 'react'

// Regla 3 del Rosco: el reloj es un contador CONTINUO que solo corre mientras es tu turno.
// Un acierto NO lo detiene (sigues jugando la siguiente letra); solo se congela ante fallo o
// pasapalabra, cuando el turno pasa al rival. El backend no corre timers (es mono-proceso), así
// que el reloj vive aquí y se reporta en cada respuesta (`time_remaining`) para el desempate de
// la Regla 4. Al llegar a 0 se avisa UNA vez con `onExpire` para que el cliente notifique al
// backend vía `POST /rosco/timeout`.

const TICK_MS = 100

interface UseRoscoClockOptions {
  /** `true` mientras es tu turno y la partida sigue viva: el reloj corre. */
  active: boolean
  /** Segundos que le quedan al jugador según el servidor (se sincroniza al activarse). */
  initialRemaining: number
  /** Se dispara una sola vez cuando el reloj llega a 0. */
  onExpire?: () => void
}

/**
 * Devuelve los segundos restantes del reloj del jugador en turno.
 *
 * `initialRemaining` solo se aplica en la transición `active` false → true (cuando recuperas el
 * turno): así un acierto, que mantiene el turno y hace llegar un nuevo estado del servidor, NO
 * reinicia el contador — sigue corriendo desde el deadline original.
 *
 * Hard-fix del estado zombi: el disparo de `onExpire` está blindado por un `useRef` que garantiza
 * UN solo timeout por activación del reloj. El ref sobrevive a re-renders y a re-ejecuciones del
 * efecto (a diferencia de una variable local del closure), así que aunque el intervalo se limpie y
 * se monte de nuevo el endpoint se dispara exactamente una vez por turno.
 */
export function useRoscoClock({
  active,
  initialRemaining,
  onExpire,
}: UseRoscoClockOptions): number {
  const [remaining, setRemaining] = useState(() => Math.max(0, initialRemaining))
  const initialRef = useRef(initialRemaining)
  initialRef.current = initialRemaining
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire
  // Rastrea si el timeout ya se emitió en esta activación (false = aún puede dispararse).
  const expiredRef = useRef(false)

  useEffect(() => {
    if (!active) return

    // Nueva activación del reloj (turno nuevo): se puede volver a expirar una vez.
    expiredRef.current = false
    const start = Math.max(0, initialRef.current)
    setRemaining(start)
    if (start <= 0) {
      // Ya entró sin tiempo (banco agotado): el timeout de este turno se dispara ya mismo.
      if (!expiredRef.current) {
        expiredRef.current = true
        onExpireRef.current?.()
      }
      return
    }

    const deadline = Date.now() + start * 1000
    const timer = setInterval(() => {
      const left = Math.max(0, (deadline - Date.now()) / 1000)
      setRemaining(left)
      if (left <= 0 && !expiredRef.current) {
        expiredRef.current = true
        clearInterval(timer)
        onExpireRef.current?.()
      }
    }, TICK_MS)

    return () => clearInterval(timer)
  }, [active])

  return remaining
}
