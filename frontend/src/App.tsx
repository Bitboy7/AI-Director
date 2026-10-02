import { Route, Routes } from 'react-router-dom'
import Dashboard from '@/pages/Dashboard'
import ProjectView from '@/pages/ProjectView'

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b px-6 py-4">
        <h1 className="text-xl font-semibold tracking-tight">AI Director</h1>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/projects/:projectId" element={<ProjectView />} />
      </Routes>
    </div>
  )
}

export default App
