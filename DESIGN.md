# DESIGN.md

Hoja de estilos y reglas visuales del frontend (React SPA + Tailwind CSS **v4**). Este documento es la
única referencia de diseño del proyecto. Cuando toques la UI, mantené los patrones aquí documentados
antes de inventar clases nuevas.

## Stack y filosofía

- **Tailwind v4, CSS-first**: los tokens viven en `frontend/src/index.css` (`@theme`). **No hay
  `tailwind.config.js`** — no crear uno.
- **Dark-only**: no existe variante `dark:`. El body fuerza `#0A0A0F`.
- UI strings en español; identificadores y columnas de BD en inglés. Emoji en labels es intencional.
- Sin formatter; lint con `oxlint`.

## Design tokens (fuente de verdad)

Definidos en `frontend/src/index.css:3-20` (bloque `@theme`):

| Token | Valor | Clase generada |
| --- | --- | --- |
| `--color-background` | `#0F0F13` | `bg-background` |
| `--color-card` | `#1A1A21` | `bg-card` |
| `--color-card-hover` | `#22222B` | `bg-card-hover` |
| `--color-accent-purple` | `#A855F7` | `bg-accent-purple` / `text-accent-purple` |
| `--color-accent-purple-dim` | `#7C3AED` | `bg-accent-purple-dim` |
| `--color-status-win` | `#059669` | *(sin uso en componentes)* |
| `--color-status-win-bg` | `#05966920` | *(sin uso en componentes)* |
| `--color-status-loss` | `#991B1B` | *(sin uso en componentes)* |
| `--color-status-loss-bg` | `#991B1B20` | *(sin uso en componentes)* |
| `--color-border` | `#2A2A35` | `border-border` |
| `--color-text-primary` | `#F3F4F6` | `text-text-primary` |
| `--color-text-secondary` | `#9CA3AF` | `text-text-secondary` |
| `--color-text-muted` | `#6B7280` | `text-text-muted` |
| `--font-sans` | `"Inter", system-ui, -apple-system, sans-serif` | `font-sans` |
| `--font-mono` | `"JetBrains Mono", ui-monospace, monospace` | `font-mono` |

CSS base en `index.css`:

- `body { background-color: #0A0A0F; color: var(--color-text-primary); font-family: var(--font-sans); }`
  con `-webkit-font-smoothing: antialiased`.
- Animación `page-enter` → clase `.animate-page-enter` (fade + `translateY(8px)`, 0.3s `ease-out`).
  Se aplica al wrapper de contenido, keyed por `pathname` en `Layout.tsx`.
- Skeleton **shimmer**: clase `.shimmer` (bloque base con `overflow-hidden` + `::after` que barre un
  gradiente `transparent → rgba(255,255,255,0.07) → transparent`, 1.6s infinito). Sustituye al pulse.
- Scrollbars: finas (`width: 6px`), thumb `#2A2A35`.

## Paleta

### Escala de neutros (la base del "negro")

| Clase | Hex | Uso |
| --- | --- | --- |
| `bg-[#0A0A10]` | `#0A0A10` | Tabs pills selector, fondo de paginación, "Cargar más" |
| `bg-[#0D0D12]` | `#0D0D12` | Inputs de review, filas internas, celdas vacías, accordion expandido |
| `bg-[#14141C]` | `#14141C` | **Tarjeta estándar fuerte** de dashboard (matches, KPIs, heatmap) |
| `bg-[#1A1A24]` | `#1A1A24` | Sub-cards / stat boxes internos, tooltips, hover de filas |
| `bg-card` | `#1A1A21` | Sidebar, headers móvil, cards de Settings/Login/Onboarding/Matchups |
| `bg-card-hover` | `#22222B` | Hover de nav links, hamburguesa, dropdowns |
| `border-border` | `#2A2A35` | Bordes semánticos (tokens) |
| `border-gray-800` | `#1f2937` | Borde de cards dashboard (raw) |
| `text-text-primary` | `#F3F4F6` | Texto principal |
| `text-text-secondary` | `#9CA3AF` | Labels secundarios, nav |
| `text-text-muted` | `#6B7280` | Hints, placeholders, versión |

### Acento de marca (púrpura)

| Clase | Valor | Uso |
| --- | --- | --- |
| `bg-accent-purple` | `#A855F7` | Botones primarios "oficiales" (Login, Onboarding, Settings) |
| `bg-accent-purple-dim` | `#7C3AED` | Hover de botón primario |
| `bg-purple-500` | raw Tailwind | Botones primarios de tabla/accordion, tabs activos |
| `text-purple-400` | raw Tailwind | Títulos de sección de cards |
| `text-purple-300` | raw Tailwind | Nombre propio en partidas |
| `bg-accent-purple/15 text-accent-purple` | — | Nav link activo |
| `bg-purple-500/10 text-purple-400/300` | — | Botones secundarios ghost, badges "LAST 5 vs PREV 5" |
| `shadow-purple-500/20` | — | Glow de botones y tabs activos |
| `ring-purple-500/30` / `ring-purple-500/40` | — | Paginación / fila del jugador propio |

### Semáforo victoria / derrota

Los tokens `status-*` del `@theme` **no se usan**: los componentes aplican directo la escala emerald/red.

**Victoria (emerald):**
- Badge `VICTORY`: `bg-emerald-500/20 text-emerald-400`
- Paneles positivos: `bg-emerald-500/5 border-emerald-500/20`
- Gradiente de fila victoriosa: `bg-gradient-to-r from-emerald-500/[0.09] via-emerald-500/[0.03] to-transparent`
- Valores `text-emerald-400`; winrate 50-60% → `text-emerald-300`

**Derrota (red):**
- Badge `DEFEAT`: `bg-red-500/20 text-red-400`
- Paneles negativos: `bg-red-500/5 border-red-500/20`
- Gradiente de fila: `bg-gradient-to-r from-red-500/[0.09] via-red-500/[0.03] to-transparent`
- Valores `text-red-400`; errores `text-red-300`

### Estados de alerta y equipos

- **Amber/Yellow** — warnings: banners `border-amber-500/30 bg-amber-500/15`, `bg-yellow-500/10
  border-yellow-500/30` (Constitución WARNING), `text-amber-400`/`text-yellow-400`.
- **Orange** — métricas excepcionales: rating ≥ 80, DPM ≥ 700, backend caído (`text-orange-400`,
  `bg-orange-500/15 border-orange-500/30`).
- **Blue** — equipo azul e info: `bg-blue-500/10 text-blue-400`, `bg-blue-500` (barra de daño),
  dot `bg-blue-400`.
- **Cyan** — vision (gráficos): `text-cyan-400`, color de gráfico `#06B6D4`.

### Spinner de loading

`animate-spin`, `h-4 w-4` / `h-8 w-8`, en iconos de estado de carga.

## Tipografía

- **Sans**: Inter (fuente UI completa).
- **Mono**: JetBrains Mono — **todos los valores numéricos** (KDA, CS, DPM, KP%, rating, winrate,
  LP, inputs numéricos). Cumple el rol de `tabular-nums` (los dígitos ya son tabulares en la fuente).

Escala usada:

| Clase | Uso |
| --- | --- |
| `text-[8px]` / `text-[9px]` | Badges de rol, stats diminutos, leyendas |
| `text-[10px]` / `text-[11px]` | Labels de sección, metadata, pills, hints, version |
| `text-xs` | Labels, dropdowns, tags |
| `text-sm` | Cuerpo: inputs, labels, nombres de campeón |
| `text-base` | Valores de fila de partida (KDA/CS/KP/DPM) |
| `text-lg` | Títulos de página, logo, emojis |
| `text-xl` | Ratings en accordion |
| `text-2xl` | Rating principal en tabla, impact |
| `text-4xl` | Winrate y BigStatCard |

Pesos: `font-medium` (labels), `font-semibold` (tabs/pills), `font-bold` (títulos, botones),
`font-black` (títulos uppercase, números grandes). Tracking: `tracking-tight` (logo), `tracking-wider`
(labels uppercase de pil), `tracking-widest` (títulos de sección de cards). Los títulos de sección de
cards usan el patrón `text-[10px] font-bold uppercase tracking-widest` + `text-text-muted`.

## Layout y spacing

- **App shell** (`Layout.tsx`): `flex h-screen flex-col` → `HealthBanner` → `flex min-h-0 flex-1`
  (sidebar `w-56` + `main flex-1 overflow-y-auto p-5`). Drawer móvil `<lg`: overlay `bg-black/60` +
  panel `w-64` con `shadow-xl shadow-black/40`, transición `duration-200 ease-out`.
- **Dashboard**: `grid grid-cols-1 gap-3 xl:grid-cols-[1fr_280px] 2xl:grid-cols-[1fr_320px]`
  (columna principal + sidebar derecha de 280/320px).
- **Max-width de página**: `max-w-sm` (Login), `max-w-md` (Onboarding), `max-w-2xl` (Settings),
  `max-w-3xl` (Matchups). El resto fluye.
- **Grids habituales**: stat cards `grid-cols-2 sm:grid-cols-4/5`, filas pares `grid-cols-2
  md:grid-cols-2/3`, heatmap `grid-cols-[56px_repeat(7,1fr)]`.

### Rounded

| Clase | Uso |
| --- | --- |
| `rounded-lg` | **La más común** (~80 usos): botones, inputs, cards login/onboarding, avatares |
| `rounded-xl` | Cards de dashboard, heatmap grid, BigStatCards, Constitution header |
| `rounded-md` | Filas de jugador, tabs pills, badges VICTORY/DEFEAT |
| `rounded-full` | Toggles, dots, pills, barras de progreso, spinner |
| `rounded-sm` | Spell icons, item boxes del accordion |

### Padding

| Clase | Uso |
| --- | --- |
| `p-3` | Filas, items internos, stat boxes, nav |
| `p-4` | **Cards de dashboard** (estándar) |
| `p-5` | Cards de Settings/Matchups/Weekly, main content |
| `p-6` | Cards de Login/Onboarding, veredicto de Constitución |
| `px-3 py-2` | Pills de filtro, filas de lista, filas de campeones |

### Gaps

`gap-1` (tabs), `gap-1.5` (items de lista), `gap-2` (avatar+texto), `gap-2.5` (nav), `gap-3` (grids
internos), `gap-4` (grids principales), `gap-x-3` (filas de partida).

### Aviso de tamaños

Avatares de campeón: `h-16 w-16` (grande) → `h-9 w-9` (accordion) → `h-6 w-6` (dropdown). Iconos:
`h-5 w-5` (secciones), `h-4 w-4` (inline), `h-3.5 w-3.5` (botones), `h-3 w-3` (muy pequeños). Summoner
spells: `h-[14px] w-[14px]` (tabla) / `h-[15px] w-[15px]` (accordion).

## Componentes canónicos

### Botón primario

```
rounded-lg bg-accent-purple px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-accent-purple/20
transition-all hover:bg-accent-purple-dim active:scale-95 disabled:cursor-not-allowed disabled:bg-gray-800
disabled:text-gray-500
```

Variante compacta de tabla (raw purple): `bg-purple-500 text-white shadow-lg shadow-purple-500/20
hover:bg-purple-400 rounded-lg px-3.5 py-2 text-[11px] font-bold uppercase tracking-wider`.

### Botón secundario / ghost

```
rounded-lg border border-accent-purple/30 bg-accent-purple/10 px-4 py-2.5 text-sm font-bold
text-accent-purple transition-all hover:bg-accent-purple/20 active:scale-95
```

Variante ghost (`Reintentar`, `Prometo Mejorar`): `border border-purple-500/30 bg-purple-500/10
text-purple-400 hover:bg-purple-500/20`.

### Tab pill selector

```
rounded-lg bg-[#0A0A10] p-0.5     (contenedor)
rounded-md px-3 py-2 text-[11px] font-semibold transition-colors     (pill)
  activo:  bg-purple-500 text-white shadow-lg shadow-purple-500/20
  inactivo: text-gray-500 hover:text-gray-300
```

### Tarjeta estándar de dashboard

```
rounded-xl border border-gray-800 bg-[#14141C] p-4
```

La tarjeta más repetida del proyecto (KPIs, heatmap, Weekly, Trends, Performance Notes…). Copy-paste.

### Tarjeta interna / stat box

```
rounded-lg border border-gray-800 bg-[#1A1A24] p-3
```

### Fila de item en lista

```
flex items-center justify-between rounded-lg border border-gray-800/50 bg-[#0D0D12] px-3 py-2
transition-colors hover:bg-[#1A1A24]
```

### Input / select estándar

```
w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary
placeholder-text-muted outline-none transition-colors focus:border-accent-purple/50
```

Variantes: numérica (añade `font-mono px-3 py-2.5`) e input de review (`border-gray-700 bg-[#0D0D12]
placeholder-gray-600 focus:border-purple-500/50`). Existen tres variantes no unificadas.

### Badge victory/defeat

```
inline-block rounded px-2 py-0.5 text-[11px] font-black uppercase tracking-wider
  victory: bg-emerald-500/20 text-emerald-400
  defeat:  bg-red-500/20 text-red-400
```

### Chip / tag de pool

```
flex items-center gap-2 rounded-lg border border-accent-purple/30 bg-accent-purple/10 px-2.5 py-1.5
```

### Toggle (VOD Review)

Manual, sin librería: `h-6 w-11 rounded-full transition-colors`, on `bg-purple-500` / off `bg-gray-700`,
thumb `absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform`, `left-[22px]` on / `left-0.5` off.

### Grids de datos

- **Fila de partida** (`MatchesTable`): `grid grid-cols-[auto_minmax(130px,1fr)_84px_88px_68px_56px_64px_72px_52px]
  items-center gap-x-3` (avatar, info, badge, KDA, CS, KP, DPM, rating, LP). Fondo condicional:
  gradiente emerald (win) / red (loss).
- **Fila de jugador** (`MatchAccordion`): `grid grid-cols-[auto_minmax(120px,180px)_auto_minmax(140px,auto)_minmax(150px,1fr)_48px]
  items-center gap-x-3 min-w-[720px]`. El jugador propio se resalta con `bg-emerald-500/[0.08]
  ring-1 ring-purple-500/40`.
- **Barra de daño**: track `bg-gray-800`, fill `bg-blue-500` (azul) / `bg-red-500` (rojo), width inline `%`.

## Estados, feedback y animaciones

- **Hover**: `hover:bg-card-hover` (nav/dropdowns), `hover:bg-white/[0.02]` (filas match),
  `hover:bg-[#1A1A24]` (filas de lista), `hover:text-purple-400`, `hover:text-red-400` (acciones
  destructivas), `hover:scale-110` (celdas heatmap con datos), `hover:scale-[1.02]` (cards KPI).
- **Pulsado**: `active:scale-95` en botones primarios; `active:scale-[0.98]` en "Guardar Review".
- **Focus**: inputs `outline-none` + `focus:border-accent-purple/50`; filas de partida
  `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-inset`.
- **Transiciones**: `transition-colors` (por defecto) y `transition-all` cuando hay escala.
- **Disabled**: `disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500`.
- **Animaciones custom**: `animate-page-enter` (navegación) y `.shimmer` (skeletons), definidas en
  `index.css`. Loading nativo: `animate-spin`, `PageLoader` usa `animate-pulse`.
- **Skeletons**: `rounded-* bg-gray-800/30` (o `/60`) + clase `shimmer`.

## Lógica de color condicional (repeticiones)

Patrones de clase que se repiten literal en varias partes — no están extraídos a helper:

- **Rating**: `rating >= 80 ? 'text-orange-400' : rating >= 60 ? 'text-emerald-400' : rating >= 40 ?
  'text-gray-300' : 'text-red-400'` (MatchesTable, MatchAccordion).
- **KDA**: `kda >= 5 ? 'text-emerald-400' : kda >= 3 ? 'text-gray-300' : kda >= 2 ? 'text-yellow-400' :
  'text-red-400'`.
- **Tilt / impact buttons**: `border-current bg-current/10` con el color del nivel.
- **Shadows de Recharts / estilos inline** (gráficos): métricas con `#F59E0B` (oro), `#A855F7`
  (púrpura), `#06B6D4` (cyan); gradiente LP `#10B981` / `#EF4444`; ticks `#6B7280`, ejes `#2A2A35`,
  tooltip/ReferenceLine `#4B5563`.

## Convenciones y deuda conocida

- Títulos de sección de cards: `text-[10px] font-bold uppercase tracking-widest text-text-muted`
  (o `text-purple-400`), a veces con icono `h-5 w-5`.
- Hay **dos capas paralelas** de color: tokens semánticos (`bg-card`, `border-border`, `bg-accent-purple`)
  en Login/Onboarding/Settings/Matchups, y colores raw/arbitrary (`bg-[#14141C]`, `border-gray-800`,
  `bg-purple-500`) en el resto. No están alineadas (p. ej. `bg-card` es `#1A1A21`, la card dashboard
  `#14141C`). **No remover los raw a favor de tokens sin revisar primero** — cambiar el color base de
  todas las tarjetas afecta a todo el dashboard.
- Los botones primarios existen en dos variantes (`bg-accent-purple` y `bg-purple-500`); ambas son
  válidas y se mantienen así.
- No existe `group-hover:*`, ni `divide-*`, ni `backdrop-blur`, ni variantes `dark:`. El overlay del
  drawer es opaco (`bg-black/60`).
- Los tokens `status-*` del `@theme` están sin usar; el semáforo real es emerald/red de Tailwind.