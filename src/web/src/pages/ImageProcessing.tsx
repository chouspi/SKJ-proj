import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

type Bucket = {
  id: number
  user_id: string
  name: string
  created_at: string
}

type StoredFile = {
  id: string
  bucket_id: number
  filename: string
  size: number
  status: string
  volume_id: number | null
  offset: number | null
  is_deleted: boolean
  created_at: string
}

const DEFAULT_USER_ID = 'alice'

const operations = [
  { id: 'grayscale', label: 'Grayscale', params: [] as { key: string; label: string; type: string; default: string }[] },
  { id: 'invert', label: 'Invert', params: [] },
  { id: 'mirror', label: 'Zrcadlit', params: [] },
  { id: 'brightness', label: 'Jas', params: [{ key: 'amount', label: 'Hodnota (-255 az 255)', type: 'number', default: '50' }] },
  { id: 'resize', label: 'Zmena velikosti', params: [{ key: 'percent', label: 'Procenta (1-200)', type: 'number', default: '50' }] },
  { id: 'blur', label: 'Rozmazat', params: [{ key: 'radius', label: 'Polomer', type: 'number', default: '2.0' }] },
]

function getProcessedFilename(filename: string, operation: string): string {
  const stem = filename.replace(/\.[^.]+$/, '') || 'image'
  return `${stem}_${operation}.png`
}

async function readErrorMessage(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `Request failed with status ${response.status}.`
  } catch {
    return `Request failed with status ${response.status}.`
  }
}

function ImageProcessing() {
  const [draftUserId, setDraftUserId] = useState(DEFAULT_USER_ID)
  const [activeUserId, setActiveUserId] = useState(DEFAULT_USER_ID)
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [selectedBucketId, setSelectedBucketId] = useState<number | null>(null)
  const [files, setFiles] = useState<StoredFile[]>([])
  const [selectedFile, setSelectedFile] = useState<StoredFile | null>(null)
  const [selectedOperation, setSelectedOperation] = useState(operations[0].id)
  const [opParams, setOpParams] = useState<Record<string, string>>({})
  const [isProcessing, setIsProcessing] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [resultFile, setResultFile] = useState<StoredFile | null>(null)
  const pollingRef = useRef<number | null>(null)
  const initialFileIdsRef = useRef<Set<string>>(new Set())

  const opDef = operations.find((o) => o.id === selectedOperation)

  async function loadBuckets(userId: string) {
    try {
      const response = await fetch(`/buckets/?user_id=${encodeURIComponent(userId)}`)
      if (!response.ok) return
      const payload = (await response.json()) as Bucket[]
      setBuckets(payload)
      if (payload.length > 0) {
        setSelectedBucketId((prev) =>
          prev !== null && payload.some((b) => b.id === prev) ? prev : payload[0].id,
        )
      } else {
        setSelectedBucketId(null)
      }
    } catch {
      setBuckets([])
    }
  }

  async function loadFiles(userId: string, bucketId: number) {
    try {
      const response = await fetch(
        `/buckets/${bucketId}/objects/?user_id=${encodeURIComponent(userId)}&include_deleted=false`,
      )
      if (!response.ok) return
      const payload = (await response.json()) as StoredFile[]
      setFiles(payload)
    } catch {
      setFiles([])
    }
  }

  useEffect(() => {
    void loadBuckets(activeUserId)
  }, [activeUserId])

  useEffect(() => {
    if (selectedBucketId !== null) {
      void loadFiles(activeUserId, selectedBucketId)
    } else {
      setFiles([])
    }
  }, [selectedBucketId, activeUserId])

  useEffect(() => {
    return () => {
      if (pollingRef.current !== null) clearInterval(pollingRef.current)
    }
  }, [])

  async function handleProcess(event: FormEvent) {
    event.preventDefault()
    if (!selectedFile || selectedBucketId === null) return

    setIsProcessing(true)
    setErrorMessage('')
    setSuccessMessage('')
    setResultFile(null)

    const params: Record<string, number> = {}
    if (opDef) {
      for (const p of opDef.params) {
        const val = opParams[p.key] ?? p.default
        params[p.key] = Number(val)
      }
    }

    try {
      const response = await fetch(
        `/buckets/${selectedBucketId}/objects/${selectedFile.id}/process?user_id=${encodeURIComponent(activeUserId)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation: selectedOperation, params }),
        },
      )
      if (!response.ok) throw new Error(await readErrorMessage(response))

      const processedName = getProcessedFilename(selectedFile.filename, selectedOperation)
      initialFileIdsRef.current = new Set(files.map((f) => f.id))

      pollingRef.current = window.setInterval(async () => {
        try {
          const objResp = await fetch(
            `/buckets/${selectedBucketId}/objects/?user_id=${encodeURIComponent(activeUserId)}&include_deleted=false`,
          )
          if (!objResp.ok) return
          const objList = (await objResp.json()) as StoredFile[]
          const newFile = objList.find(
            (f) => f.filename === processedName && !initialFileIdsRef.current.has(f.id),
          )
          if (newFile) {
            if (newFile.status === 'ready') {
              setResultFile(newFile)
              setSuccessMessage(`Hotovo: ${processedName}`)
              if (pollingRef.current !== null) {
                clearInterval(pollingRef.current)
                pollingRef.current = null
              }
              setIsProcessing(false)
              void loadFiles(activeUserId, selectedBucketId)
            } else if (newFile.status === 'failed') {
              setErrorMessage('Zpracovani obrazku selhalo.')
              if (pollingRef.current !== null) {
                clearInterval(pollingRef.current)
                pollingRef.current = null
              }
              setIsProcessing(false)
            }
          }
        } catch {
          /* ignore polling errors */
        }
      }, 2000)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Process selhal.')
      setIsProcessing(false)
    }
  }

  function handleUserSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextUserId = draftUserId.trim()
    if (!nextUserId) {
      setErrorMessage('User ID nesmi byt prazdne.')
      return
    }
    setErrorMessage('')
    setActiveUserId(nextUserId)
  }

  return (
    <>
      <section className="legacy-bar">
        <span className="eyebrow">Image Processing</span>
        <form className="legacy-user-form" onSubmit={handleUserSubmit}>
          <label className="legacy-user-field">
            <span>User:</span>
            <input
              type="text"
              value={draftUserId}
              onChange={(event) => setDraftUserId(event.target.value)}
              placeholder="alice"
            />
          </label>
          <button type="submit" className="secondary-button">
            Pouzit
          </button>
        </form>
      </section>

      <section className="hero-panel">
        <div>
          <p className="eyebrow">Zpracovani obrazku</p>
          <h1>Image Processing</h1>
          <p className="hero-copy">
            Vyber obrazek z bucketu, zvol operaci a nechej ho zpracovat workerem.
          </p>
        </div>
      </section>

      {errorMessage ? <div className="feedback error">{errorMessage}</div> : null}
      {successMessage ? <div className="feedback success">{successMessage}</div> : null}

      <div className="panel">
        <div className="toolbar">
          <div className="panel-heading">
            <h2>Vyber bucket</h2>
            <p>Zvol bucket obsahujici zdrojovy obrazek.</p>
          </div>
          <select
            className="bucket-select"
            value={selectedBucketId ?? ''}
            onChange={(event) => {
              setSelectedBucketId(event.target.value ? Number(event.target.value) : null)
              setSelectedFile(null)
              setResultFile(null)
            }}
          >
            {buckets.length === 0 ? (
              <option value="">Zadne buckety</option>
            ) : (
              buckets.map((bucket) => (
                <option key={bucket.id} value={bucket.id}>
                  {bucket.name}
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      {selectedBucketId !== null && (
        <div className="workspace">
          <aside className="sidebar">
            <div className="panel">
              <div className="panel-heading">
                <h2>Operace</h2>
                <p>Zvol operaci a parametry.</p>
              </div>
              <form className="stack" onSubmit={handleProcess}>
                <label className="field">
                  <span>Operace</span>
                  <select
                    value={selectedOperation}
                    onChange={(e) => {
                      setSelectedOperation(e.target.value)
                      setOpParams({})
                      setResultFile(null)
                    }}
                    disabled={isProcessing}
                  >
                    {operations.map((op) => (
                      <option key={op.id} value={op.id}>{op.label}</option>
                    ))}
                  </select>
                </label>

                {opDef && opDef.params.map((p) => (
                  <label key={p.key} className="field">
                    <span>{p.label}</span>
                    <input
                      type={p.type}
                      value={opParams[p.key] ?? p.default}
                      onChange={(e) => setOpParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                      disabled={isProcessing}
                    />
                  </label>
                ))}

                <button
                  type="submit"
                  className="primary-button"
                  disabled={isProcessing || !selectedFile}
                >
                  {isProcessing ? 'Zpracovavam...' : 'Process image'}
                </button>
              </form>
            </div>
          </aside>

          <section className="content-column">
            <div className="panel">
              <div className="panel-heading">
                <h2>Zdrojovy obrazek</h2>
                <p>Klikni na obrazek pro vyber.</p>
              </div>
              {files.length === 0 ? (
                <div className="empty-state">
                  <h3>Zadne obrazky</h3>
                  <p>Bucket neobsahuje zadne objekty.</p>
                </div>
              ) : (
                <div className="image-grid">
                  {files.map((file) => (
                    <button
                      key={file.id}
                      type="button"
                      className={`image-card selectable-card${selectedFile?.id === file.id ? ' is-selected' : ''}`}
                      onClick={() => {
                        setSelectedFile(file)
                        setResultFile(null)
                      }}
                      disabled={isProcessing}
                    >
                      <span className="image-card-preview">
                        <img
                          src={`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`}
                          alt={file.filename}
                          loading="lazy"
                        />
                      </span>
                      <div className="image-card-body" style={{ padding: '0.7rem 0.9rem', gap: '0.2rem' }}>
                        <strong style={{ fontSize: '0.85rem' }}>{file.filename}</strong>
                        <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>{file.status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {resultFile ? (
              <div className="panel">
                <div className="panel-heading">
                  <h2>Vysledek</h2>
                  <p>Zpracovany obrazek je pripraven.</p>
                </div>
                <div className="upload-preview">
                  <img
                    src={`/objects/${resultFile.id}?user_id=${encodeURIComponent(activeUserId)}`}
                    alt={resultFile.filename}
                  />
                </div>
                <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                  <a
                    href={`/objects/${resultFile.id}?user_id=${encodeURIComponent(activeUserId)}`}
                    className="primary-button"
                    style={{ textDecoration: 'none', display: 'inline-block' }}
                    download={resultFile.filename}
                  >
                    Stahnout
                  </a>
                  <code className="upload-object-id" style={{ flex: 1 }}>{resultFile.filename}</code>
                </div>
              </div>
            ) : null}
          </section>
        </div>
      )}
    </>
  )
}

export default ImageProcessing
