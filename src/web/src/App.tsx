import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Images from './pages/Images'
import Volumes from './pages/Volumes'
import Compaction from './pages/Compaction'
import ImageProcessing from './pages/ImageProcessing'
import Legacy from './pages/Legacy'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <main className="app-shell">
        <nav className="topbar">
          <div className="topbar-brand">
            <span className="eyebrow">SKJ Storage</span>
            <div className="topbar-nav">
              <NavLink to="/" end className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Dashboard
              </NavLink>
              <NavLink to="/upload" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Upload
              </NavLink>
              <NavLink to="/images" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Obrazky
              </NavLink>
              <NavLink to="/volumes" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Volumes
              </NavLink>
              <NavLink to="/compaction" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Compaction
              </NavLink>
              <NavLink to="/image-processing" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Image Processing
              </NavLink>
              <NavLink to="/legacy" className={({ isActive }) => `topbar-tab${isActive ? ' is-active' : ''}`}>
                Legacy
              </NavLink>
            </div>
          </div>
        </nav>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/images" element={<Images />} />
          <Route path="/volumes" element={<Volumes />} />
          <Route path="/compaction" element={<Compaction />} />
          <Route path="/image-processing" element={<ImageProcessing />} />
          <Route path="/legacy" element={<Legacy />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

export default App
