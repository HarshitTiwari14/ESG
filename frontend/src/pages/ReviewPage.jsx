import { useState, useEffect, useCallback } from 'react'
import { records } from '../services/api'
import { CheckCircle, Flag, X, ChevronDown, ChevronUp, Eye, RefreshCw } from 'lucide-react'
import './ReviewPage.css'

const STATUS_CONFIG = {
  pending: { label: 'Pending', color: 'var(--text-muted)', bg: 'var(--bg-elevated)' },
  flagged: { label: 'Flagged', color: 'var(--amber)', bg: 'var(--amber-dim)' },
  approved: { label: 'Approved', color: 'var(--accent)', bg: 'var(--accent-dim)' },
  locked: { label: 'Locked', color: 'var(--blue)', bg: 'var(--blue-dim)' },
}

const SCOPE_LABELS = { 1: 'S1', 2: 'S2', 3: 'S3' }
const SCOPE_COLORS = { 1: 'var(--scope1)', 2: 'var(--scope2)', 3: 'var(--scope3)' }

function fmt(n) {
  const v = parseFloat(n)
  if (v >= 1000) return `${(v/1000).toFixed(2)}t`
  return `${v.toFixed(1)} kg`
}

function Badge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending
  return (
    <span className="badge" style={{ color: cfg.color, background: cfg.bg }}>
      {cfg.label}
    </span>
  )
}

function RecordRow({ record, onRefresh }) {
  const [expanded, setExpanded] = useState(false)
  const [flagModal, setFlagModal] = useState(false)
  const [flagReason, setFlagReason] = useState('')
  const [loading, setLoading] = useState(false)

  const doApprove = async () => {
    setLoading(true)
    try {
      await records.approve(record.id)
      onRefresh()
    } finally { setLoading(false) }
  }

  const doFlag = async () => {
    setLoading(true)
    try {
      await records.flag(record.id, flagReason)
      setFlagModal(false)
      setFlagReason('')
      onRefresh()
    } finally { setLoading(false) }
  }

  const doUnflag = async () => {
    setLoading(true)
    try {
      await records.unflag(record.id)
      onRefresh()
    } finally { setLoading(false) }
  }

  const locked = record.status === 'locked'

  return (
    <>
      <tr className={`record-row ${expanded ? 'expanded' : ''}`} onClick={() => setExpanded(e => !e)}>
        <td>
          <span className="scope-badge" style={{ color: SCOPE_COLORS[record.scope] }}>
            {SCOPE_LABELS[record.scope]}
          </span>
        </td>
        <td className="cat-cell">{record.category?.replace(/_/g, ' ')}</td>
        <td className="date-cell">{record.activity_date}</td>
        <td>{record.location || record.description || '—'}</td>
        <td className="mono-cell">{fmt(record.co2e_kg)} CO₂e</td>
        <td><Badge status={record.status} /></td>
        <td onClick={e => e.stopPropagation()}>
          {!locked && (
            <div className="action-btns">
              {record.status !== 'approved' && (
                <button className="btn-approve" onClick={doApprove} disabled={loading} title="Approve">
                  <CheckCircle size={14} />
                </button>
              )}
              {record.status !== 'flagged' ? (
                <button className="btn-flag" onClick={() => setFlagModal(true)} disabled={loading} title="Flag">
                  <Flag size={14} />
                </button>
              ) : (
                <button className="btn-unflag" onClick={doUnflag} disabled={loading} title="Unflag">
                  <X size={14} />
                </button>
              )}
            </div>
          )}
        </td>
        <td>
          {expanded ? <ChevronUp size={14} color="var(--text-dim)" /> : <ChevronDown size={14} color="var(--text-dim)" />}
        </td>
      </tr>

      {expanded && (
        <tr className="detail-row">
          <td colSpan={8}>
            <div className="detail-panel slide-in">
              <div className="detail-grid">
                <DetailItem label="Raw Value" value={`${record.activity_value_raw} ${record.activity_unit_raw}`} />
                <DetailItem label="Normalized" value={`${record.activity_value_norm} ${record.activity_unit_norm}`} />
                <DetailItem label="Emission Factor" value={`${record.emission_factor} kgCO₂e / unit`} />
                <DetailItem label="Factor Version" value={record.factor_version} />
                {record.batch_source === 'sap' && <>
                  <DetailItem label="SAP Doc #" value={record.sap_document_number} />
                  <DetailItem label="Plant Code" value={record.sap_plant_code} />
                  <DetailItem label="Cost Center" value={record.sap_cost_center} />
                  <DetailItem label="Vendor" value={record.vendor} />
                </>}
                {record.batch_source === 'utility' && <>
                  <DetailItem label="Meter ID" value={record.utility_meter_id} />
                  <DetailItem label="Tariff" value={record.utility_tariff} />
                  <DetailItem label="Period End" value={record.activity_period_end} />
                </>}
                {record.batch_source === 'travel' && <>
                  <DetailItem label="Route" value={record.travel_origin && `${record.travel_origin} → ${record.travel_destination}`} />
                  <DetailItem label="Class" value={record.travel_class} />
                  <DetailItem label="Distance" value={record.travel_distance_km && `${record.travel_distance_km} km`} />
                  <DetailItem label="Traveler" value={record.travel_traveler_id} />
                </>}
              </div>

              {record.flag_reason && (
                <div className="flag-note">
                  <Flag size={12} /> {record.flag_reason}
                </div>
              )}

              {record.audit_logs?.length > 0 && (
                <div className="audit-trail">
                  <div className="audit-title">Audit Trail</div>
                  {record.audit_logs.map(log => (
                    <div key={log.id} className="audit-entry">
                      <span className="audit-action">{log.action}</span>
                      <span className="audit-actor">{log.actor_name || 'system'}</span>
                      <span className="audit-time">{new Date(log.timestamp).toLocaleString()}</span>
                      {log.note && <span className="audit-note">{log.note}</span>}
                    </div>
                  ))}
                </div>
              )}

              {record.raw_data && (
                <details className="raw-data">
                  <summary>Raw source data</summary>
                  <pre>{JSON.stringify(record.raw_data, null, 2)}</pre>
                </details>
              )}
            </div>
          </td>
        </tr>
      )}

      {flagModal && (
        <tr>
          <td colSpan={8}>
            <div className="flag-modal" onClick={e => e.stopPropagation()}>
              <input
                className="flag-input"
                placeholder="Reason for flagging (required)"
                value={flagReason}
                onChange={e => setFlagReason(e.target.value)}
                autoFocus
              />
              <button className="btn-flag-confirm" onClick={doFlag} disabled={!flagReason.trim() || loading}>
                Confirm Flag
              </button>
              <button className="btn-cancel" onClick={() => setFlagModal(false)}>Cancel</button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function DetailItem({ label, value }) {
  if (!value) return null
  return (
    <div className="detail-item">
      <div className="detail-label">{label}</div>
      <div className="detail-value">{value}</div>
    </div>
  )
}

export default function ReviewPage() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ status: '', scope: '', search: '' })
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const PAGE_SIZE = 50

  const load = useCallback(() => {
    setLoading(true)
    const params = { page }
    if (filters.status) params.status = filters.status
    if (filters.scope) params.scope = filters.scope
    if (filters.search) params.search = filters.search
    records.list(params)
      .then(r => {
        setData(r.data.results || r.data)
        setTotal(r.data.count || r.data.length)
      })
      .finally(() => setLoading(false))
  }, [filters, page])

  useEffect(() => { load() }, [load])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="review-page fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Review Queue</h1>
          <p className="page-desc">{total} records — approve, flag, or inspect before locking for audit</p>
        </div>
        <button className="btn-refresh" onClick={load}><RefreshCw size={14} /></button>
      </div>

      <div className="filter-bar">
        <select
          className="filter-select"
          value={filters.status}
          onChange={e => { setFilters(f => ({ ...f, status: e.target.value })); setPage(1) }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="flagged">Flagged</option>
          <option value="approved">Approved</option>
          <option value="locked">Locked</option>
        </select>

        <select
          className="filter-select"
          value={filters.scope}
          onChange={e => { setFilters(f => ({ ...f, scope: e.target.value })); setPage(1) }}
        >
          <option value="">All scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>

        <input
          className="filter-search"
          placeholder="Search description, vendor, location…"
          value={filters.search}
          onChange={e => { setFilters(f => ({ ...f, search: e.target.value })); setPage(1) }}
        />
      </div>

      <div className="table-wrap">
        {loading ? (
          <div className="table-loading">Loading records…</div>
        ) : (
          <table className="records-table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Category</th>
                <th>Date</th>
                <th>Location / Description</th>
                <th>CO₂e</th>
                <th>Status</th>
                <th>Actions</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr><td colSpan={8} className="empty-state">No records match your filters.</td></tr>
              ) : (
                data.map(r => <RecordRow key={r.id} record={r} onRefresh={load} />)
              )}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  )
}
