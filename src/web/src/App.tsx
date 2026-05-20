import { NavLink, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Legacy from './pages/Legacy'
import Upload from './pages/Upload'
import './App.css'

function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <p className="eyebrow">SKJ Storage</p>
          <nav className="topbar-nav" aria-label="Hlavni navigace">
            <NavLink to="/" end className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
              Dashboard
            </NavLink>
            <NavLink to="/legacy" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
              Legacy
            </NavLink>
            <NavLink to="/upload" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
              Upload
            </NavLink>
          </nav>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/legacy" element={<Legacy />} />
        <Route path="/upload" element={<Upload />} />
      </Routes>
    </main>
  )
}

export default App
