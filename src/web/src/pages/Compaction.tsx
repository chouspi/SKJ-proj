import { useEffect, useRef, useState } from 'react'

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

type CompactionStatus = {
  volume_id: number
  status: string
  log: string
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

function Compaction() {
  const [volumes, setVolumes] = useState<VolumeInfo[]>([])
  const [selectedVolumeId, setSelectedVolumeId] = useState<number | null>(null)
  const [compactionStatus, setCompactionStatus] = useState<CompactionStatus | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState('')
  const pollingRef = useRef<number | null>(null)
  const logRef = useRef<HTMLPreElement | null>(null)

  useEffect(() => {
    let cancelled = false
    async function fetchVolumes() {
      try {
        const response = await fetch('/system/volumes')
        if (!response.ok) throw new Error(`Failed: ${response.status}`)
        const payload = await response.json() as { volumes: VolumeInfo[] }
        if (!cancelled) {
          setVolumes(payload.volumes)
          if (payload.volumes.length > 0) {
            setSelectedVolumeId((prev) =>
              prev !== null && payload.volumes.some((v) => v.volume_id === prev)
                ? prev
                : payload.volumes[0].volume_id,
            )
          }
        }
      } catch { /* ignore */ }
    }
    void fetchVolumes()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    return () => {
      if (pollingRef.current !== null) clearInterval(pollingRef.current)
    }
  }, [])

  async function startCompaction() {
    if (selectedVolumeId === null) return
    setIsRunning(true)
    setError('')
    setCompactionStatus(null)

    try {
      const response = await fetch(`/system/compaction/${selectedVolumeId}`, { method: 'POST' })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail ?? `Failed: ${response.status}`)
      }

      pollingRef.current = window.setInterval(async () => {
        try {
          const statusResp = await fetch(`/system/compaction/${selectedVolumeId}`)
          if (!statusResp.ok) return
          const status = await statusResp.json() as CompactionStatus
          setCompactionStatus(status)
          if (status.status === 'completed' || status.status === 'failed') {
            if (pollingRef.current !== null) {
              clearInterval(pollingRef.current)
              pollingRef.current = null
            }
            setIsRunning(false)
            const volResp = await fetch('/system/volumes')
            if (volResp.ok) {
              const payload = await volResp.json() as { volumes: VolumeInfo[] }
              setVolumes(payload.volumes)
            }
          }
        } catch { /* ignore */ }
      }, 1000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start compaction')
      setIsRunning(false)
    }
  }

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [compactionStatus?.log])

  const selectedVolume = volumes.find((v) => v.volume_id === selectedVolumeId)
  const estimatedSavings = selectedVolume
    ? Math.round(selectedVolume.file_size_bytes * (selectedVolume.fragmentation_pct / 100))
    : 0

  return (
    <section className="dashboard">
      <div className="hero-panel dashboard-hero">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Compaction</h1>
          <p className="hero-copy">
            Kompakce volume souboru odstrani data smazanych objektu a uvolni misto na disku.
          </p>
        </div>
      </div>

      {error ? <div className="feedback error">{error}</div> : null}

      <div className="panel">
        <div className="toolbar">
          <div className="panel-heading">
            <h2>Vyber volume</h2>
            <p>Zvol volume soubor ke kompakci.</p>
          </div>
          <select
            className="bucket-select"
            value={selectedVolumeId ?? ''}
            onChange={(event) => {
              setSelectedVolumeId(event.target.value ? Number(event.target.value) : null)
              setCompactionStatus(null)
              setError('')
            }}
            disabled={isRunning}
          >
            {volumes.length === 0 ? (
              <option value="">Zadne volumes</option>
            ) : (
              volumes.map((v) => (
                <option key={v.volume_id} value={v.volume_id}>
                  {v.name}
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      {selectedVolume ? (
        <>
          <div className="panel">
            <div className="panel-heading">
              <h2>Informace o volume</h2>
              <p>Detail zvoleneho volume souboru.</p>
            </div>
            <div className="dashboard-metric-grid">
              <div className="dashboard-metric">
                <span>Aktualni velikost</span>
                <strong>{formatBytes(selectedVolume.file_size_bytes)}</strong>
              </div>
              <div className="dashboard-metric">
                <span>Aktivnich objektu</span>
                <strong>{selectedVolume.active_objects}</strong>
              </div>
              <div className="dashboard-metric">
                <span>Smazanych objektu</span>
                <strong>{selectedVolume.deleted_objects}</strong>
              </div>
              <div className="dashboard-metric">
                <span>Fragmentace</span>
                <strong>{selectedVolume.fragmentation_pct}%</strong>
              </div>
              <div className="dashboard-metric">
                <span>Odhad ussetreneho mista</span>
                <strong>{formatBytes(estimatedSavings)}</strong>
              </div>
            </div>
          </div>

          <div className="panel" style={{ textAlign: 'center' }}>
            <button
              type="button"
              className="primary-button"
              onClick={() => void startCompaction()}
              disabled={isRunning || selectedVolume.active_objects === 0}
              style={{ fontSize: '1.1rem', padding: '1rem 2.5rem' }}
            >
              {isRunning ? 'Probiha kompakce...' : 'Spustit kompakci'}
            </button>
          </div>
        </>
      ) : volumes.length === 0 ? (
        <div className="empty-state">
          <h3>Zadne volumes</h3>
          <p>Zatym nebyly vytvoreny zadne volume soubory.</p>
        </div>
      ) : null}

      {compactionStatus && compactionStatus.log ? (
        <div className="panel">
          <div className="panel-heading">
            <h2>Log</h2>
            <p>
              {compactionStatus.status === 'running'
                ? 'Probiha kompakce...'
                : compactionStatus.status === 'completed'
                  ? 'Kompakce dokoncena.'
                  : compactionStatus.status === 'failed'
                    ? 'Kompakce selhala.'
                    : ''}
            </p>
          </div>
          <pre ref={logRef} className="compaction-log">{compactionStatus.log}</pre>
        </div>
      ) : null}
    </section>
  )
}

export default Compaction
