# legacy/auth_v1 — Sistema de autenticación X-API-Token (archivado)

Con la v2.0 la autenticación pasó a delegarse en **Supabase Auth**: el backend valida los tokens
de sesión (`Authorization: Bearer <JWT>`, HS256 o ES256/RS256 vía JWKS) y cada tabla
transaccional pertenece a un `user_id` con RLS. El esquema anterior de **`X-API-Token`**
(secreto compartido en `APP_API_TOKEN`, app "mono-usuario") quedó obsoleto y se retiró del
árbol de código vivo. En vez de borrar esa historia, aquí queda archivada.

## Contenido

| Archivo | Original | Qué era |
| --- | --- | --- |
| `backend_deps.py` | `backend/app/deps.py` (pre-`511b041`) | `require_token` con `secrets.compare_digest` contra `APP_API_TOKEN`. |
| `backend_config.py` | `backend/app/config.py` (pre-`511b041`) | `Settings` con el campo `app_api_token`. |
| `frontend_client.ts` | `frontend/src/api/client.ts` (pre-`aa503d0`) | Interceptor axios que enviaba `X-API-Token` (env `VITE_API_TOKEN` + `localStorage["lol_tracker.api_token"]`). |
| `openapi_v1_contract.json` | `frontend/src/api/openapi.json` (snapshot v1) | Contrato OpenAPI que documentaba `x-api-token` en todas las operaciones. |

## Reglas de oro

- **NO importar desde aquí.** Ninguno de estos archivos se referencia desde el backend ni el
  frontend; son referencia histórica para auditorías y para entender el porqué de la v2.0.
- No reintroducir `X-API-Token`, `APP_API_TOKEN`, `VITE_API_TOKEN` ni
  `lol_tracker.api_token` en el código vivo. El auth de sesión es Supabase Auth.
- El `rate-limit` del proceso sigue siendo un guard grueso anti-abuso (clave por IP), ahora sin
  el branch de "token".

## Cronología de la transición (commits)

- `7e1823a` — inyectar RLS multi-usuario y delegar auth nativo a Supabase (migración 013,
  seed_auth_stub, CI con Postgres efímero).
- `511b041` — validación JWT HS256 en backend (deps.py V2, PyJWT, tests de auth).
- `aa503d0` — frontend: SDK Supabase, AuthContext, interceptor Bearer y página de Login.
- `f60f6ae` — soporte ES256/RS256 vía JWKS (PyJWKClient + `cryptography`).