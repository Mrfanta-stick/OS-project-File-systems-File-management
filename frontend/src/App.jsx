
import { useEffect, useState } from 'react'
import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [system, setSystem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [filename, setFilename] = useState('')
  const [content, setContent] = useState('')

  async function fetchState() {
    try {
      setError('')
      const response = await fetch(`${API_BASE}/api/state`)
      if (!response.ok) throw new Error('Could not fetch file-system information.')
      const data = await response.json()
      setSystem(data)
    } catch (err) {
      setError('Backend not connected. Make sure your FastAPI server is running.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchState()
  }, [])

  async function createFile(e) {
    e.preventDefault()
    setMessage('')
    setError('')

    if (!filename.trim()) {
      setError('Please enter a file name.')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/api/touch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: filename.trim() }),
      })

      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to create file.')

      setMessage(data.message || 'File created successfully.')
      setFilename('')
      fetchState()
    } catch (err) {
      setError(err.message)
    }
  }

  async function writeFile(e) {
    e.preventDefault()
    setMessage('')
    setError('')

    if (!filename.trim()) {
      setError('Enter the file name first.')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/api/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: filename.trim(),
          content,
        }),
      })

      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to write file.')

      setMessage(data.message || 'File written successfully.')
      setContent('')
      fetchState()
    } catch (err) {
      setError(err.message)
    }
  }

  async function formatDisk() {
    const confirmed = window.confirm(
      'Are you sure you want to format the disk? This will erase the file-system data.'
    )

    if (!confirmed) return

    setMessage('')
    setError('')

    try {
      const response = await fetch(`${API_BASE}/api/format`, {
        method: 'POST',
      })

      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to format disk.')

      setMessage(data.message || 'Disk formatted successfully.')
      setFilename('')
      setContent('')
      fetchState()
    } catch (err) {
      setError(err.message)
    }
  }

  const files = Array.isArray(system?.files) ? system.files : []
  const inodes = Array.isArray(system?.inodes) ? system.inodes : []

  function getFileName(file, index) {
    if (typeof file === 'string') return file
    if (file?.name) return file.name
    if (file?.filename) return file.filename
    if (Array.isArray(file)) return String(file[1] ?? `Entry ${index + 1}`)
    return `Directory entry ${index + 1}`
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">OS</div>
          <div>
            <h2>FileSys</h2>
            <span>Operating System Project</span>
          </div>
        </div>

        <p className="menu-heading">WORKSPACE</p>
        <a className="nav-link active" href="#dashboard">▦ Dashboard</a>
        <a className="nav-link" href="#files">▤ File Manager</a>
        <a className="nav-link" href="#disk">▦ Disk Visualizer</a>
        <a className="nav-link" href="#operations">⚙ Operations</a>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot"></span>
            <span>File System Simulator</span>
          </div>
          <small>Based on OS File Management</small>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="breadcrumb">Workspace / Dashboard</p>
            <h1>File System Dashboard</h1>
          </div>
          <button className="refresh-button" onClick={fetchState}>
            ↻ Refresh
          </button>
        </header>

        <section className="welcome-section" id="dashboard">
          <div>
            <p className="eyebrow">OPERATING SYSTEMS · FILE MANAGEMENT</p>
            <h2>Virtual Disk Overview</h2>
            <p>Monitor your file system, inodes and disk organization.</p>
          </div>
          <div className="disk-symbol">▤</div>
        </section>

        {error && <div className="alert error-alert">{error}</div>}
        {message && <div className="alert success-alert">{message}</div>}

        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-top">
              <span>Total Disk Size</span>
              <span className="stat-icon purple">▤</span>
            </div>
            <h2>64 KB</h2>
            <p>128 blocks × 512 bytes</p>
          </div>

          <div className="stat-card">
            <div className="stat-top">
              <span>Total Blocks</span>
              <span className="stat-icon blue">▦</span>
            </div>
            <h2>{system?.blocks_count ?? 128}</h2>
            <p>Blocks in virtual disk</p>
          </div>

          <div className="stat-card">
            <div className="stat-top">
              <span>Total Inodes</span>
              <span className="stat-icon orange">▧</span>
            </div>
            <h2>{loading ? '...' : inodes.length || 32}</h2>
            <p>Inode table capacity</p>
          </div>

          <div className="stat-card">
            <div className="stat-top">
              <span>Directory Entries</span>
              <span className="stat-icon green">▤</span>
            </div>
            <h2>{loading ? '...' : files.length}</h2>
            <p>Entries returned by backend</p>
          </div>
        </section>

        <section className="content-grid">
          <div className="panel disk-panel" id="disk">
            <div className="panel-heading">
              <div>
                <h3>Disk Block Organization</h3>
                <p>How the 128 blocks are arranged</p>
              </div>
              <span className="tag">512 bytes / block</span>
            </div>

            <div className="disk-legend">
              <span><i className="legend-system"></i> System blocks</span>
              <span><i className="legend-data"></i> Data region</span>
            </div>

            <div className="block-grid">
              {Array.from({ length: 128 }, (_, index) => (
                <div
                  key={index}
                  className={`disk-block ${index < 11 ? 'system-block' : 'data-block'}`}
                  title={
                    index === 0 ? 'Block 0: Superblock' :
                    index === 1 ? 'Block 1: Inode bitmap' :
                    index === 2 ? 'Block 2: Data bitmap' :
                    index <= 10 ? `Block ${index}: Inode table` :
                    `Block ${index}: Data region (allocation status not yet displayed)`
                  }
                >
                  {index}
                </div>
              ))}
            </div>

            <div className="disk-note">
              Blocks 0–10 are reserved for file-system metadata. Blocks 11–127
              form the data region. Allocation status will be connected in a later step.
            </div>
          </div>

          <div className="panel operations-panel" id="operations">
            <div className="panel-heading">
              <div>
                <h3>File Operations</h3>
                <p>Perform actions on your virtual disk</p>
              </div>
            </div>

            <form onSubmit={createFile} className="operation-form">
              <label htmlFor="filename">File name</label>
              <input
                id="filename"
                type="text"
                placeholder="Example: notes.txt"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
              />
              <button className="primary-button" type="submit">
                + Create File
              </button>
            </form>

            <form onSubmit={writeFile} className="operation-form">
              <label htmlFor="filecontent">File content</label>
              <textarea
                id="filecontent"
                placeholder="Enter the content you want to write..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows="4"
              />
              <button className="secondary-button" type="submit">
                Write to File
              </button>
            </form>

            <button className="format-button" onClick={formatDisk}>
              Format Virtual Disk
            </button>
          </div>
        </section>

        <section className="panel files-panel" id="files">
          <div className="panel-heading">
            <div>
              <h3>Root Directory</h3>
              <p>Files and entries returned by the backend</p>
            </div>
            <button className="small-button" onClick={fetchState}>
              Refresh list
            </button>
          </div>

          {loading ? (
            <p className="empty-state">Loading file-system data...</p>
          ) : files.length === 0 ? (
            <p className="empty-state">No directory entries found.</p>
          ) : (
            <div className="file-list">
              {files.map((file, index) => (
                <div className="file-row" key={index}>
                  <span className="file-symbol">▤</span>
                  <span>{getFileName(file, index)}</span>
                  <span className="file-label">Directory entry</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <footer>
          <span>OS File System Simulator</span>
          <span>Virtual disk · 64 KB · 128 blocks</span>
        </footer>
      </main>
    </div>
  )
}

export default App
