import { useEffect, useState } from 'react'
import './Dashboard.css'

type ServiceHealth = Record<string, string>

interface SystemStats {
  total_objects: number
  uploading: number
  ready: number
  deleted: number
  volume_count: number
  total_size_bytes: number
}

interface DashboardData {
  services: ServiceHealth
  stats: SystemStats
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = size
  let unitIndex = -1
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 1 : 2)} ${units[unitIndex]}`
}

const serviceLabels: Record<string, string> = {
  s3_gateway: 'S3 Gateway',
  message_broker: 'Message Broker',
  haystack_node: 'Haystack Node',
  image_processing: 'Image Processing Node',
}

const serviceDescriptions: Record<string, string> = {
  s3_gateway: 'REST API pro spravu bucketu, nahravani a stahovani objektu',
  message_broker: 'WebSocket Pub/Sub broker pro async komunikaci mezi uzly',
  haystack_node: 'Append-only storage pro perzistentni ukladani binarnich dat',
  image_processing: 'Worker pro zpracovani obrazku (negativ, zrcadleni, orez, jas, sedotony)',
}

function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function fetchStats() {
      setLoading(true)
      setError('')
      try {
        const response = await fetch('/system/stats')
        if (!response.ok) throw new Error(`Failed to fetch stats: ${response.status}`)
        const payload = (await response.json()) as DashboardData
        if (!cancelled) setData(payload)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load dashboard data')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void fetchStats()
    const interval = setInterval(fetchStats, 10000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  if (loading && !data) {
    return (
      <section className="dashboard">
        <div className="loading-state">Nacitam data dashboardu...</div>
      </section>
    )
  }

  if (error && !data) {
    return (
      <section className="dashboard">
        <div className="feedback error">{error}</div>
      </section>
    )
  }

  const { services, stats } = data!

  return (
    <section className="dashboard">
      <div className="hero-panel dashboard-hero">
        <div>
          <p className="eyebrow">Prehled systemu</p>
          <h1>Dashboard</h1>

        </div>
      </div>

      {error ? <div className="feedback error">{error}</div> : null}

      <div className="panel">
        <div className="panel-heading">
          <h2>Stav sluzeb</h2>
          <p>Aktualni stav jednotlivych uzlu systemu.</p>
        </div>
        <div className="service-grid">
          {Object.entries(serviceLabels).map(([key, label]) => {
            const status = services[key] ?? 'unreachable'
            return (
              <div key={key} className={`service-card status-${status}`}>
                <div className="service-card-header">
                  <span className={`status-dot ${status}`} />
                  <strong>{label}</strong>
                  <span className={`status-pill ${status === 'healthy' ? 'active' : status === 'unreachable' ? 'deleted' : 'neutral'}`}>
                    {status === 'healthy' ? 'online' : status === 'unreachable' ? 'offline' : 'nezdravy'}
                  </span>
                </div>
                <p className="service-card-desc">{serviceDescriptions[key]}</p>
              </div>
            )
          })}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <h2>Statistiky</h2>
          <p>Globalni prehled vsech objektu a vyuziti storage.</p>
        </div>
        <div className="dashboard-metric-grid">
          <div className="dashboard-metric">
            <span>Celkem objektu</span>
            <strong>{stats.total_objects}</strong>
          </div>
          <div className="dashboard-metric">
            <span>Uploading</span>
            <strong>{stats.uploading}</strong>
          </div>
          <div className="dashboard-metric">
            <span>Ready</span>
            <strong>{stats.ready}</strong>
          </div>
          <div className="dashboard-metric">
            <span>Smazanych</span>
            <strong>{stats.deleted}</strong>
          </div>
          <div className="dashboard-metric">
            <span>Volume souboru</span>
            <strong>{stats.volume_count}</strong>
          </div>
          <div className="dashboard-metric">
            <span>Celkova velikost</span>
            <strong>{formatBytes(stats.total_size_bytes)}</strong>
          </div>
        </div>
      </div>


    </section>
  )
}

export default Dashboard
