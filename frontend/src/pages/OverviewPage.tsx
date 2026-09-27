import { useEffect, useState } from 'react'
import { Activity, ArrowRight, BriefcaseBusiness, Clock3, FileWarning, Flag, MessageSquareText, Users, Waypoints } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api'
import { EmptyState, ErrorState, formatDate, LoadingRows, PageHeader, StatusPill } from '../components/ui'
import type { ActivityItem, AttentionItem, DashboardOverview, Pipeline } from '../types'

const stages: Array<{ key: keyof Pipeline; label: string; color: string }> = [
  { key: 'preparing', label: 'Preparing', color: 'var(--stage-preparing)' },
  { key: 'ready', label: 'Ready', color: 'var(--stage-ready)' },
  { key: 'submitted', label: 'Submitted', color: 'var(--stage-submitted)' },
  { key: 'under_review', label: 'Under review', color: 'var(--stage-review)' },
  { key: 'offer_received', label: 'Offer received', color: 'var(--stage-offer)' },
  { key: 'rejected', label: 'Rejected', color: 'var(--stage-rejected)' },
  { key: 'withdrawn', label: 'Withdrawn', color: 'var(--stage-withdrawn)' },
]

function attentionPath(item: AttentionItem) {
  if (item.type === 'escalation') return '/staff/escalations'
  if (item.type === 'overdue_task') return '/staff/tasks'
  if (item.type === 'pending_followup') return '/staff/follow-ups'
  if (item.type === 'document_problem') return '/staff/documents'
  return item.lead_id ? `/staff/students/${item.lead_id}` : '/staff/applications'
}

function attentionLabel(type: string) {
  const labels: Record<string, string> = {
    escalation: 'HUMAN HANDOFF',
    overdue_task: 'OVERDUE TASK',
    document_problem: 'DOCUMENT PROBLEM',
    pending_followup: 'AWAITING APPROVAL',
    application_readiness: 'APPLICATION BLOCKED',
  }
  return labels[type] ?? type.replaceAll('_', ' ').toUpperCase()
}

function activityTitle(item: ActivityItem) {
  return item.action.replaceAll('_', ' ')
}

export function OverviewPage() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [attention, setAttention] = useState<AttentionItem[]>([])
  const [activity, setActivity] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.dashboard.overview(7), api.dashboard.pipeline(), api.dashboard.attention(8), api.dashboard.activity(7)])
      .then(([summary, stagesResponse, attentionResponse, activityResponse]) => {
        if (!active) return
        setOverview(summary)
        setPipeline(stagesResponse.pipeline)
        setAttention(attentionResponse.items)
        setActivity(activityResponse.activity)
        setError('')
      })
      .catch((reason: unknown) => { if (active) setError(errorMessage(reason)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [refreshKey])

  const metrics = overview ? [
    { label: 'Total leads', value: overview.total_leads, note: 'Student profiles', icon: Users, tone: 'blue' },
    { label: 'Active applications', value: overview.active_applications, note: `${overview.total_applications} total cases`, icon: BriefcaseBusiness, tone: 'cyan' },
    { label: 'Offers received', value: overview.offers_received, note: 'Recorded by staff', icon: Flag, tone: 'green' },
    { label: 'Document problems', value: overview.document_problems, note: 'Latest checks only', icon: FileWarning, tone: 'amber' },
    { label: 'Pending follow-ups', value: overview.pending_followups, note: 'Awaiting approval', icon: MessageSquareText, tone: 'violet' },
    { label: 'Open escalations', value: overview.open_escalations, note: 'Open or in progress', icon: Waypoints, tone: 'blue' },
    { label: 'Overdue tasks', value: overview.overdue_tasks, note: 'Pending past due date', icon: Clock3, tone: 'red' },
    { label: 'Needs attention', value: overview.applications_needing_attention, note: 'Unique applications', icon: Activity, tone: 'amber' },
  ] : []
  const maxStage = Math.max(1, ...(pipeline ? Object.values(pipeline) : [0]))

  return (
    <div className="page-stack">
      <PageHeader eyebrow="OPERATIONS · LIVE SNAPSHOT" title="Overview" description="A clear read on student momentum and the work that needs a human next." action={<span className="refresh-stamp"><span className="online-dot" /> Live from AdmitCrew data</span>} />
      {error && <ErrorState message={error} onRetry={() => setRefreshKey((value) => value + 1)} />}
      {loading && !overview ? <LoadingRows rows={4} /> : <>
        <section className="metric-grid" aria-label="Overview metrics">
          {metrics.map(({ label, value, note, icon: Icon, tone }) => <article className={`metric-card metric-${tone}`} key={label}><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={17} /></span></div><strong className="metric-value">{value.toLocaleString()}</strong><small>{note}</small></article>)}
        </section>
        <div className="overview-grid">
          <section className="panel pipeline-panel">
            <div className="panel-heading"><div><span className="eyebrow">CASE FLOW</span><h2>Application pipeline</h2></div><Link to="/staff/applications" className="text-link">All applications <ArrowRight size={14} /></Link></div>
            <div className="pipeline-bars">
              {stages.map((stage) => {
                const count = pipeline?.[stage.key] ?? 0
                return <div className="pipeline-row" key={stage.key}><div className="pipeline-label"><span>{stage.label}</span><strong>{count}</strong></div><div className="pipeline-track"><span style={{ width: `${Math.max(count ? 5 : 0, (count / maxStage) * 100)}%`, background: stage.color }} /></div></div>
              })}
            </div>
          </section>
          <section className="panel attention-panel">
            <div className="panel-heading"><div><span className="eyebrow">STAFF QUEUE</span><h2>Needs attention</h2></div><Link to="/staff/escalations" className="text-link">Open queue <ArrowRight size={14} /></Link></div>
            {loading && !overview ? <LoadingRows rows={4} /> : attention.length ? <div className="attention-list">{attention.slice(0, 6).map((item) => <Link key={`${item.type}-${item.source_record_id}`} to={attentionPath(item)} className={`attention-item attention-${item.severity}`}><span className="attention-marker" /><span className="attention-copy"><span className="attention-label">{attentionLabel(item.type)}{item.student_name ? ` · ${item.student_name}` : ''}</span><strong>{item.title}</strong><small>{item.description || 'Review the source record.'}</small></span><span className="attention-time">{formatDate(item.due_at ?? item.created_at)}</span></Link>)}</div> : <EmptyState title="Nothing needs attention" description="No unresolved items are in the staff queue right now." />}
          </section>
        </div>
        <section className="panel activity-panel">
          <div className="panel-heading"><div><span className="eyebrow">AUDIT TRAIL</span><h2>Recent activity</h2></div><Link to="/staff/activity" className="text-link">View activity <ArrowRight size={14} /></Link></div>
          {activity.length ? <div className="activity-list">{activity.slice(0, 6).map((item) => <div className="activity-row" key={`${item.agent}-${item.id}`}><span className="activity-icon"><Activity size={15} /></span><span className="activity-copy"><strong>{activityTitle(item)}</strong><small>{item.agent.replaceAll('_', ' ')}{item.details ? ` · ${item.details}` : ''}</small></span><time>{formatDate(item.created_at, true)}</time></div>)}</div> : <EmptyState title="No recent activity" description="Meaningful staff and agent actions will appear here." />}
        </section>
        <div className="overview-bottomline"><span>AI supports the workflow. Staff remains in control.</span><StatusPill value="verified source data" compact /></div>
      </>}
    </div>
  )
}
