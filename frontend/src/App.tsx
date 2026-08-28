import { lazy } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import Layout from './components/Layout'

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

function App() {
  return (
    <HashRouter>
      <Toaster theme="dark" position="top-right" richColors closeButton />
      <Routes>
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
      </Routes>
    </HashRouter>
  )
}

export default App
