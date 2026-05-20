import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type StoredFile = {
  id: string
  filename: string
  size: number
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
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [files, setFiles] = useState<StoredFile[]>([])
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [busyFileId, setBusyFileId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  async function loadFiles(userId: string) {
    setIsLoadingFiles(true)
    setErrorMessage('')

    try {
      const response = await fetch(`/files?user_id=${encodeURIComponent(userId)}`)
      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const payload = (await response.json()) as StoredFile[]
      setFiles(payload)
    } catch (error) {
      setFiles([])
      setErrorMessage(error instanceof Error ? error.message : 'Nepodarilo se nacist soubory.')
    } finally {
      setIsLoadingFiles(false)
    }
  }

  useEffect(() => {
    void loadFiles(activeUserId)
  }, [activeUserId])

  function clearMessages() {
    setErrorMessage('')
    setSuccessMessage('')
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

      const response = await fetch(`/files/upload?user_id=${encodeURIComponent(activeUserId)}`, {
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
      setSuccessMessage(`Soubor ${selectedFile.name} byl nahrany.`)
      await loadFiles(activeUserId)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Upload selhal.')
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDelete(fileId: string) {
    setBusyFileId(fileId)
    clearMessages()

    try {
      const response = await fetch(`/files/${fileId}?user_id=${encodeURIComponent(activeUserId)}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      setSuccessMessage('Soubor byl smazan.')
      await loadFiles(activeUserId)
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
      const response = await fetch(`/files/${file.id}?user_id=${encodeURIComponent(activeUserId)}`)
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
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Download selhal.')
    } finally {
      setBusyFileId(null)
    }
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
      void loadFiles(nextUserId)
      return
    }

    setActiveUserId(nextUserId)
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Storage Frontend</p>
          <h1>Gateway dashboard pro upload, download a spravu souboru.</h1>
          <p className="hero-copy">
            Frontend bezi ve <code>src/web</code> a mluvi s aktualni FastAPI aplikaci pres Vite
            proxy. V dalsich iteracich muze zustat UI vrstva stejna, i kdyz se backend rozdeli na
            gateway, broker a haystack storage node.
          </p>
        </div>

        <div className="hero-stats" aria-label="Aktualni uzivatel a stav">
          <article>
            <span>Aktivni user</span>
            <strong>{activeUserId}</strong>
          </article>
          <article>
            <span>Pocet souboru</span>
            <strong>{files.length}</strong>
          </article>
          <article>
            <span>Backend</span>
            <strong>FastAPI /files</strong>
          </article>
        </div>
      </section>

      <section className="workspace">
        <aside className="sidebar">
          <div className="panel">
            <div className="panel-heading">
              <h2>Uzivatel</h2>
              <p>Zmena vlastnika, pod kterym se pracuje se soubory.</p>
            </div>

            <form className="stack" onSubmit={handleUserSubmit}>
              <label className="field">
                <span>User ID</span>
                <input
                  type="text"
                  value={draftUserId}
                  onChange={(event) => setDraftUserId(event.target.value)}
                  placeholder="alice"
                />
              </label>
              <button type="submit" className="primary-button">
                Pouzit usera
              </button>
            </form>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>Upload</h2>
              <p>Nahrani souboru do aktualniho storage backendu.</p>
            </div>

            <form className="stack" onSubmit={handleUpload}>
              <label className="upload-dropzone">
                <span>{selectedFile ? selectedFile.name : 'Vyber soubor z disku'}</span>
                <small>
                  {selectedFile ? formatBytes(selectedFile.size) : 'Soucasny backend uklada soubor ihned na disk.'}
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
                List: <code>GET /files</code>
              </li>
              <li>
                Upload: <code>POST /files/upload</code>
              </li>
              <li>
                Download: <code>GET /files/&lt;id&gt;</code>
              </li>
              <li>
                Delete: <code>DELETE /files/&lt;id&gt;</code>
              </li>
            </ul>
          </div>
        </aside>

        <section className="content-column">
          <div className="toolbar panel">
            <div className="panel-heading">
              <h2>Soubory uzivatele</h2>
              <p>Aktualni stav objektu ulozenych pod `user_id={activeUserId}`.</p>
            </div>

            <button
              type="button"
              className="secondary-button"
              onClick={() => void loadFiles(activeUserId)}
              disabled={isLoadingFiles}
            >
              {isLoadingFiles ? 'Nacitam...' : 'Obnovit seznam'}
            </button>
          </div>

          {errorMessage ? <div className="feedback error">{errorMessage}</div> : null}
          {successMessage ? <div className="feedback success">{successMessage}</div> : null}

          <div className="panel table-panel">
            {isLoadingFiles && files.length === 0 ? (
              <div className="empty-state">
                <h3>Nacitam seznam</h3>
                <p>Frontend ceka na odpoved z `GET /files`.</p>
              </div>
            ) : files.length === 0 ? (
              <div className="empty-state">
                <h3>Zatim tu nic neni</h3>
                <p>
                  Pro vybraneho uzivatele se nenasly zadne soubory. Nahraj prvni objekt nebo zmen
                  `user_id`.
                </p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Nazev</th>
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
                          <td>{formatBytes(file.size)}</td>
                          <td>{formatDate(file.created_at)}</td>
                          <td>
                            <div className="actions">
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => void handleDownload(file)}
                                disabled={isBusy}
                              >
                                Download
                              </button>
                              <button
                                type="button"
                                className="danger-button"
                                onClick={() => void handleDelete(file.id)}
                                disabled={isBusy}
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
