import { lazy } from 'react'
import { HashRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import Layout from './components/Layout'
import { AuthProvider } from './contexts/AuthContext'
import { useAuth } from './hooks/useAuth'
import Login from './pages/Login'

// Code-splitting: cada página viaja en su propio chunk y sólo se descarga al navegar.
// Nota: DiarioPage fue descartado por decisión de diseño (2026-08-23), junto con el
// concepto de "Sesión" con límites rígidos diarios — app más ligera, menos restrictiva.
// ScoutPage retirado del nav (2026-08-24): el backend (/api/scout/*) sigue vivo y probado,
// pero sin UI real era un ítem de navegación vacío. Vuelve cuando tenga tarjetas de verdad.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ChampionPoolPage = lazy(() => import('./pages/ChampionPoolPage'))
const ConstitutionPage = lazy(() => import('./pages/Constitution'))
const HeatmapPage = lazy(() => import('./pages/Heatmap'))
const SettingsPage = lazy(() => import('./pages/Settings'))
const MatchupsPage = lazy(() => import('./pages/Matchups'))
const TrendsPage = lazy(() => import('./pages/Trends'))
const WeeklyPage = lazy(() => import('./pages/Weekly'))

// Guard de rutas privadas. Mientras se resuelve la sesión muestra un esqueleto (evita el
// destello login→app); sin sesión, redirige a /login recordando a dónde iba el usuario.
function RequireAuth() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="shimmer h-6 w-48 rounded bg-card" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

function App() {
  return (
    <AuthProvider>
      <HashRouter>
        <Toaster theme="dark" position="top-right" richColors closeButton />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="pool" element={<ChampionPoolPage />} />
              <Route path="constitution" element={<ConstitutionPage />} />
              <Route path="heatmap" element={<HeatmapPage />} />
              <Route path="matchups" element={<MatchupsPage />} />
              <Route path="trends" element={<TrendsPage />} />
              <Route path="weekly" element={<WeeklyPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Route>
        </Routes>
      </HashRouter>
    </AuthProvider>
  )
}

export default App