import { useEffect, useState } from 'react'

type VolumeInfo = {
  volume_id: number
  name: string
  file_size_bytes: number
  max_size_bytes: number
  usage_pct: number
  total_objects: number
  active_objects: number
  deleted_objects: number
  fragmentation_pct: number
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

function Volumes() {
  const [volumes, setVolumes] = useState<VolumeInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function fetchVolumes() {
      setLoading(true)
      setError('')
      try {
        const response = await fetch('/system/volumes')
        if (!response.ok) throw new Error(`Failed to fetch volumes: ${response.status}`)
        const payload = await response.json() as { volumes: VolumeInfo[] }
        if (!cancelled) setVolumes(payload.volumes)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load volumes')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void fetchVolumes()
    return () => { cancelled = true }
  }, [])

  return (
    <section className="dashboard">
      <div className="hero-panel dashboard-hero">
        <div>
          <p className="eyebrow">Sprava svazku</p>
          <h1>Volumes</h1>
          <p className="hero-copy">
            Prehled append-only volume souboru, jejich zaplneni a fragmentace.
          </p>
        </div>
      </div>

      {error ? <div className="feedback error">{error}</div> : null}

      {loading ? (
        <div className="loading-state">Nacitam volumes...</div>
      ) : volumes.length === 0 ? (
        <div className="empty-state">
          <h3>Zadne volumes</h3>
          <p>Zatym nebyly vytvoreny zadne volume soubory.</p>
        </div>
      ) : (
        <div className="panel table-panel">
          <div className="table-panel-header">
            <div>
              <h2>Seznam volume souboru</h2>
              <p>Kazdy volume je append-only binarni soubor na disku. Maximalni velikost: {formatBytes(volumes[0]?.max_size_bytes ?? 0)}.</p>
            </div>
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Volume</th>
                  <th>Size</th>
                  <th>Max size</th>
                  <th>Usage</th>
                  <th>Active objects</th>
                  <th>Deleted objects</th>
                  <th>Fragmentace</th>
                </tr>
              </thead>
              <tbody>
                {volumes.map((v) => (
                  <tr key={v.volume_id}>
                    <td><code>{v.name}</code></td>
                    <td>{formatBytes(v.file_size_bytes)}</td>
                    <td>{formatBytes(v.max_size_bytes)}</td>
                    <td>
                      <div className="usage-bar-wrapper">
                        <div className="usage-bar">
                          <div
                            className={`usage-bar-fill${v.usage_pct >= 90 ? ' usage-bar-danger' : v.usage_pct >= 75 ? ' usage-bar-warn' : ''}`}
                            style={{ width: `${Math.min(v.usage_pct, 100)}%` }}
                          />
                        </div>
                        <span>{v.usage_pct}%</span>
                      </div>
                    </td>
                    <td>{v.active_objects}</td>
                    <td>{v.deleted_objects}</td>
                    <td>{v.fragmentation_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}

export default Volumes
