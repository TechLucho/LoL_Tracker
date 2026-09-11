import type { UIMatch, UIParticipant } from './types'

export interface OkrTargets {
  target_dpm: number
  target_kp_percent: number
  target_vision_score: number
}

export interface OkrResult {
  label: string
  current: number
  target: number
  met: boolean
}

/**
 * Valida los tres objetivos de rendimiento de una partida contra las metas del usuario.
 *
 * En los tres casos "más es mejor": DPM, kill participation y vision score no tienen techo
 * que penalice al usuario (a diferencia del CS/min o las muertes). `kill_participation` se
 * guarda como ratio 0-1 en el JSONB, pero la meta (`target_kp_percent`) es entero 0-100:
 * la comparación se hace en porcentaje, nunca en ratio.
 */
export function computeOkrResults(
  me: UIParticipant,
  match: UIMatch,
  targets: OkrTargets,
): OkrResult[] {
  const dpm = match.dpm
  const kpPct = Math.round(match.kill_participation * 100)
  const vision = me.vision_score

  return [
    { label: 'DPM', current: dpm, target: targets.target_dpm, met: dpm >= targets.target_dpm },
    {
      label: 'KP%',
      current: kpPct,
      target: targets.target_kp_percent,
      met: kpPct >= targets.target_kp_percent,
    },
    {
      label: 'Visión',
      current: vision,
      target: targets.target_vision_score,
      met: vision >= targets.target_vision_score,
    },
  ]
}