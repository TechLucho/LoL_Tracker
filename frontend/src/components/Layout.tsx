import { Suspense, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ErrorBoundary } from 'react-error-boundary'
import {
  Crosshair,
  LayoutDashboard,
  Menu,
  Shield,
  Clock,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import HealthBanner from './HealthBanner'
import PageError from './PageError'
import PageLoader from './PageLoader'
import { useSyncMatches } from '../hooks/useMatches'

const navItems = [
  { to: '/', label: 'Centro de Mando', icon: LayoutDashboard },
  { to: '/constitution', label: 'La Constitución', icon: Shield },
  { to: '/heatmap', label: 'Horarios / Heatmap', icon: Clock },
  { to: '/pool', label: 'Champion Pool', icon: Crosshair },
]

const bottomItems = [
  { to: '/settings', label: 'Configuración', icon: SlidersHorizontal },
]

// Contenido compartido entre el sidebar de escritorio y el drawer móvil. `onNavigate`
// cierra el drawer al tocar un enlace; en escritorio no se pasa y no cambia nada.
function SidebarContent({ onNavigate, onClose }: { onNavigate?: () => void; onClose?: () => void }) {
  const renderLink = (item: (typeof navItems)[number]) => {
    const Icon = item.icon
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.to === '/'}
        onClick={onNavigate}
        className={({ isActive }) =>
          `flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
            isActive
              ? 'bg-accent-purple/15 text-accent-purple'
              : 'text-text-secondary hover:bg-card-hover hover:text-text-primary'
          }`
        }
      >
        <Icon className="h-4 w-4" />
        <span>{item.label}</span>
      </NavLink>
    )
  }

  return (
    <>
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <span className="text-lg">⚔️</span>
        <h1 className="text-sm font-bold tracking-tight">LoL Tracker</h1>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar menú"
            className="ml-auto rounded-lg p-1 text-text-secondary transition-colors hover:bg-card-hover hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-3">{navItems.map(renderLink)}</nav>

      <div className="mt-auto border-t border-border p-3">
        {bottomItems.map(renderLink)}
        <p className="mt-2 px-3 text-[10px] text-text-muted">v2.0 — FastAPI + React</p>
      </div>
    </>
  )
}

export default function Layout() {
  const location = useLocation()
  // Drawer móvil (<lg): cerrado por defecto; se abre con la hamburguesa y se cierra al
  // navegar, tocando el backdrop o pulsando Escape.
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = () => setDrawerOpen(false)

  useEffect(() => {
    if (!drawerOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [drawerOpen])

  // Auto-sync silencioso: una sola vez por sesión de app, al montar el layout (que envuelve
  // todas las rutas, así que dispare entre o por deep-link). Si no hay partidas nuevas, ni
  // se entera; si trae datos frescos, las queries invalidadas refrescan la UI solas. El ref
  // evita el doble disparo del StrictMode en dev y re-ejecuciones al navegar.
  const autoSynced = useRef(false)
  const { mutate: startAutoSync } = useSyncMatches({ silent: true })
  useEffect(() => {
    if (autoSynced.current) return
    autoSynced.current = true
    startAutoSync()
  }, [startAutoSync])

  return (
    <div className="flex h-screen flex-col bg-background text-text-primary">
      <HealthBanner />

      {/* Header móvil (<lg): hamburguesa + título. En escritorio lo sustituye el sidebar. */}
      <header className="flex items-center gap-3 border-b border-border bg-card px-4 py-3 lg:hidden">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Abrir menú de navegación"
          aria-expanded={drawerOpen}
          className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-card-hover hover:text-text-primary"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-lg">⚔️</span>
        <h1 className="text-sm font-bold tracking-tight">LoL Tracker</h1>
      </header>

      {/* Columna única: banner arriba (cuando existe), sidebar + contenido debajo.
          min-h-0 permite que main haga overflow-y dentro del flex column. */}
      <div className="flex min-h-0 flex-1">
        {/* Sidebar de escritorio (≥lg) */}
        <aside className="hidden h-full w-56 shrink-0 flex-col border-r border-border bg-card lg:flex">
          <SidebarContent />
        </aside>

        {/* Drawer móvil (<lg): overlay + panel deslizante. Siempre montado para animar
            entrada/salida; `inert` evita tabular dentro del menú oculto (React 19). */}
        <div
          onClick={closeDrawer}
          aria-hidden={!drawerOpen}
          className={`fixed inset-0 z-40 bg-black/60 transition-opacity duration-200 lg:hidden ${
            drawerOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
          }`}
        />
        <aside
          inert={!drawerOpen}
          aria-label="Navegación"
          className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-card shadow-xl shadow-black/40 transition-transform duration-200 ease-out lg:hidden ${
            drawerOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <SidebarContent onNavigate={closeDrawer} onClose={closeDrawer} />
        </aside>

        <main className="flex-1 overflow-y-auto p-5">
          {/* key por ruta: remonta el contenido en cada navegación para repetir el fade-in.
              El Suspense mantiene el sidebar visible mientras se descarga el chunk de la página.
              El ErrorBoundary va por FUERA del Suspense: si un chunk falla al descargarse (deploy
              nuevo con pestaña vieja) o una página revienta en render, se muestra PageError en vez
              de la pantalla blanca. resetKeys lo resetea al navegar a otra página. */}
          <div key={location.pathname} className="animate-page-enter">
            <ErrorBoundary FallbackComponent={PageError} resetKeys={[location.pathname]}>
              <Suspense fallback={<PageLoader />}>
                <Outlet />
              </Suspense>
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}
