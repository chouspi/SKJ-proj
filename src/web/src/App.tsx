import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Bucket = {
  id: number
  user_id: string
  name: string
  created_at: string
  bandwidth_bytes: number
  current_storage_bytes: number
  ingress_bytes: number
  egress_bytes: number
  internal_transfer_bytes: number
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
  if (size < 1024) {
    return `${size} B`
  }

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

function App() {
  const [draftUserId, setDraftUserId] = useState(DEFAULT_USER_ID)
  const [activeUserId, setActiveUserId] = useState(DEFAULT_USER_ID)
  const [draftBucketName, setDraftBucketName] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [activeBucketId, setActiveBucketId] = useState<number | null>(null)
  const [bucketBilling, setBucketBilling] = useState<Bucket | null>(null)
  const [files, setFiles] = useState<StoredFile[]>([])
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [isLoadingBuckets, setIsLoadingBuckets] = useState(false)
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [isLoadingBilling, setIsLoadingBilling] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isCreatingBucket, setIsCreatingBucket] = useState(false)
  const [busyFileId, setBusyFileId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const activeBucket = useMemo(
    () => buckets.find((bucket) => bucket.id === activeBucketId) ?? null,
    [activeBucketId, buckets],
  )

  function clearMessages() {
    setErrorMessage('')
    setSuccessMessage('')
  }

  async function loadBuckets(userId: string, preferredBucketId: number | null = null) {
    setIsLoadingBuckets(true)
    setErrorMessage('')

    try {
      const response = await fetch(`/buckets/?user_id=${encodeURIComponent(userId)}`)
      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const payload = (await response.json()) as Bucket[]
      setBuckets(payload)

      const resolvedBucketId = payload.some((bucket) => bucket.id === preferredBucketId)
        ? preferredBucketId
        : (payload[0]?.id ?? null)

      setActiveBucketId(resolvedBucketId)

      if (resolvedBucketId === null) {
        setFiles([])
        setBucketBilling(null)
      }

      return resolvedBucketId
    } catch (error) {
      setBuckets([])
      setActiveBucketId(null)
      setFiles([])
      setBucketBilling(null)
      setErrorMessage(error instanceof Error ? error.message : 'Nepodarilo se nacist buckety.')
      return null
    } finally {
      setIsLoadingBuckets(false)
    }
  }

  async function loadBucketObjects(userId: string, bucketId: number, nextIncludeDeleted: boolean) {
    setIsLoadingFiles(true)
    setErrorMessage('')

    try {
      const response = await fetch(
        `/buckets/${bucketId}/objects/?user_id=${encodeURIComponent(userId)}&include_deleted=${nextIncludeDeleted}`,
      )
      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const payload = (await response.json()) as StoredFile[]
      setFiles(payload)
    } catch (error) {
      setFiles([])
      setErrorMessage(error instanceof Error ? error.message : 'Nepodarilo se nacist objekty bucketu.')
    } finally {
      setIsLoadingFiles(false)
    }
  }

  async function loadBucketBilling(userId: string, bucketId: number) {
    setIsLoadingBilling(true)
    setErrorMessage('')

    try {
      const response = await fetch(`/buckets/${bucketId}/billing/?user_id=${encodeURIComponent(userId)}`)
      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const payload = (await response.json()) as Bucket
      setBucketBilling(payload)
    } catch (error) {
      setBucketBilling(null)
      setErrorMessage(error instanceof Error ? error.message : 'Nepodarilo se nacist billing bucketu.')
    } finally {
      setIsLoadingBilling(false)
    }
  }

  async function refreshActiveBucketData(bucketId: number | null) {
    if (bucketId === null) {
      setFiles([])
      setBucketBilling(null)
      return
    }

    await Promise.all([
      loadBucketObjects(activeUserId, bucketId, includeDeleted),
      loadBucketBilling(activeUserId, bucketId),
    ])
  }

  useEffect(() => {
    void loadBuckets(activeUserId, null)
  }, [activeUserId])

  useEffect(() => {
    if (activeBucketId === null) {
      setFiles([])
      setBucketBilling(null)
      return
    }

    void Promise.all([
      loadBucketObjects(activeUserId, activeBucketId, includeDeleted),
      loadBucketBilling(activeUserId, activeBucketId),
    ])
  }, [activeBucketId, activeUserId, includeDeleted])

  async function handleCreateBucket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const bucketName = draftBucketName.trim()

    if (!bucketName) {
      setErrorMessage('Zadej nazev bucketu.')
      setSuccessMessage('')
      return
    }

    setIsCreatingBucket(true)
    clearMessages()

    try {
      const response = await fetch(`/buckets/?user_id=${encodeURIComponent(activeUserId)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: bucketName }),
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const createdBucket = (await response.json()) as Bucket
      setDraftBucketName('')
      setSuccessMessage(`Bucket ${createdBucket.name} byl vytvoren.`)
      await loadBuckets(activeUserId, createdBucket.id)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Vytvoreni bucketu selhalo.')
    } finally {
      setIsCreatingBucket(false)
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedFile) {
      setErrorMessage('Vyber soubor pro upload.')
      setSuccessMessage('')
      return
    }

    setIsUploading(true)
    clearMessages()

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const query = new URLSearchParams({ user_id: activeUserId })
      if (activeBucketId !== null) {
        query.set('bucket_id', String(activeBucketId))
      }

      const response = await fetch(`/files/upload?${query.toString()}`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      setSelectedFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      const resolvedBucketId = await loadBuckets(activeUserId, activeBucketId)
      await refreshActiveBucketData(resolvedBucketId)
      setSuccessMessage(
        `Soubor ${selectedFile.name} byl prijat ke zpracovani${activeBucket ? ` v bucketu ${activeBucket.name}` : ' ve vychozim bucketu'}. Stav se zmeni na ready po ACK z Haystacku.`,
      )
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Upload selhal.')
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDelete(file: StoredFile) {
    setBusyFileId(file.id)
    clearMessages()

    try {
      const response = await fetch(`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      await refreshActiveBucketData(file.bucket_id)
      setSuccessMessage(`Objekt ${file.filename} byl soft-smazan.`)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Mazani selhalo.')
    } finally {
      setBusyFileId(null)
    }
  }

  async function handleDownload(file: StoredFile) {
    setBusyFileId(file.id)
    clearMessages()

    try {
      const response = await fetch(`/objects/${file.id}?user_id=${encodeURIComponent(activeUserId)}`)
      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = file.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)

      if (activeBucketId !== null) {
        void loadBucketBilling(activeUserId, activeBucketId)
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Download selhal.')
    } finally {
      setBusyFileId(null)
    }
  }

  async function handleRefresh() {
    clearMessages()
    const resolvedBucketId = await loadBuckets(activeUserId, activeBucketId)
    await refreshActiveBucketData(resolvedBucketId)
  }

  function handleUserSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextUserId = draftUserId.trim()

    if (!nextUserId) {
      setErrorMessage('User ID nesmi byt prazdne.')
      setSuccessMessage('')
      return
    }

    clearMessages()

    if (nextUserId === activeUserId) {
      void handleRefresh()
      return
    }

    setBuckets([])
    setFiles([])
    setBucketBilling(null)
    setActiveBucketId(null)
    setDraftBucketName('')
    setActiveUserId(nextUserId)
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <p className="eyebrow">Storage Frontend</p>
          <nav className="topbar-nav" aria-label="Hlavni navigace">
            <button type="button" className="topbar-tab is-active">
              Soubory
            </button>
          </nav>
        </div>

        <form className="topbar-user" onSubmit={handleUserSubmit}>
          <label className="topbar-user-field">
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
      </header>

      <section className="hero-panel">
        <div>
          <p className="eyebrow">Soubory</p>
          <h1>Sprava souboru, bucketu a billing metrik na jednom miste.</h1>
          <p className="hero-copy">
            Frontend bezi ve <code>src/web</code> a mluvi s aktualni FastAPI aplikaci pres Vite
            proxy. Uz umi pracovat s buckety, soft delete a billing metrikami nad novym backendem.
          </p>
        </div>

        <div className="hero-stats" aria-label="Aktualni uzivatel a stav">
          <article>
            <span>Aktivni user</span>
            <strong>{activeUserId}</strong>
          </article>
          <article>
            <span>Buckety</span>
            <strong>{buckets.length}</strong>
          </article>
          <article>
            <span>Aktivni bucket</span>
            <strong>{activeBucket?.name ?? 'zadny'}</strong>
          </article>
          <article>
            <span>Storage v bucketu</span>
            <strong>{bucketBilling ? formatBytes(bucketBilling.current_storage_bytes) : '-'}</strong>
          </article>
        </div>
      </section>

      <section className="workspace">
        <aside className="sidebar">
          <div className="panel">
            <div className="panel-heading">
              <h2>Novy bucket</h2>
              <p>Bucket je logicka skupina objektu a nositel billing metrik.</p>
            </div>

            <form className="stack" onSubmit={handleCreateBucket}>
              <label className="field">
                <span>Nazev bucketu</span>
                <input
                  type="text"
                  value={draftBucketName}
                  onChange={(event) => setDraftBucketName(event.target.value)}
                  placeholder="alice-photos"
                />
              </label>
              <button type="submit" className="primary-button" disabled={isCreatingBucket}>
                {isCreatingBucket ? 'Vytvarim...' : 'Vytvorit bucket'}
              </button>
            </form>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Upload</h2>
              <p>
                Soubor se nahraje do aktivniho bucketu. Pokud zadny neni vybrany, backend pouzije
                vychozi bucket `default-&lt;user_id&gt;`.
              </p>
            </div>

            <form className="stack" onSubmit={handleUpload}>
              <label className="field">
                <span>Cilovy bucket</span>
                <input type="text" value={activeBucket?.name ?? 'Vychozi bucket backendu'} readOnly />
              </label>

              <label className="upload-dropzone">
                <span>{selectedFile ? selectedFile.name : 'Vyber soubor z disku'}</span>
                <small>
                  {selectedFile
                    ? formatBytes(selectedFile.size)
                    : 'Upload aktualizuje ingress a bandwidth counters zvoleneho bucketu.'}
                </small>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                />
              </label>

              <button type="submit" className="primary-button" disabled={isUploading}>
                {isUploading ? 'Nahravam...' : 'Nahrat soubor'}
              </button>
            </form>
          </div>

          <div className="panel info-panel">
            <div className="panel-heading">
              <h2>Napojeni</h2>
              <p>Frontend ocekava lokalni backend na `127.0.0.1:8000`.</p>
            </div>
            <ul className="info-list">
              <li>
                Buckety: <code>GET /buckets</code>
              </li>
              <li>
                Vytvoreni: <code>POST /buckets</code>
              </li>
              <li>
                Objekty: <code>GET /buckets/&lt;id&gt;/objects</code>
              </li>
              <li>
                Billing: <code>GET /buckets/&lt;id&gt;/billing</code>
              </li>
              <li>
                Upload: <code>POST /files/upload</code>
              </li>
              <li>
                Download/Delete: <code>/objects/&lt;id&gt;</code>
              </li>
            </ul>
          </div>
        </aside>

        <section className="content-column">
          <div className="toolbar panel">
            <div className="panel-heading">
              <h2>Buckety a objekty</h2>
              <p>Vyber bucket, sleduj billing a spravuj jeho obsah.</p>
            </div>

            <button
              type="button"
              className="secondary-button"
              onClick={() => void handleRefresh()}
              disabled={isLoadingBuckets || isLoadingFiles || isLoadingBilling}
            >
              {isLoadingBuckets || isLoadingFiles || isLoadingBilling ? 'Nacitam...' : 'Obnovit data'}
            </button>
          </div>

          {errorMessage ? <div className="feedback error">{errorMessage}</div> : null}
          {successMessage ? <div className="feedback success">{successMessage}</div> : null}

          <div className="panel">
            <div className="panel-heading panel-heading-inline">
              <div>
                <h2>Seznam bucketu</h2>
                <p>Bucket urcuje namespace objektu i billing counters.</p>
              </div>
              <span className="status-pill neutral">
                {isLoadingBuckets ? 'Nacitam buckety' : `${buckets.length} bucketu`}
              </span>
            </div>

            {buckets.length === 0 ? (
              <div className="empty-state empty-state-compact">
                <h3>Zatim zadny bucket</h3>
                <p>Vytvor bucket rucne nebo nahraj soubor a backend zalozi vychozi bucket sam.</p>
              </div>
            ) : (
              <div className="bucket-grid">
                {buckets.map((bucket) => {
                  const isSelected = bucket.id === activeBucketId

                  return (
                    <button
                      key={bucket.id}
                      type="button"
                      className={`bucket-card${isSelected ? ' is-selected' : ''}`}
                      onClick={() => setActiveBucketId(bucket.id)}
                    >
                      <div className="bucket-card-header">
                        <strong>{bucket.name}</strong>
                        <span className={`status-pill${isSelected ? ' active' : ' neutral'}`}>
                          {isSelected ? 'Aktivni' : 'Vybrat'}
                        </span>
                      </div>
                      <span className="bucket-card-meta">ID {bucket.id}</span>
                      <span className="bucket-card-meta">Vytvoren {formatDate(bucket.created_at)}</span>
                      <span className="bucket-card-meta">
                        Storage {formatBytes(bucket.current_storage_bytes)}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          <div className="panel metrics-panel">
            <div className="panel-heading panel-heading-inline">
              <div>
                <h2>Billing aktivniho bucketu</h2>
                <p>
                  {activeBucket
                    ? `Metriky pro bucket ${activeBucket.name}.`
                    : 'Vyber bucket pro zobrazeni billing metrik.'}
                </p>
              </div>
              <span className="status-pill neutral">
                {isLoadingBilling ? 'Nacitam billing' : activeBucket ? 'Aktualni stav' : 'Bez bucketu'}
              </span>
            </div>

            {bucketBilling ? (
              <div className="metric-grid">
                <article>
                  <span>Storage</span>
                  <strong>{formatBytes(bucketBilling.current_storage_bytes)}</strong>
                </article>
                <article>
                  <span>Bandwidth</span>
                  <strong>{formatBytes(bucketBilling.bandwidth_bytes)}</strong>
                </article>
                <article>
                  <span>Ingress</span>
                  <strong>{formatBytes(bucketBilling.ingress_bytes)}</strong>
                </article>
                <article>
                  <span>Egress</span>
                  <strong>{formatBytes(bucketBilling.egress_bytes)}</strong>
                </article>
                <article>
                  <span>Internal</span>
                  <strong>{formatBytes(bucketBilling.internal_transfer_bytes)}</strong>
                </article>
              </div>
            ) : (
              <div className="empty-state empty-state-compact">
                <h3>Billing zatim neni k dispozici</h3>
                <p>Vyber bucket nebo nejdriv nejaky vytvor.</p>
              </div>
            )}
          </div>

          <div className="panel table-panel">
            <div className="table-panel-header">
              <div>
                <h2>Objekty v bucketu</h2>
                <p>
                  {activeBucket
                    ? `Obsah bucketu ${activeBucket.name}.`
                    : 'Vyber bucket pro zobrazeni seznamu objektu.'}
                </p>
              </div>

              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={includeDeleted}
                  onChange={(event) => setIncludeDeleted(event.target.checked)}
                />
                <span>Zobrazit soft-smazane</span>
              </label>
            </div>

            {activeBucketId === null ? (
              <div className="empty-state">
                <h3>Neni vybran bucket</h3>
                <p>Vyber bucket ze seznamu nebo vytvor novy v leve casti dashboardu.</p>
              </div>
            ) : isLoadingFiles && files.length === 0 ? (
              <div className="empty-state">
                <h3>Nacitam objekty</h3>
                <p>Frontend ceka na odpoved z `GET /buckets/&lt;id&gt;/objects`.</p>
              </div>
            ) : files.length === 0 ? (
              <div className="empty-state">
                <h3>Zatim tu nic neni</h3>
                <p>Bucket zatim neobsahuje zadne objekty nebo vsechny zustaly skryte po soft delete.</p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Nazev</th>
                      <th>Stav</th>
                      <th>Velikost</th>
                      <th>Vytvoreno</th>
                      <th>Akce</th>
                    </tr>
                  </thead>
                  <tbody>
                    {files.map((file) => {
                      const isBusy = busyFileId === file.id

                      return (
                        <tr key={file.id}>
                          <td>
                            <div className="file-meta">
                              <strong>{file.filename}</strong>
                              <span>{file.id}</span>
                            </div>
                          </td>
                          <td>
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
                          </td>
                          <td>{formatBytes(file.size)}</td>
                          <td>{formatDate(file.created_at)}</td>
                          <td>
                            <div className="actions">
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => void handleDownload(file)}
                                disabled={isBusy || file.is_deleted || file.status !== 'ready'}
                              >
                                Download
                              </button>
                              <button
                                type="button"
                                className="danger-button"
                                onClick={() => void handleDelete(file)}
                                disabled={isBusy || file.is_deleted}
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </section>
    </main>
  )
}

export default App
