import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

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

type UploadedFile = {
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

async function readErrorMessage(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `Request failed with status ${response.status}.`
  } catch {
    return `Request failed with status ${response.status}.`
  }
}

function Upload() {
  const [draftUserId, setDraftUserId] = useState(DEFAULT_USER_ID)
  const [activeUserId, setActiveUserId] = useState(DEFAULT_USER_ID)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [uploadedObject, setUploadedObject] = useState<UploadedFile | null>(null)
  const [pollStatus, setPollStatus] = useState<string | null>(null)
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [selectedBucketId, setSelectedBucketId] = useState<number | null>(null)
  const [isLoadingBuckets, setIsLoadingBuckets] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const pollingRef = useRef<number | null>(null)

  async function loadBuckets(userId: string) {
    setIsLoadingBuckets(true)
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
    } finally {
      setIsLoadingBuckets(false)
    }
  }

  useEffect(() => {
    void loadBuckets(activeUserId)
  }, [activeUserId])

  function clearMessages() {
    setErrorMessage('')
  }

  function handleFileChange(file: File | null) {
    setSelectedFile(file)
    setUploadedObject(null)
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    setPollStatus(null)

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
    }

    if (file) {
      setPreviewUrl(URL.createObjectURL(file))
    }
  }

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      if (pollingRef.current !== null) clearInterval(pollingRef.current)
    }
  }, [previewUrl])

  useEffect(() => {
    if (pollStatus === 'ready' || pollStatus === 'failed') {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [pollStatus])

  async function pollUploadStatus(objectId: string) {
    try {
      const response = await fetch(`/upload/${objectId}?user_id=${encodeURIComponent(activeUserId)}`)
      if (!response.ok) {
        setPollStatus('failed')
        return
      }
      const payload = (await response.json()) as UploadedFile
      setPollStatus(payload.status)
      setUploadedObject(payload)
    } catch {
      setPollStatus('failed')
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedFile) {
      setErrorMessage('Vyber soubor pro upload.')
      return
    }

    setIsUploading(true)
    clearMessages()
    setUploadedObject(null)
    setPollStatus(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const query = new URLSearchParams({ user_id: activeUserId })
      if (selectedBucketId !== null) {
        query.set('bucket_id', String(selectedBucketId))
      }

      const response = await fetch(`/files/upload?${query.toString()}`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const payload = (await response.json()) as UploadedFile
      setUploadedObject(payload)
      setPollStatus(payload.status)

      pollingRef.current = window.setInterval(() => {
        void pollUploadStatus(payload.id)
      }, 3000)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Upload selhal.')
    } finally {
      setIsUploading(false)
    }
  }

  function handleUserSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextUserId = draftUserId.trim()
    if (!nextUserId) {
      setErrorMessage('User ID nesmi byt prazdne.')
      return
    }
    clearMessages()
    setActiveUserId(nextUserId)
  }

  return (
    <>
      <section className="legacy-bar">
        <span className="eyebrow">Upload fotky</span>
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
          <p className="eyebrow">Nahrani souboru</p>
          <h1>Nahraj soubor</h1>
        </div>
      </section>

      {errorMessage ? <div className="feedback error">{errorMessage}</div> : null}

      <section className="workspace">
        <aside className="sidebar">
          <div className="panel">
            <div className="panel-heading">
              <h2>Nahrat soubor</h2>
              <p>Vyber obrazek z disku a nahraj ho na server.</p>
            </div>

            <form className="stack" onSubmit={handleUpload}>
              <label className="field">
                <span>Album (bucket)</span>
                <select
                  value={selectedBucketId ?? ''}
                  onChange={(event) => setSelectedBucketId(event.target.value ? Number(event.target.value) : null)}
                  disabled={isLoadingBuckets}
                >
                  {isLoadingBuckets ? (
                    <option value="">Nacitam alba...</option>
                  ) : buckets.length === 0 ? (
                    <option value="">Zadna alba</option>
                  ) : (
                    buckets.map((bucket) => (
                      <option key={bucket.id} value={bucket.id}>
                        {bucket.name}
                      </option>
                    ))
                  )}
                </select>
              </label>

              <label className="field upload-dropzone">
                <span>{selectedFile ? selectedFile.name : 'Vyber soubor z disku'}</span>
                <small>
                  {selectedFile
                    ? `${(selectedFile.size / 1024).toFixed(1)} KB`
                    : 'Podporovany jsou obrazky (JPEG, PNG, atd.).'}
                </small>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
                />
              </label>

              <button type="submit" className="primary-button" disabled={isUploading || !selectedFile}>
                {isUploading ? 'Nahravam...' : 'Upload'}
              </button>
            </form>
          </div>
        </aside>

        <section className="content-column">
          <div className="panel">
            <div className="panel-heading">
              <h2>Nahled</h2>
              <p>Zde se zobrazi nahled vybraneho obrazku.</p>
            </div>

            {previewUrl ? (
              <div className="upload-preview">
                <img src={previewUrl} alt={selectedFile?.name ?? 'nahled'} />
              </div>
            ) : (
              <div className="empty-state">
                <h3>Zadny obrazek nevybran</h3>
                <p>Pomoci formulare vlevo vyber obrazek pro nahled a upload.</p>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Stav uploadu</h2>
              <p>Informace o prave nahranem souboru a jeho zpracovani.</p>
            </div>

            {uploadedObject ? (
              <div className="stack">
                <div className="field">
                  <span>object_id</span>
                  <code className="upload-object-id">{uploadedObject.id}</code>
                </div>

                <div className="field">
                  <span>status</span>
                  <span
                    className={`status-pill${
                      pollStatus === 'ready'
                        ? ' active'
                        : pollStatus === 'failed'
                          ? ' deleted'
                          : ' neutral'
                    }`}
                  >
                    {pollStatus ?? uploadedObject.status}
                  </span>
                </div>

                <div className="upload-message">
                  {pollStatus === 'ready'
                    ? 'Soubor byl uspesne zapsan a je pripraven.'
                    : pollStatus === 'failed'
                      ? 'Zpracovani souboru selhalo.'
                      : 'Soubor byl prijat, ceka se na ACK API volani.'}
                </div>

                {pollStatus !== 'ready' && pollStatus !== 'failed' ? (
                  <div className="upload-polling">Kontrola stavu kazdych 3 sekund...</div>
                ) : null}
              </div>
            ) : (
              <div className="empty-state">
                <h3>Zatim nic nenahrano</h3>
                <p>Po uploadu se zde zobrazi object_id, stav a dalsi informace.</p>
              </div>
            )}
          </div>
        </section>
      </section>
    </>
  )
}

export default Upload
