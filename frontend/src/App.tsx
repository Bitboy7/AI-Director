import { Link, Route, Routes } from 'react-router-dom'
import { Settings } from 'lucide-react'
import Dashboard from '@/pages/Dashboard'
import ProjectView from '@/pages/ProjectView'
import SettingsPage from '@/pages/Settings'

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <h1 className="text-xl font-semibold tracking-tight">AI Director</h1>
        <Link
          to="/settings"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <Settings className="size-4" />
          Configuración
        </Link>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/projects/:projectId" element={<ProjectView />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </div>
  )
}

export default App
