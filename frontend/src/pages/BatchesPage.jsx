import { useState, useEffect } from 'react'
import { batches as batchApi } from '../services/api'
import { Layers, CheckCircle, AlertCircle, Clock, Lock } from 'lucide-react'

const SOURCE_LABELS = {
  sap: { label: 'SAP Fuel & Procurement', color: 'var(--scope1)', scope: 'Scope 1' },
  utility: { label: 'Utility Electricity', color: 'var(--scope2)', scope: 'Scope 2' },
  travel: { label: 'Corporate Travel', color: 'var(--scope3)', scope: 'Scope 3' },
}

const STATUS_ICON = {
  done: <CheckCircle size={14} color="var(--accent)" />,
  failed: <AlertCircle size={14} color="var(--red)" />,
  processing: <Clock size={14} color="var(--amber)" />,
}

function fmt(d) {
  return new Date(d).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function BatchesPage() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [locking, setLocking] = useState(null)
  const [lockMsg, setLockMsg] = useState({})

  const load = () => {
    setLoading(true)
    batchApi.list().then(r => setData(r.data.results || r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleLock = async (id) => {
    setLocking(id)
    try {
      const r = await batchApi.lock(id)
      setLockMsg(m => ({ ...m, [id]: `Locked ${r.data.locked_count} records for audit.` }))
      load()
    } catch {
      setLockMsg(m => ({ ...m, [id]: 'Lock failed — ensure all records are approved first.' }))
    } finally {
      setLocking(null)
    }
  }

  return (
    <div style={{ padding: '28px 32px' }} className="fade-in">
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }}>
          Ingestion Batches
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
          Every file upload and its processing result. Lock approved batches to make them audit-immutable.
        </p>
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)' }}>Loading batches…</p>
      ) : data.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)',
          background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border)'
        }}>
          <Layers size={32} strokeWidth={1} style={{ marginBottom: '12px', opacity: 0.4 }} />
          <p>No batches yet. Upload a file to get started.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {data.map(batch => {
            const src = SOURCE_LABELS[batch.source_type] || {}
            return (
              <div key={batch.id} style={{
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: '12px', padding: '20px 24px',
                borderLeft: `3px solid ${src.color || 'var(--border)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                      <span style={{
                        fontSize: '11px', fontWeight: 500, color: src.color,
                        background: src.color + '22', padding: '2px 8px', borderRadius: '4px'
                      }}>{src.scope}</span>
                      <span style={{ fontWeight: 500, color: 'var(--text)' }}>{src.label}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)', fontSize: '12px' }}>
                        {STATUS_ICON[batch.status]}
                        {batch.status}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      {batch.original_filename || 'Unnamed file'} · uploaded by <strong>{batch.uploaded_by_name}</strong> · {fmt(batch.uploaded_at)}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      <span style={{ color: 'var(--accent)' }}>{batch.row_count} records ingested</span>
                      {batch.error_count > 0 && (
                        <span style={{ color: 'var(--red)', marginLeft: '12px' }}>
                          {batch.error_count} parse errors
                        </span>
                      )}
                    </div>
                    {lockMsg[batch.id] && (
                      <div style={{ fontSize: '12px', color: 'var(--accent)', marginTop: '6px' }}>
                        {lockMsg[batch.id]}
                      </div>
                    )}
                  </div>

                  {batch.status === 'done' && (
                    <button
                      onClick={() => handleLock(batch.id)}
                      disabled={locking === batch.id}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: '8px 16px', borderRadius: '8px',
                        background: 'var(--blue-dim)', color: 'var(--blue)',
                        border: '1px solid var(--blue)', fontSize: '12px',
                        fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap',
                        opacity: locking === batch.id ? 0.5 : 1,
                      }}
                    >
                      <Lock size={12} />
                      {locking === batch.id ? 'Locking…' : 'Lock approved records'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
