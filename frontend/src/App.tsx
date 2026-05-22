import { useState, useCallback } from 'react'
import { useApi, apiPost } from './hooks/useApi'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { AlertTriangle, CheckCircle, Clock, Play, RefreshCw, Zap, TrendingUp, Shield } from 'lucide-react'

type Tab = 'dashboard' | 'tickets' | 'escalations' | 'knowledge'

interface DashboardData {
  total_tickets: number; open_tickets: number; escalated: number; auto_resolved: number;
  resolved: number; high_risk_open: number; auto_resolve_rate: number; escalation_rate: number;
  engineering_time_pct: number; avg_resolution_hours: number;
  by_category: Record<string, number>; by_system: Record<string, number>; by_severity: Record<string, number>;
}

interface TicketItem {
  id: number; ticket_id: string; title: string; biller_name: string; status: string;
  category: string | null; severity: string | null; affected_system: string | null;
  escalation_probability: number; escalation_risk: string | null; will_need_engineering: boolean;
  created_at: string;
}

interface EscalationItem extends TicketItem {
  factors: Array<{ factor: string; value: string; impact: number }>;
  predicted_resolution_hours: number;
}

interface KBItem {
  id: number; pattern_name: string; category: string; trigger_keywords: string[];
  resolution_steps: string; auto_resolvable: boolean; success_rate: number; times_used: number;
}

const COLORS = ['#3b82f6', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6', '#06b6d4', '#f97316', '#6366f1']

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [refreshKey, setRefreshKey] = useState(0)
  const [pipelineRunning, setPipelineRunning] = useState(false)

  const { data: dashboard } = useApi<DashboardData>('/predictions/dashboard', [refreshKey])
  const { data: tickets } = useApi<TicketItem[]>('/tickets?limit=100', [refreshKey])
  const { data: escalations } = useApi<EscalationItem[]>('/predictions/escalation?limit=50', [refreshKey])
  const { data: kb } = useApi<KBItem[]>('/knowledge-base', [refreshKey])

  const runPipeline = useCallback(async () => {
    setPipelineRunning(true)
    try { await apiPost('/agents/run-pipeline'); setRefreshKey(k => k + 1) }
    catch (e) { console.error(e) }
    finally { setPipelineRunning(false) }
  }, [])

  const sevColors: Record<string, string> = { critical: 'bg-red-100 text-red-800', high: 'bg-orange-100 text-orange-800', medium: 'bg-yellow-100 text-yellow-800', low: 'bg-blue-100 text-blue-800' }
  const riskColors: Record<string, string> = { high: 'text-red-600', medium: 'text-yellow-600', low: 'text-green-600' }

  const catData = dashboard ? Object.entries(dashboard.by_category).map(([k, v]) => ({ name: k.replace(/_/g, ' '), value: v })) : []
  const sevData = dashboard ? Object.entries(dashboard.by_severity).map(([k, v]) => ({ name: k, value: v })) : []

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-purple-600 p-2 rounded-lg"><Shield className="w-6 h-6 text-white" /></div>
              <div>
                <h1 className="text-xl font-bold">SupportIQ Insights</h1>
                <p className="text-sm text-gray-500">Escalation Predictor & Auto-Resolver</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setRefreshKey(k => k + 1)} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg"><RefreshCw className="w-5 h-5" /></button>
              <button onClick={runPipeline} disabled={pipelineRunning} className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 flex items-center gap-2 disabled:opacity-50">
                <Play className="w-4 h-4" />{pipelineRunning ? 'Running...' : 'Run Pipeline'}
              </button>
            </div>
          </div>
          <nav className="flex gap-1 mt-4 -mb-px">
            {([
              { id: 'dashboard' as Tab, label: 'Dashboard' },
              { id: 'tickets' as Tab, label: 'Tickets' },
              { id: 'escalations' as Tab, label: 'Escalation Queue' },
              { id: 'knowledge' as Tab, label: 'Knowledge Base' },
            ]).map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg ${tab === t.id ? 'bg-gray-50 text-purple-600 border-b-2 border-purple-600' : 'text-gray-500 hover:text-gray-700'}`}>
                {t.label}
                {t.id === 'escalations' && dashboard && dashboard.high_risk_open > 0 && (
                  <span className="ml-2 bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full text-xs">{dashboard.high_risk_open}</span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {tab === 'dashboard' && dashboard && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Open Tickets', value: dashboard.open_tickets, icon: Clock, color: 'text-blue-600' },
                { label: 'High Risk', value: dashboard.high_risk_open, icon: AlertTriangle, color: 'text-red-600' },
                { label: 'Auto-Resolved', value: dashboard.auto_resolved, icon: Zap, color: 'text-green-600' },
                { label: 'Escalated', value: dashboard.escalated, icon: TrendingUp, color: 'text-orange-600' },
              ].map(card => (
                <div key={card.label} className="bg-white rounded-lg shadow-sm border p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-gray-500">{card.label}</p>
                    <card.icon className={`w-5 h-5 ${card.color}`} />
                  </div>
                  <p className="text-2xl font-bold mt-1">{card.value}</p>
                </div>
              ))}
            </div>

            {/* Rates */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-lg shadow-sm border p-4 text-center">
                <p className="text-sm text-gray-500">Auto-Resolve Rate</p>
                <p className="text-3xl font-bold text-green-600">{dashboard.auto_resolve_rate}%</p>
              </div>
              <div className="bg-white rounded-lg shadow-sm border p-4 text-center">
                <p className="text-sm text-gray-500">Escalation Rate</p>
                <p className="text-3xl font-bold text-orange-600">{dashboard.escalation_rate}%</p>
              </div>
              <div className="bg-white rounded-lg shadow-sm border p-4 text-center">
                <p className="text-sm text-gray-500">Eng. Time (target: 10%)</p>
                <p className={`text-3xl font-bold ${dashboard.engineering_time_pct > 10 ? 'text-red-600' : 'text-green-600'}`}>{dashboard.engineering_time_pct}%</p>
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg shadow-sm border p-5">
                <h3 className="text-lg font-semibold mb-3">Tickets by Category</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={catData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis /><Tooltip /><Bar dataKey="value" fill="#8b5cf6" /></BarChart>
                </ResponsiveContainer>
              </div>
              <div className="bg-white rounded-lg shadow-sm border p-5">
                <h3 className="text-lg font-semibold mb-3">By Severity</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart><Pie data={sevData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label>{sevData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /></PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        )}

        {tab === 'tickets' && (
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="px-5 py-4 border-b"><h3 className="text-lg font-semibold">All Tickets</h3></div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50"><tr>
                  <th className="px-4 py-3 text-left">ID</th><th className="px-4 py-3 text-left">Title</th>
                  <th className="px-4 py-3 text-left">Biller</th><th className="px-4 py-3 text-left">Category</th>
                  <th className="px-4 py-3 text-left">Severity</th><th className="px-4 py-3 text-left">Risk</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr></thead>
                <tbody className="divide-y">
                  {(tickets || []).map(t => (
                    <tr key={t.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs">{t.ticket_id}</td>
                      <td className="px-4 py-3 max-w-xs truncate">{t.title}</td>
                      <td className="px-4 py-3 text-xs">{t.biller_name}</td>
                      <td className="px-4 py-3 text-xs">{t.category?.replace(/_/g, ' ') || '-'}</td>
                      <td className="px-4 py-3">{t.severity && <span className={`px-2 py-0.5 rounded-full text-xs ${sevColors[t.severity] || ''}`}>{t.severity}</span>}</td>
                      <td className="px-4 py-3">{t.escalation_risk && <span className={`text-xs font-medium ${riskColors[t.escalation_risk] || ''}`}>{(t.escalation_probability * 100).toFixed(0)}%</span>}</td>
                      <td className="px-4 py-3 text-xs">{t.status.replace(/_/g, ' ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === 'escalations' && (
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">Escalation Risk Queue</h3>
            {(escalations || []).map(e => (
              <div key={e.id} className="bg-white rounded-lg shadow-sm border p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className={`text-lg font-bold ${riskColors[e.escalation_risk || 'low']}`}>{(e.escalation_probability * 100).toFixed(0)}%</span>
                    <div>
                      <p className="font-medium">{e.title}</p>
                      <p className="text-sm text-gray-500">{e.ticket_id} — {e.biller_name}</p>
                    </div>
                  </div>
                  <div className="text-right text-sm">
                    {e.severity && <span className={`px-2 py-0.5 rounded-full text-xs ${sevColors[e.severity] || ''}`}>{e.severity}</span>}
                    <p className="text-xs text-gray-400 mt-1">Est. {e.predicted_resolution_hours}h to resolve</p>
                  </div>
                </div>
                {e.factors && e.factors.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {e.factors.map((f, i) => (
                      <span key={i} className="text-xs bg-gray-100 px-2 py-1 rounded">{f.factor}: {f.value}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {(!escalations || escalations.length === 0) && <p className="text-gray-400 text-center py-8">No escalation predictions — run the pipeline first</p>}
          </div>
        )}

        {tab === 'knowledge' && (
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">Resolution Pattern Knowledge Base</h3>
            {(kb || []).map(p => (
              <div key={p.id} className="bg-white rounded-lg shadow-sm border p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {p.auto_resolvable ? <Zap className="w-4 h-4 text-green-500" /> : <CheckCircle className="w-4 h-4 text-gray-400" />}
                    <span className="font-medium">{p.pattern_name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{(p.success_rate * 100).toFixed(0)}% success</span>
                    <span>{p.times_used} uses</span>
                    {p.auto_resolvable && <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded">Auto</span>}
                  </div>
                </div>
                <p className="text-xs text-gray-500 mb-2">{p.category.replace(/_/g, ' ')}</p>
                <div className="flex flex-wrap gap-1 mb-2">
                  {p.trigger_keywords.map(kw => <span key={kw} className="text-xs bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded">{kw}</span>)}
                </div>
                <pre className="text-xs bg-gray-50 p-3 rounded whitespace-pre-wrap">{p.resolution_steps}</pre>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="border-t mt-12 py-4 text-center text-xs text-gray-400">
        SupportIQ Insights v1.0.0 — InvoiceCloud Q3 Hackathon | Reducing engineering escalation from 13% toward 10%
      </footer>
    </div>
  )
}
