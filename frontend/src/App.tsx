import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { BarChart3, Clapperboard, Settings } from 'lucide-react'
import Dashboard from '@/pages/Dashboard'
import ProjectView from '@/pages/ProjectView'
import SettingsPage from '@/pages/Settings'
import Stats from '@/pages/Stats'

function App() {
  const location = useLocation()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex size-7 items-center justify-center rounded-md bg-pencil text-primary-foreground shadow-[0_0_20px_-2px_color-mix(in_oklch,var(--pencil)_50%,transparent)]">
              <Clapperboard className="size-4" />
            </span>
            <span className="text-sm font-semibold tracking-[0.16em] uppercase">
              AI <span className="text-pencil">Director</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              to="/stats"
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <BarChart3 className="size-4" />
              Estadísticas
            </Link>
            <Link
              to="/settings"
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Settings className="size-4" />
              Configuración
            </Link>
          </nav>
        </div>
      </header>
      <main key={location.pathname} className="animate-tab-in flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects/:projectId" element={<ProjectView />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/stats" element={<Stats />} />
        </Routes>
      </main>
    </div>
  )
}

export default App