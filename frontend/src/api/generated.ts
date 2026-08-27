/**
 * Tipos re-exportados del esquema OpenAPI generado.
 *
 * Este archivo es el ÚNICO lugar que conecta el backend (schemas.py) con el frontend.
 * Para regenerar después de cambios en el backend:
 *
 *   cd backend && python -m backend.scripts.export_openapi
 *   cd frontend && npx openapi-typescript src/api/openapi.json -o src/api/schema.d.ts
 *
 * NO editar schema.d.ts a mano — se sobreescribe en cada generación.
 */

import type { components } from './schema'

// ──────────────────────── Backend schemas (fuente de verdad) ────────────────────────
// Re-exportamos los tipos del backend EXACTAMENTE como aparecen en OpenAPI.
// Si el backend cambia un campo, aquí se refleja automáticamente.

export type BackendMatch = components['schemas']['Match']
export type BackendParticipant = components['schemas']['Participant']
export type MatchUpdate = components['schemas']['MatchUpdate']

export type SyncResult = components['schemas']['SyncResult']
export type SyncAccepted = components['schemas']['SyncAccepted']
export type SyncStatus = components['schemas']['SyncStatus']
export type LpCapture = components['schemas']['LpCapture']

export type HealthStatus = components['schemas']['HealthStatus']

export type ChampionMeta = components['schemas']['ChampionMeta']
export type ItemMeta = components['schemas']['ItemMeta']
export type SpellMeta = components['schemas']['SpellMeta']
export type ChampionsIndex = components['schemas']['ChampionsIndex']
export type ItemsIndex = components['schemas']['ItemsIndex']
export type SpellsIndex = components['schemas']['SpellsIndex']

export type ChampionStats = components['schemas']['ChampionStats']
export type HeatmapCell = components['schemas']['HeatmapCell']

export type UserSettings = components['schemas']['UserSettings']
export type UserSettingsUpdate = components['schemas']['UserSettingsUpdate']

export type ConstitutionStatus = components['schemas']['ConstitutionStatus']
