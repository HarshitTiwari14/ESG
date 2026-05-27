import { useState, useRef } from 'react'
import { upload } from '../services/api'
import { Upload, CheckCircle, AlertCircle, FileText } from 'lucide-react'
import './UploadPage.css'

const SOURCES = [
  {
    key: 'sap',
    label: 'SAP Fuel & Procurement',
    scope: 'Scope 1',
    desc: 'MB51 goods movement flat-file export (semicolon or tab delimited). German or English headers accepted.',
    accept: '.csv,.txt,.xlsx',
    color: 'var(--scope1)',
  },
  {
    key: 'utility',
    label: 'Utility Electricity',
    scope: 'Scope 2',
    desc: 'Portal CSV export from DISCOM or utility provider. Columns: Meter ID, Billing Period, Consumption (kWh).',
    accept: '.csv',
    color: 'var(--scope2)',
  },
  {
    key: 'travel',
    label: 'Corporate Travel',
    scope: 'Scope 3',
    desc: 'Navan or Concur trip report CSV. Includes flights, hotels, car rentals, taxis, and train journeys.',
    accept: '.csv',
    color: 'var(--scope3)',
  },
]

function UploadZone({ source, onSuccess }) {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle') // idle | uploading | done | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleFile = (f) => {
    setFile(f)
    setStatus('idle')
    setError('')
    setResult(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const doUpload = async () => {
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    fd.append('source_type', source.key)
    setStatus('uploading')
    setError('')
    try {
      const r = await upload(fd)
      setResult(r.data)
      setStatus('done')
      onSuccess?.()
    } catch (e) {
      setError(e.response?.data?.error || 'Upload failed')
      setStatus('error')
    }
  }

  return (
    <div className="upload-zone-card" style={{ '--zone-color': source.color }}>
      <div className="upload-zone-header">
        <div>
          <div className="zone-scope" style={{ color: source.color }}>{source.scope}</div>
          <h3 className="zone-title">{source.label}</h3>
          <p className="zone-desc">{source.desc}</p>
        </div>
      </div>

      <div
        className={`drop-area ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={source.accept}
          style={{ display: 'none' }}
          onChange={e => e.target.files[0] && handleFile(e.target.files[0])}
        />
        {file ? (
          <div className="file-selected">
            <FileText size={18} color={source.color} />
            <span>{file.name}</span>
            <span className="file-size">({(file.size / 1024).toFixed(0)} KB)</span>
          </div>
        ) : (
          <div className="drop-prompt">
            <Upload size={20} color="var(--text-dim)" />
            <span>Drop file here or click to browse</span>
            <span className="accepted">{source.accept}</span>
          </div>
        )}
      </div>

      {status === 'done' && result && (
        <div className="upload-result success">
          <CheckCircle size={14} />
          <span>Ingested {result.row_count} records, {result.error_count} parse errors</span>
        </div>
      )}

      {status === 'error' && (
        <div className="upload-result error">
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      <button
        className="upload-btn"
        onClick={doUpload}
        disabled={!file || status === 'uploading'}
        style={{ '--btn-color': source.color }}
      >
        {status === 'uploading' ? 'Processing…' : 'Upload & Ingest'}
      </button>
    </div>
  )
}

export default function UploadPage() {
  return (
    <div className="upload-page fade-in">
      <div className="page-header">
        <h1 className="page-title">Upload Data</h1>
        <p className="page-desc">
          Upload emission source files. Each file is parsed, normalized, and queued for analyst review.
          Original files are preserved for audit traceability.
        </p>
      </div>

      <div className="upload-grid">
        {SOURCES.map(s => <UploadZone key={s.key} source={s} />)}
      </div>

      <div className="sample-note">
        <h3>Sample file formats</h3>
        <div className="samples-grid">
          <div className="sample-block">
            <div className="sample-label">SAP (MB51 export)</div>
            <pre>{`Belnr;Bldat;Werks;Kostl;Maktx;Menge;Meins
5000012301;15.01.2024;IN01;CC-PROD;High Speed Diesel;12500;L`}</pre>
          </div>
          <div className="sample-block">
            <div className="sample-label">Utility portal CSV</div>
            <pre>{`Meter ID,Billing Period Start,Consumption,Unit
MTR-BLR-001,01/01/2024,48500,kWh`}</pre>
          </div>
          <div className="sample-block">
            <div className="sample-label">Navan / Concur travel export</div>
            <pre>{`Trip Date,Traveler,Travel Type,Origin,Destination,Class
2024-01-10,EMP001,Flight,DEL,BLR,economy`}</pre>
          </div>
        </div>
      </div>
    </div>
  )
}
