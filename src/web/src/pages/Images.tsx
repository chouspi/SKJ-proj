import { useEffect, useRef, useState } from 'react'

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

function formatDate(value: string) {
  return new Intl.DateTimeFormat('cs-CZ', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

async function readErrorMessage(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `Request failed with status ${response.status}.`
  } catch {
    return `Request failed with status ${response.status}.`
  }
}

function Images() {
  const [draftUserId, setDraftUserId] = useState(DEFAULT_USER_ID)
  const [activeUserId, setActiveUserId] = useState(DEFAULT_USER_ID)
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [selectedBucketId, setSelectedBucketId] = useState<number | null>(null)
  const [files, setFiles] = useState<StoredFile[]>([])
  const [isLoadingBuckets, setIsLoadingBuckets] = useState(false)
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [busyFileId, setBusyFileId] = useState<string | null>(null)
  const [detailFile, setDetailFile] = useState<StoredFile | null>(null)
  const dialogRef = useRef<HTMLDialogElement | null>(null)

  async function loadBuckets(userId: string) {
    setIsLoadingBuckets(true)
    setErrorMessage('')
    try {
      const response = await fetch(`/buckets/?user_id=${encodeURIComponent(userId)}`)
      if (!response.ok) throw new Error(await readErrorMessage(response))
      const payload = (await response.json()) as Bucket[]
      setBuckets(payload)
      if (payload.length > 0) {
        setSelectedBucketId((prev) =>
          prev !== null && payload.some((b) => b.id === prev) ? prev : payload[0].id,
        )
      } else {
        setSelectedBucketId(null)
        setFiles([])
      }
    } catch (error) {
      setBuckets([])
      setSelectedBucketId(null)
      setFiles([])
      setErrorMessage(error instanceof Error ? error.message : 'Nepodarilo se nacist buckety.')
    } finally {
      setIsLoadingBuckets(false)
    }
  }

  async function loadFiles(userId: string, bucketId: number) {
    setIsLoadingFiles(true)
    setErrorMessage('')
    try {
      const response = await fetch(
        `/buckets/${bucketId}/objects/?user_id=${encodeURIComponent(userId)}&include_deleted=false`,
      )
      if (!response.ok) throw new Error(await readErrorMessage(response))
      const payload = (await response.json()) as StoredFile[]
      setFiles(payload)
    } catch (error) {
      setFiles([])
      setErrorMessage(error instanceof Error ? error.message : 'Nepodarilo se nacist objekty.')
    } finally {
      setIsLoadingFiles(false)
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

  async function handleDownload(file: StoredFile) {
    setBusyFileId(file.id)
    setErrorMessage('')
    try {
      const response = await fetch(`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`)
      if (!response.ok) throw new Error(await readErrorMessage(response))
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = file.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Download selhal.')
    } finally {
      setBusyFileId(null)
    }
  }

  async function handleDelete(file: StoredFile) {
    setBusyFileId(file.id)
    setErrorMessage('')
    setSuccessMessage('')
    try {
      const response = await fetch(`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error(await readErrorMessage(response))
      setSuccessMessage(`Objekt ${file.filename} byl smazan.`)
      if (selectedBucketId !== null) {
        void loadFiles(activeUserId, selectedBucketId)
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Mazani selhalo.')
    } finally {
      setBusyFileId(null)
    }
  }

  function openDetail(file: StoredFile) {
    setDetailFile(file)
    dialogRef.current?.showModal()
  }

  function closeDetail() {
    setDetailFile(null)
    dialogRef.current?.close()
  }

  function handleUserSubmit(event: React.FormEvent<HTMLFormElement>) {
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
        <span className="eyebrow">Obrazky</span>
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
          <p className="eyebrow">Prohlizeni obrazku</p>
          <h1>Obrazky</h1>
          <p className="hero-copy">
            Vyber bucket a prohlizej vsechny obrazky v nem ulozene.
          </p>
        </div>
      </section>

      {errorMessage ? <div className="feedback error">{errorMessage}</div> : null}
      {successMessage ? <div className="feedback success">{successMessage}</div> : null}

      <div className="panel">
        <div className="toolbar">
          <div className="panel-heading">
            <h2>Vyber bucket</h2>
            <p>Zvol bucket, ze ktereho chces zobrazit obrazky.</p>
          </div>
          <select
            className="bucket-select"
            value={selectedBucketId ?? ''}
            onChange={(event) => setSelectedBucketId(event.target.value ? Number(event.target.value) : null)}
            disabled={isLoadingBuckets}
          >
            {isLoadingBuckets ? (
              <option value="">Nacitam buckety...</option>
            ) : buckets.length === 0 ? (
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

      {selectedBucketId === null ? (
        <div className="empty-state">
          <h3>Neni vybran bucket</h3>
          <p>Vyber bucket pro zobrazeni obrazku.</p>
        </div>
      ) : isLoadingFiles ? (
        <div className="empty-state">
          <h3>Nacitam obrazky</h3>
          <p>Frontend ceka na odpoved z API.</p>
        </div>
      ) : files.length === 0 ? (
        <div className="empty-state">
          <h3>Zadne obrazky</h3>
          <p>Tento bucket neobsahuje zadne objekty.</p>
        </div>
      ) : (
        <div className="image-grid">
          {files.map((file) => (
            <div key={file.id} className="image-card">
              <a
                href={`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`}
                className="image-card-preview"
                target="_blank"
                rel="noreferrer"
              >
                <img
                  src={`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`}
                  alt={file.filename}
                  loading="lazy"
                />
              </a>
              <div className="image-card-body">
                <div className="image-card-info">
                  <strong className="image-card-name">{file.filename}</strong>
                  <span className="image-card-meta">
                    {formatBytes(file.size)} &middot; {formatDate(file.created_at)}
                  </span>
                  <span
                    className={`status-pill${
                      file.is_deleted
                        ? ' deleted'
                        : file.status === 'ready'
                          ? ' active'
                          : file.status === 'failed'
                            ? ' deleted'
                            : ' neutral'
                    }`}
                  >
                    {file.is_deleted ? 'Soft deleted' : file.status}
                  </span>
                </div>
                <div className="image-card-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => openDetail(file)}
                    disabled={busyFileId === file.id}
                  >
                    Detail
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => void handleDownload(file)}
                    disabled={busyFileId === file.id || file.is_deleted || file.status !== 'ready'}
                  >
                    Download
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => void handleDelete(file)}
                    disabled={busyFileId === file.id || file.is_deleted}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <dialog ref={dialogRef} className="detail-dialog" onClick={(e) => { if (e.target === dialogRef.current) closeDetail() }}>
        {detailFile ? (
          <div className="detail-content">
            <div className="detail-header">
              <h2>{detailFile.filename}</h2>
              <button type="button" className="secondary-button" onClick={closeDetail}>
                Zavrit
              </button>
            </div>
            <img
              src={`/objects/${detailFile.id}?user_id=${encodeURIComponent(activeUserId)}`}
              alt={detailFile.filename}
              className="detail-image"
            />
            <div className="detail-meta">
              <div className="detail-meta-row">
                <span>object_id</span>
                <code>{detailFile.id}</code>
              </div>
              <div className="detail-meta-row">
                <span>Velikost</span>
                <strong>{formatBytes(detailFile.size)}</strong>
              </div>
              <div className="detail-meta-row">
                <span>Status</span>
                <span
                  className={`status-pill${
                    detailFile.is_deleted
                      ? ' deleted'
                      : detailFile.status === 'ready'
                        ? ' active'
                        : ' neutral'
                  }`}
                >
                  {detailFile.is_deleted ? 'Soft deleted' : detailFile.status}
                </span>
              </div>
              <div className="detail-meta-row">
                <span>Vytvoreno</span>
                <strong>{formatDate(detailFile.created_at)}</strong>
              </div>
              <div className="detail-meta-row">
                <span>Volume ID</span>
                <strong>{detailFile.volume_id ?? '-'}</strong>
              </div>
              <div className="detail-meta-row">
                <span>Offset</span>
                <strong>{detailFile.offset ?? '-'}</strong>
              </div>
              <div className="detail-meta-row">
                <span>Bucket ID</span>
                <strong>{detailFile.bucket_id}</strong>
              </div>
            </div>
          </div>
        ) : null}
      </dialog>
    </>
  )
}

export default Images
