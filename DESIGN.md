# DESIGN.md

> Hoja de estilos y reglas visuales del frontend (React SPA + Tailwind CSS **v4**). Inspirada en la estética minimalista-oscura (Linear, Raycast, Vercel). Este documento es la única referencia de diseño del proyecto.

## Tabla de Contenidos

1. [Filosofía Visual](#1-filosofía-visual)
2. [Design Tokens](#2-design-tokens-indexcss)
3. [Tipografía](#3-tipografía-escala-ampliada)
4. [Componentes Canónicos](#4-componentes-canónicos)
5. [Formas y Geometría](#5-formas-y-geometría-border-radius)
6. [Semántica de Color](#6-semántica-de-color-el-neón-de-datos)
7. [Do's & Don'ts](#7-dos--donts)
8. [Cambios Clave](#8-cambios-clave)

---

## 0. Principios Rectores

Analizando los documentos de Linear, Raycast y Vercel, salta a la vista por qué esas tres webs son el estándar de oro actual: **la restricción**.

Todas comparten un patrón idéntico que podemos aplicar al Centro de Mando:

### El Sistema de "Escalera" (Surface Ladder)

No usan sombras pesadas. Separan los elementos apilando fondos sutilmente más claros sobre el lienzo oscuro, delimitados por un borde ultrafino de 1px (hairline).

### Tipografía Bimodal

Usan una fuente Sans (Inter/Geist) con *tracking negativo* (letras más juntas) para los títulos grandes, y una fuente Mono en mayúsculas y muy separada para las etiquetas o cejas de sección.

### El Acento Escaso

Linear usa su lavanda y Raycast su rojo/blanco con cuentagotas. Todo es blanco, negro y gris, lo que hace que cuando aparece el color neón (en nuestro caso, el púrpura), el impacto visual sea brutal.

> **Problema actual del diseño:** la tipografía es microscópica (`text-[10px]`, `text-xs`) y hay colores superpuestos (`bg-card` vs `bg-[#14141C]`). Con esta propuesta se limpia todo, se amplían los tamaños de fuente para que respire y se aplican las reglas de Linear, Raycast y Vercel.

## 1. Filosofía Visual

- **Oscuro por defecto, Neón por acento:** El lienzo es un negro profundo. El púrpura brillante (`#A855F7`) y los colores semánticos (Emerald, Red) se usan exclusivamente para destacar datos clave, botones primarios y estados activos.
- **Profundidad por Hairlines:** Evitamos las sombras pesadas (`drop-shadow`). La profundidad se logra apilando tarjetas sobre el fondo oscuro usando bordes de 1px (Hairlines) y sutiles brillos (glows) para elementos interactivos.
- **Tipografía como Estructura:** Títulos grandes y compactos (tracking negativo). Etiquetas de sección pequeñas, monoespaciadas y espaciadas (uppercase). Datos numéricos gigantes.

## 2. Design Tokens (index.css)

| Token | Valor | Clase Tailwind | Rol |
| --- | --- | --- | --- |
| `--color-canvas` | `#0A0A0F` | `bg-canvas` | Fondo base de la app. El lienzo principal. |
| `--color-surface-1` | `#14141C` | `bg-surface-1` | Tarjetas principales (Dashboard, Heatmap). |
| `--color-surface-2` | `#1A1A24` | `bg-surface-2` | Sub-paneles internos, tooltips, hover de filas. |
| `--color-hairline` | `#2A2A35` | `border-hairline` | Borde de 1px universal para todas las tarjetas. |
| `--color-accent-primary` | `#A855F7` | `bg-accent-primary` / `text-accent-primary` | El Neón. Botones principales, tabs activos. |
| `--color-text-ink` | `#F3F4F6` | `text-text-ink` | Títulos y texto de alta prioridad (casi blanco). |
| `--color-text-body` | `#9CA3AF` | `text-text-body` | Texto secundario y párrafos. |
| `--color-text-mute` | `#6B7280` | `text-text-mute` | Placeholders, leyendas, metadatos. |

## 3. Tipografía (Escala Ampliada)

- **Sans (Inter):** Para toda la interfaz, botones y títulos.
- **Mono (JetBrains Mono):** **EXCLUSIVO** para números (rating, LP, KDA) y cejas de sección.

### Jerarquía

| Token / Clase | Estilo Tailwind | Uso |
| --- | --- | --- |
| `display-xl` | `text-4xl md:text-5xl font-black tracking-tighter text-text-ink` | Títulos de página, estadísticas masivas (Winrate global). |
| `heading-lg` | `text-2xl font-bold tracking-tight text-text-ink` | Títulos de sección importantes (Matchups, Weekly). |
| `heading-md` | `text-lg font-semibold tracking-tight text-text-ink` | Títulos de tarjetas principales. |
| `mono-eyebrow` | `text-xs font-mono font-bold uppercase tracking-widest text-accent-primary` | "Cejas" de sección (ej. "PERFORMANCE NOTES"). Reemplaza al antiguo `text-[10px]`. |
| `body-base` | `text-sm md:text-base text-text-body` | Nuevo tamaño estándar para lectura y filas (antes era xs/sm). |
| `data-huge` | `text-2xl font-mono font-bold text-text-ink` | Rating, KDA o LP destacado dentro de tarjetas. |
| `data-sm` | `text-sm font-mono text-text-mute` | Metadatos numéricos secundarios. |

## 4. Componentes Canónicos

### Tarjeta Principal (Surface 1)

Inspirada en el estilo "App UI" de Linear/Raycast.

```html
<div className="rounded-xl border border-hairline bg-surface-1 p-6">
  <!-- Las tarjetas respiran: p-6 (24px) en lugar de p-4 -->
</div>
```

### Tarjeta Anidada / Panel de Datos (Surface 2)

```html
<div className="rounded-lg border border-hairline/50 bg-surface-2 p-4">
  <!-- Para aislar stats dentro de una tarjeta más grande -->
</div>
```

### Ceja de Sección (Vercel Style)

```html
<h3 className="mb-4 text-xs font-mono font-bold uppercase tracking-widest text-accent-primary/80">
  KDA Acumulado
</h3>
```

### Botones

**Primario (El Neón):** Completamente redondeado para marketing, suave para UI.

```html
<!-- Estilo Pill (Marketing/Acciones mayores) -->
<button className="rounded-full bg-accent-primary px-6 py-2.5 text-sm font-bold text-white shadow-[0_0_16px_rgba(168,85,247,0.4)] transition-all hover:bg-accent-primary/90 active:scale-95">
  Conectar Riot ID
</button>

<!-- Estilo UI (Filtros, Guardar) -->
<button className="rounded-lg bg-accent-primary px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-accent-primary/90">
  Sincronizar
</button>
```

**Secundario / Ghost:**

```html
<button className="rounded-lg border border-hairline bg-transparent px-4 py-2 text-sm font-semibold text-text-ink transition-colors hover:bg-surface-2">
  Cancelar
</button>
```

## 5. Formas y Geometría (Border Radius)

- `rounded-xl` (12px-16px): Tarjetas y contenedores principales (Layout exterior).
- `rounded-lg` (8px): Botones, inputs, tarjetas anidadas.
- `rounded-full`: Botones CTA masivos, insignias de estado, avatares.
- `rounded-sm` (4px): Iconos de habilidades (Spells), teclas o atajos (Keycaps).

## 6. Semántica de Color (El Neón de Datos)

El fondo oscuro hace que estos colores brillen intensamente. Solo aplicables a números, insignias (badges) o gráficos, **nunca a fondos grandes**.

- **Victoria / Bueno:** `text-emerald-400` + badge `bg-emerald-500/15`
- **Derrota / Malo:** `text-red-400` + badge `bg-red-500/15`
- **Alerta / Warning:** `text-amber-400` + badge `bg-amber-500/15`
- **Info / Neutro (Azul Riot):** `text-cyan-400` o `text-blue-400`

## 7. Do's & Don'ts

- **DO:** Usar la fuente MONO (`font-mono`) en mayúsculas para las cabeceras de sección. Esto le da un aspecto de "panel de control" o telemetría muy profesional.
- **DO:** Usar `tracking-tight` (letras juntas) en textos grandes y `tracking-widest` (letras separadas) en textos microscópicos.
- **DON'T:** Usar tamaños menores a `text-xs` (12px). Se elimina por completo el uso de `text-[8px]` y `text-[10px]`.
- **DON'T:** Usar `drop-shadow` para separar tarjetas. Usa el `border-hairline` y la diferencia sutil entre `bg-canvas` y `bg-surface-1`.

## 8. Cambios Clave

1. **La "Ceja" (Eyebrow):** Tomado directamente de Vercel, los títulos de las tarjetas dejarán de ser un gris diminuto. Ahora serán de fuente monoespaciada, en mayúsculas, con letras muy separadas (`tracking-widest`) y con un sutil color púrpura. Es el toque más premium que se le puede dar a un panel de control.
2. **Textos Legibles:** Se ha erradicado el `text-[10px]`. El texto base pasará a ser `text-sm` (14px) o `text-base` (16px), haciendo la app mucho más cómoda de leer sin perder el aspecto denso de datos.
3. **El Botón "Pill":** Tomado de Vercel y Raycast, el botón primario de acciones importantes (como Iniciar Sesión o Conectar Riot ID) tendrá `rounded-full` y un brillo neón (`shadow-[0_0_16px_rgba(...)]`), mientras que los botones internos de la tabla se mantendrán cuadrados (`rounded-lg`) para no saturar la vista.