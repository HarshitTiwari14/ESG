import { useState, useEffect } from 'react'
import { dashboard } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts'
import { TrendingUp, AlertTriangle, CheckCircle, Lock } from 'lucide-react'
import './DashboardPage.css'

const SCOPE_COLORS = { scope_1: '#fb923c', scope_2: '#60a5fa', scope_3: '#a78bfa' }
const CAT_COLOR = '#4ade80'

function fmt(n) {
  if (n >= 1_000_000) return `${(n/1_000_000).toFixed(1)}t CO₂e`
  if (n >= 1000) return `${(n/1000).toFixed(1)}t CO₂e`
  return `${n.toFixed(0)} kg CO₂e`
}

function StatCard({ label, value, sub, color, icon: Icon }) {
  return (
    <div className="stat-card" style={{ '--accent-c': color }}>
      <div className="stat-icon"><Icon size={18} strokeWidth={1.5} /></div>
      <div className="stat-body">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  )
}

function ScopeBar({ scope, data }) {
  const total = Object.values(data).reduce((s, d) => s + d.total_co2e_kg, 0)
  const val = data[scope]?.total_co2e_kg || 0
  const pct = total > 0 ? (val / total * 100).toFixed(1) : 0
  const labels = { scope_1: 'Scope 1 — Direct', scope_2: 'Scope 2 — Electricity', scope_3: 'Scope 3 — Travel' }
  const color = SCOPE_COLORS[scope]
  return (
    <div className="scope-bar-row">
      <div className="scope-bar-label">{labels[scope]}</div>
      <div className="scope-bar-track">
        <div className="scope-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="scope-bar-val" style={{ color }}>{fmt(val)}</div>
      <div className="scope-bar-pct">{pct}%</div>
    </div>
  )
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    dashboard.stats().then(r => setStats(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page-loading">Loading dashboard…</div>
  if (!stats) return <div className="page-loading">No data yet. Upload some files!</div>

  const { scope_totals, review_counts, category_breakdown, total_co2e_kg } = stats

  const catChartData = (category_breakdown || []).map(d => ({
    name: d.category.replace(/_/g, ' '),
    value: parseFloat(d.total_co2e),
    count: d.count,
  }))

  return (
    <div className="dashboard-page fade-in">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-desc">Emissions overview — all scopes, current reporting period</p>
      </div>

      <div className="kpi-row">
        <StatCard
          label="Total Emissions"
          value={fmt(total_co2e_kg)}
          sub="All scopes combined"
          color="var(--accent)"
          icon={TrendingUp}
        />
        <StatCard
          label="Pending Review"
          value={review_counts.pending + review_counts.flagged}
          sub={`${review_counts.flagged} flagged`}
          color="var(--amber)"
          icon={AlertTriangle}
        />
        <StatCard
          label="Approved"
          value={review_counts.approved}
          sub="Ready for audit"
          color="var(--blue)"
          icon={CheckCircle}
        />
        <StatCard
          label="Locked"
          value={review_counts.locked}
          sub="Audit-immutable"
          color="var(--scope3)"
          icon={Lock}
        />
      </div>

      <div className="chart-grid">
        <div className="card">
          <h2 className="card-title">Scope Breakdown</h2>
          <div className="scope-bars">
            {['scope_1', 'scope_2', 'scope_3'].map(s => (
              <ScopeBar key={s} scope={s} data={scope_totals} />
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="card-title">By Category</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={catChartData} margin={{ top: 4, right: 4, bottom: 20, left: 4 }}>
              <XAxis
                dataKey="name"
                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                angle={-30}
                textAnchor="end"
                interval={0}
              />
              <YAxis hide />
              <Tooltip
                contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                formatter={(v) => [fmt(v), 'CO₂e']}
                labelStyle={{ color: 'var(--text)', fontWeight: 500 }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {catChartData.map((_, i) => (
                  <Cell key={i} fill={CAT_COLOR} fillOpacity={0.7 + (i % 3) * 0.1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Scope Distribution</h2>
        <div className="scope-pie-row">
          <ResponsiveContainer width={200} height={180}>
            <PieChart>
              <Pie
                data={[
                  { name: 'Scope 1', value: scope_totals.scope_1?.total_co2e_kg || 0 },
                  { name: 'Scope 2', value: scope_totals.scope_2?.total_co2e_kg || 0 },
                  { name: 'Scope 3', value: scope_totals.scope_3?.total_co2e_kg || 0 },
                ]}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                strokeWidth={0}
              >
                <Cell fill="#fb923c" />
                <Cell fill="#60a5fa" />
                <Cell fill="#a78bfa" />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="scope-legend">
            {[
              { key: 'scope_1', label: 'Scope 1', desc: 'Direct fuel combustion', color: '#fb923c' },
              { key: 'scope_2', label: 'Scope 2', desc: 'Purchased electricity', color: '#60a5fa' },
              { key: 'scope_3', label: 'Scope 3', desc: 'Business travel', color: '#a78bfa' },
            ].map(s => (
              <div key={s.key} className="legend-item">
                <div className="legend-dot" style={{ background: s.color }} />
                <div>
                  <div className="legend-label">{s.label}</div>
                  <div className="legend-desc">{s.desc}</div>
                  <div className="legend-val" style={{ color: s.color }}>
                    {fmt(scope_totals[s.key]?.total_co2e_kg || 0)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
