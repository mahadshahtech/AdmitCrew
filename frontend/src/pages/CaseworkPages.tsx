import { Children, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Activity, ArrowRight, ArrowUpRight, BriefcaseBusiness, Check, CheckCircle2, CircleUserRound, Clock3, FileCheck2, FileWarning, MessageSquareText, Plus, Search, Send, ShieldCheck, UserRoundPlus, X } from 'lucide-react'
import { api, ApiError, errorMessage } from '../api'
import { EmptyState, ErrorState, formatDate, initials, LoadingRows, PageHeader, Panel, StatusPill, useToast } from '../components/ui'
import type { ActivityItem, Application, ApplicationStatus, DocumentRecord, Escalation, Followup, Lead, Program, StaffProfile, StudentCase, Task } from '../types'

function SearchBox({ value, onChange, placeholder = 'Search records' }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return <label className="search-box"><Search size={16} /><span className="sr-only">{placeholder}</span><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>
}

function RowLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link to={to} className="row-link">{children}<ArrowUpRight size={14} /></Link>
}

export function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    const timer = window.setTimeout(() => {
      api.leads.list(search)
        .then((response) => { if (active) { setLeads(response.leads); setError('') } })
        .catch((reason: unknown) => { if (active) setError(errorMessage(reason)) })
        .finally(() => { if (active) setLoading(false) })
    }, 160)
    return () => { active = false; window.clearTimeout(timer) }
  }, [search, revision])

  return <div className="page-stack">
    <PageHeader eyebrow="STUDENT RELATIONSHIPS" title="Leads" description="Student profiles and the next conversation to have." action={<span className="count-chip"><UsersIcon /> {leads.length} shown</span>} />
    <Panel className="table-panel">
      <div className="table-toolbar"><SearchBox value={search} onChange={setSearch} placeholder="Search name, phone, or country" /><span className="table-caption">Sorted by student name</span></div>
      {error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}
      {loading ? <LoadingRows /> : leads.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Student</th><th>Phone</th><th>Preferred country</th><th>Marks</th><th>IELTS</th><th>Last reply</th><th /></tr></thead><tbody>{leads.map((lead) => <tr key={lead.id}><td><Link className="student-cell" to={`/staff/students/${lead.id}`}><span className="student-avatar">{initials(lead.name)}</span><span><strong>{lead.name}</strong><small>Lead #{lead.id}</small></span></Link></td><td>{lead.phone}</td><td>{lead.preferred_country || '—'}</td><td>{lead.marks == null ? '—' : `${lead.marks}%`}</td><td>{lead.ielts_score ?? '—'}</td><td>{lead.last_reply_at || '—'}</td><td><RowLink to={`/staff/students/${lead.id}`}><span className="sr-only">Open {lead.name}</span></RowLink></td></tr>)}</tbody></table></div> : <EmptyState title={search ? 'No matching students' : 'No leads yet'} description={search ? 'Try another name, phone number, or country.' : 'Student conversations will create lead records here.'} />}
    </Panel>
  </div>
}

function UsersIcon() { return <CircleUserRound size={14} aria-hidden="true" /> }

type CaseTab = 'overview' | 'applications' | 'documents' | 'tasks' | 'followups' | 'escalations' | 'activity'
const caseTabs: Array<{ key: CaseTab; label: string }> = [
  { key: 'overview', label: 'Overview' }, { key: 'applications', label: 'Applications' },
  { key: 'documents', label: 'Documents' }, { key: 'tasks', label: 'Tasks' },
  { key: 'followups', label: 'Follow-ups' }, { key: 'escalations', label: 'Escalations' },
  { key: 'activity', label: 'Activity' },
]

export function StudentCasePage() {
  const params = useParams()
  const leadId = Number(params.leadId)
  const [caseData, setCaseData] = useState<StudentCase | null>(null)
  const [tab, setTab] = useState<CaseTab>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    api.dashboard.student(leadId)
      .then((data) => { if (active) { setCaseData(data); setError('') } })
      .catch((reason: unknown) => { if (active) setError(errorMessage(reason)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [leadId, revision])

  if (loading) return <div className="page-stack"><LoadingRows rows={6} /></div>
  if (error || !caseData) return <div className="page-stack"><PageHeader eyebrow="STUDENT CASE" title="Case unavailable" /><ErrorState message={error || 'Student lead not found.'} onRetry={() => setRevision((value) => value + 1)} /><Link className="text-link" to="/staff/leads">Back to leads <ArrowRight size={14} /></Link></div>

  const { lead, applications, documents, tasks, followups, escalations, recent_activity: activity } = caseData
  const body: Record<CaseTab, ReactNode> = {
    overview: <div className="case-overview-grid"><Panel title="Student profile"><dl className="detail-grid"><div><dt>Phone</dt><dd>{lead.phone}</dd></div><div><dt>Preferred country</dt><dd>{lead.preferred_country || 'Not set'}</dd></div><div><dt>Marks</dt><dd>{lead.marks == null ? 'Not recorded' : `${lead.marks}%`}</dd></div><div><dt>IELTS</dt><dd>{lead.ielts_score ?? 'Not recorded'}</dd></div><div><dt>Budget</dt><dd>{lead.budget || 'Not recorded'}</dd></div><div><dt>Last reply</dt><dd>{lead.last_reply_at || 'Not recorded'}</dd></div></dl></Panel><Panel title="Case snapshot"><div className="case-count-grid"><div><strong>{applications.length}</strong><span>Applications</span></div><div><strong>{documents.length}</strong><span>Documents</span></div><div><strong>{tasks.filter((task) => task.status === 'pending').length}</strong><span>Pending tasks</span></div><div><strong>{escalations.filter((item) => item.status !== 'resolved').length}</strong><span>Open handoffs</span></div></div><p className="case-nudge">Keep the case current with verified updates and clear next steps.</p></Panel><Panel title="Latest activity" className="case-activity-mini">{activity.length ? activity.slice(0, 5).map((item) => <div className="mini-activity" key={item.id}><span className="activity-bullet" /><span><strong>{item.action.replaceAll('_', ' ')}</strong><small>{item.agent.replaceAll('_', ' ')}</small></span><time>{formatDate(item.created_at, true)}</time></div>) : <EmptyState title="No case activity" description="New case events will appear here." />}</Panel></div>,
    applications: <CaseList>{applications.map((item) => <div className="case-record" key={item.id}><span className="record-icon record-blue"><BriefcaseBusiness size={16} /></span><div className="record-main"><strong>{item.university}</strong><span>{item.program} · {item.country}</span><small>Updated {formatDate(item.updated_at)}</small></div><StatusPill value={item.status} /></div>)}</CaseList>,
    documents: <CaseList>{documents.map((item) => <div className="case-record" key={item.id}><span className={`record-icon ${item.status === 'problem' ? 'record-amber' : 'record-green'}`}><FileCheck2 size={16} /></span><div className="record-main"><strong>{item.document_type || 'Unclassified document'}</strong><span>{item.filename}</span><small>{item.result || 'No review details'} · {formatDate(item.uploaded_at)}</small></div><StatusPill value={item.status} /></div>)}</CaseList>,
    tasks: <CaseList>{tasks.map((item) => <div className="case-record" key={item.id}><span className={`record-icon ${item.is_overdue ? 'record-red' : 'record-blue'}`}><CheckCircle2 size={16} /></span><div className="record-main"><strong>{item.title}</strong><span>{item.description || item.task_type}</span><small>Due {formatDate(item.due_at)}{item.is_overdue ? ' · overdue' : ''}</small></div><StatusPill value={item.status} /></div>)}</CaseList>,
    followups: <CaseList>{followups.map((item) => <div className="case-record" key={item.id}><span className="record-icon record-violet"><MessageSquareText size={16} /></span><div className="record-main"><strong>{item.message}</strong><span>Created {formatDate(item.created_at)}</span></div><StatusPill value={item.status} /></div>)}</CaseList>,
    escalations: <CaseList>{escalations.map((item) => <div className="case-record case-record-tall" key={item.id}><span className="record-icon record-amber"><FileWarning size={16} /></span><div className="record-main"><strong>{item.question}</strong><span>{item.reason}</span>{item.staff_response && <small>Staff response: {item.staff_response}</small>}<small>{item.source_agent || 'Staff'} · {formatDate(item.created_at, true)}</small></div><StatusPill value={item.status} /></div>)}</CaseList>,
    activity: <CaseList>{activity.map((item) => <div className="case-record" key={item.id}><span className="record-icon record-blue"><Activity size={16} /></span><div className="record-main"><strong>{item.action.replaceAll('_', ' ')}</strong><span>{item.agent.replaceAll('_', ' ')}</span></div><time>{formatDate(item.created_at, true)}</time></div>)}</CaseList>,
  }

  return <div className="page-stack">
    <PageHeader eyebrow={`STUDENT CASE · LEAD #${lead.id}`} title={lead.name} description={`${lead.preferred_country || 'Country not set'} · Started ${formatDate(lead.created_at)}`} action={<Link className="button button-quiet" to="/staff/leads"><ArrowRight className="back-arrow" size={15} /> All leads</Link>} />
    <div className="case-identity"><span className="case-avatar">{initials(lead.name)}</span><div><strong>{lead.phone}</strong><span>Last reply {lead.last_reply_at || 'not recorded'}</span></div><div className="case-identity-spacer" /><span className="case-source"><span className="online-dot" /> Source of truth · AdmitCrew records</span></div>
    <div className="tabs case-tabs" role="tablist" aria-label="Student case sections">{caseTabs.map((item) => <button type="button" role="tab" aria-selected={tab === item.key} className={`tab-button${tab === item.key ? ' tab-active' : ''}`} key={item.key} onClick={() => setTab(item.key)}>{item.label}<span>{item.key === 'applications' ? applications.length : item.key === 'documents' ? documents.length : item.key === 'tasks' ? tasks.length : item.key === 'followups' ? followups.length : item.key === 'escalations' ? escalations.length : ''}</span></button>)}</div>
    <div className="case-tab-content">{body[tab]}</div>
  </div>
}

function CaseList({ children }: { children: ReactNode }) {
  return <Panel className="case-record-list">{Children.count(children) ? children : <EmptyState title="Nothing here yet" description="New records for this student will appear in this section." />}</Panel>
}

const applicationTransitions: Record<ApplicationStatus, ApplicationStatus[]> = {
  preparing: ['ready', 'withdrawn'], ready: ['submitted', 'withdrawn'],
  submitted: ['under_review', 'withdrawn'], under_review: ['offer_received', 'rejected', 'withdrawn'],
  offer_received: [], rejected: [], withdrawn: [],
}

export function ApplicationsPage() {
  const toast = useToast()
  const [applications, setApplications] = useState<Application[]>([])
  const [leads, setLeads] = useState<Lead[]>([])
  const [programs, setPrograms] = useState<Program[]>([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [creating, setCreating] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [createForm, setCreateForm] = useState({ lead_id: '', program_id: '', notes: '' })
  const [selectedStatus, setSelectedStatus] = useState<Record<number, ApplicationStatus>>({})
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [busyId, setBusyId] = useState<number | null>(null)
  const [rowError, setRowError] = useState<{ id: number; text: string } | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.applications.list(), api.leads.list(), api.programs.list()])
      .then(([applicationResponse, leadResponse, programResponse]) => {
        if (!active) return
        setApplications(applicationResponse.applications)
        setLeads(leadResponse.leads)
        setPrograms(programResponse.programs)
        setError('')
      })
      .catch((reason: unknown) => { if (active) setError(errorMessage(reason)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])

  const visible = useMemo(() => applications.filter((application) => {
    const matchesStatus = statusFilter === 'all' || application.status === statusFilter
    const needle = search.trim().toLowerCase()
    const matchesSearch = !needle || [application.student_name, application.university, application.program, application.country].some((value) => value?.toLowerCase().includes(needle))
    return matchesStatus && matchesSearch
  }), [applications, search, statusFilter])

  async function createApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const program = programs.find((item) => item.id === Number(createForm.program_id))
    if (!program || !createForm.lead_id) return
    setCreateBusy(true)
    try {
      const response = await api.applications.create(Number(createForm.lead_id), program.university, program.program, createForm.notes || undefined)
      toast(response.created ? 'Application created.' : 'This student already has that application.')
      setCreating(false)
      setCreateForm({ lead_id: '', program_id: '', notes: '' })
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setCreateBusy(false) }
  }

  async function changeStatus(application: Application) {
    const next = selectedStatus[application.id]
    if (!next || next === application.status) return
    setBusyId(application.id)
    setRowError(null)
    try {
      await api.applications.updateStatus(application.id, next)
      toast(`Application moved to ${next.replaceAll('_', ' ')}.`)
      setRevision((value) => value + 1)
    } catch (reason) {
      if (reason instanceof ApiError && reason.detail && typeof reason.detail === 'object' && 'readiness' in reason.detail) {
        const readiness = (reason.detail as { readiness: { missing_documents?: string[]; problematic_documents?: Array<{ document_type: string }> } }).readiness
        const reasons = [...(readiness.missing_documents ?? []).map((document) => `Missing ${document}`), ...(readiness.problematic_documents ?? []).map((document) => `${document.document_type} needs review`)]
        setRowError({ id: application.id, text: reasons.join(' · ') || errorMessage(reason) })
      } else setRowError({ id: application.id, text: errorMessage(reason) })
    } finally { setBusyId(null) }
  }

  async function addNote(application: Application) {
    const note = notes[application.id]?.trim()
    if (!note) return
    setBusyId(application.id)
    try {
      await api.applications.addNote(application.id, note)
      setNotes((current) => ({ ...current, [application.id]: '' }))
      toast('Case note added.')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setBusyId(null) }
  }

  const statuses: ApplicationStatus[] = ['preparing', 'ready', 'submitted', 'under_review', 'offer_received', 'rejected', 'withdrawn']

  return <div className="page-stack">
    <PageHeader eyebrow="APPLICATION PIPELINE" title="Applications" description="Track each case through preparation, submission, review, and recorded outcome." action={<button type="button" className="button button-primary" onClick={() => setCreating((value) => !value)}><Plus size={16} /> New application</button>} />
    {creating && <Panel title="Create application" className="create-panel"><form className="inline-form create-application-form" onSubmit={createApplication}><label>Student<select required value={createForm.lead_id} onChange={(event) => setCreateForm((value) => ({ ...value, lead_id: event.target.value }))}><option value="">Choose a student</option>{leads.map((lead) => <option key={lead.id} value={lead.id}>{lead.name} · #{lead.id}</option>)}</select></label><label>Verified program<select required value={createForm.program_id} onChange={(event) => setCreateForm((value) => ({ ...value, program_id: event.target.value }))}><option value="">Choose a catalog program</option>{programs.map((program) => <option key={program.id} value={program.id}>{program.university} · {program.program}</option>)}</select></label><label className="form-grow">Initial note <input value={createForm.notes} onChange={(event) => setCreateForm((value) => ({ ...value, notes: event.target.value }))} placeholder="Optional case context" /></label><button className="button button-primary" type="submit" disabled={createBusy || !createForm.lead_id || !createForm.program_id}>{createBusy ? 'Saving…' : 'Create'}</button></form></Panel>}
    <Panel className="table-panel"><div className="table-toolbar"><SearchBox value={search} onChange={setSearch} placeholder="Search student, university, program" /><div className="toolbar-right"><label className="sr-only" htmlFor="application-filter">Filter applications</label><select id="application-filter" className="filter-select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{statuses.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select><span className="table-caption">{visible.length} shown</span></div></div>
      {error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}
      {loading ? <LoadingRows /> : visible.length ? <div className="table-scroll"><table className="data-table application-table"><thead><tr><th>Student / program</th><th>Status</th><th>Submitted</th><th>Decision</th><th>Update status</th><th>Case note</th></tr></thead><tbody>{visible.map((application) => { const allowed = applicationTransitions[application.status]; const selected = selectedStatus[application.id] ?? ''; return <tr key={application.id}><td><Link className="program-cell" to={`/staff/students/${application.lead_id}`}><strong>{application.student_name}</strong><span>{application.university} · {application.program}</span></Link></td><td><StatusPill value={application.status} /></td><td>{formatDate(application.submitted_at)}</td><td>{formatDate(application.decision_at)}</td><td>{allowed.length ? <div className="row-action-stack"><select aria-label={`Next status for ${application.student_name}`} value={selected} onChange={(event) => setSelectedStatus((current) => ({ ...current, [application.id]: event.target.value as ApplicationStatus }))}><option value="">Select next…</option>{allowed.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select><button className="button button-quiet button-small" type="button" disabled={!selected || busyId === application.id} onClick={() => changeStatus(application)}>{busyId === application.id ? 'Saving…' : 'Apply'}</button>{rowError?.id === application.id && <small className="inline-validation" role="alert">{rowError.text}</small>}</div> : <span className="muted-text">Final state</span>}</td><td><div className="row-action-stack"><input aria-label={`Note for ${application.student_name}`} value={notes[application.id] ?? ''} onChange={(event) => setNotes((current) => ({ ...current, [application.id]: event.target.value }))} placeholder="Add a note" /><button className="button button-quiet button-small" type="button" disabled={!notes[application.id]?.trim() || busyId === application.id} onClick={() => addNote(application)}>Save note</button></div></td></tr>})}</tbody></table></div> : <EmptyState title="No applications found" description={search ? 'Try a broader search or another status.' : 'Applications created for students will appear here.'} />}
    </Panel>
  </div>
}

export function DocumentsPage() {
  const toast = useToast()
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [leads, setLeads] = useState<Lead[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [checking, setChecking] = useState(false)
  const [form, setForm] = useState({ lead_id: '', document_type: 'Passport', filename: '', document_name: '', expiry_date: '', ielts_score: '' })

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.documents.list(), api.leads.list()]).then(([docs, leadResponse]) => {
      if (active) { setDocuments(docs.documents); setLeads(leadResponse.leads); setError('') }
    }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])

  const visible = useMemo(() => documents.filter((document) => [document.student_name, document.document_type, document.filename, document.status, document.result].some((value) => value?.toLowerCase().includes(search.trim().toLowerCase()))), [documents, search])

  async function submitCheck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.lead_id || checking) return
    setChecking(true)
    try {
      const result = await api.documents.check({ lead_id: Number(form.lead_id), document_type: form.document_type, filename: form.filename, document_name: form.document_name, expiry_date: form.document_type === 'Passport' ? form.expiry_date : undefined, ielts_score: form.document_type === 'IELTS' && form.ielts_score ? Number(form.ielts_score) : undefined })
      toast(result.status === 'ok' ? 'Document check recorded as OK.' : 'Document check recorded with a problem.', result.status === 'ok' ? 'success' : 'info')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setChecking(false) }
  }

  return <div className="page-stack"><PageHeader eyebrow="DOCUMENT REVIEW" title="Documents" description="Review recorded checks and identify issues that need counselor follow-up." action={<span className="count-chip"><FileCheck2 size={14} /> {documents.length} records</span>} />
    <Panel title="Run a manual document check" className="create-panel"><form className="inline-form document-check-form" onSubmit={submitCheck}><label>Student<select required value={form.lead_id} onChange={(event) => setForm((value) => ({ ...value, lead_id: event.target.value }))}><option value="">Choose student</option>{leads.map((lead) => <option key={lead.id} value={lead.id}>{lead.name}</option>)}</select></label><label>Document type<select value={form.document_type} onChange={(event) => setForm((value) => ({ ...value, document_type: event.target.value }))}><option>Passport</option><option>transcript</option><option>IELTS</option></select></label><label>Filename<input required value={form.filename} onChange={(event) => setForm((value) => ({ ...value, filename: event.target.value }))} placeholder="passport.pdf" /></label><label>Name on document<input required value={form.document_name} onChange={(event) => setForm((value) => ({ ...value, document_name: event.target.value }))} placeholder="Name shown on document" /></label>{form.document_type === 'Passport' && <label>Expiry date<input required type="date" value={form.expiry_date} onChange={(event) => setForm((value) => ({ ...value, expiry_date: event.target.value }))} /></label>}{form.document_type === 'IELTS' && <label>IELTS score<input required type="number" min="0" max="9" step="0.5" value={form.ielts_score} onChange={(event) => setForm((value) => ({ ...value, ielts_score: event.target.value }))} /></label>}<button type="submit" className="button button-primary" disabled={checking || !form.lead_id}>{checking ? 'Checking…' : 'Record check'}</button></form></Panel>
    <Panel className="table-panel"><div className="table-toolbar"><SearchBox value={search} onChange={setSearch} placeholder="Search student or document" /><span className="table-caption">Latest first</span></div>{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}{loading ? <LoadingRows /> : visible.length ? <div className="table-scroll"><table className="data-table documents-table"><thead><tr><th>Student</th><th>Document</th><th>File</th><th>Result</th><th>Checked</th></tr></thead><tbody>{visible.map((document) => <tr key={document.id}><td><Link className="plain-link" to={`/staff/students/${document.lead_id}`}>{document.student_name || `Lead #${document.lead_id}`}</Link></td><td>{document.document_type || 'Unclassified'}</td><td className="file-cell">{document.filename}</td><td><div className="result-cell"><StatusPill value={document.status} /><span>{document.result || 'No details'}</span></div></td><td>{formatDate(document.uploaded_at, true)}</td></tr>)}</tbody></table></div> : <EmptyState title="No document checks found" description="Recorded Document Agent checks will appear here." />}</Panel>
  </div>
}

export function TasksPage() {
  const toast = useToast()
  const [tasks, setTasks] = useState<Task[]>([])
  const [leads, setLeads] = useState<Lead[]>([])
  const [applications, setApplications] = useState<Application[]>([])
  const [upcomingIds, setUpcomingIds] = useState<Set<number>>(new Set())
  const [overdueIds, setOverdueIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [filter, setFilter] = useState<'all' | 'pending' | 'overdue' | 'upcoming' | 'completed' | 'cancelled'>('all')
  const [creating, setCreating] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [generationId, setGenerationId] = useState('')
  const [generationBusy, setGenerationBusy] = useState(false)
  const [form, setForm] = useState({ lead_id: '', application_id: '', title: '', task_type: 'staff_review', due_at: '', priority: 'normal', description: '' })

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.tasks.list(), api.leads.list(), api.applications.list(), api.tasks.upcoming(7), api.tasks.overdue()]).then(([taskResponse, leadResponse, applicationResponse, upcomingResponse, overdueResponse]) => {
      if (active) { setTasks(taskResponse.tasks); setLeads(leadResponse.leads); setApplications(applicationResponse.applications); setUpcomingIds(new Set(upcomingResponse.tasks.map((task) => task.id))); setOverdueIds(new Set(overdueResponse.tasks.map((task) => task.id))); setError('') }
    }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])

  const visible = useMemo(() => {
    if (filter === 'overdue') return tasks.filter((task) => overdueIds.has(task.id))
    if (filter === 'upcoming') return tasks.filter((task) => upcomingIds.has(task.id))
    if (filter === 'all') return tasks
    return tasks.filter((task) => task.status === filter)
  }, [filter, overdueIds, tasks, upcomingIds])

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreating(false)
    try {
      await api.tasks.create({ lead_id: Number(form.lead_id), application_id: form.application_id ? Number(form.application_id) : undefined, title: form.title.trim(), task_type: form.task_type, due_at: form.due_at, priority: form.priority, description: form.description || undefined })
      toast('Task created.')
      setForm({ lead_id: '', application_id: '', title: '', task_type: 'staff_review', due_at: '', priority: 'normal', description: '' })
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
  }

  async function generateDeadline() {
    if (!generationId || generationBusy) return
    setGenerationBusy(true)
    try {
      const result = await api.tasks.generateDeadline(Number(generationId))
      if (result.generated) toast('Verified application deadline task generated.')
      else toast(result.reason === 'no_verified_deadline_available' ? 'No usable verified deadline is in the catalog.' : 'A deadline task already exists or the application is no longer open.', 'info')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setGenerationBusy(false) }
  }

  async function updateTask(task: Task, action: 'complete' | 'cancel') {
    if (action === 'cancel' && !window.confirm(`Cancel “${task.title}”?`)) return
    setBusyId(task.id)
    try {
      if (action === 'complete') await api.tasks.complete(task.id)
      else await api.tasks.cancel(task.id)
      toast(action === 'complete' ? 'Task completed.' : 'Task cancelled.')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setBusyId(null) }
  }

  const openApplications = applications.filter((item) => ['preparing', 'ready'].includes(item.status))
  const filters: Array<typeof filter> = ['all', 'pending', 'overdue', 'upcoming', 'completed', 'cancelled']

  return <div className="page-stack"><PageHeader eyebrow="WORK QUEUE" title="Tasks & deadlines" description="Due dates come from staff records or verified catalog deadlines—not guesses." action={<button className="button button-primary" type="button" onClick={() => setCreating((value) => !value)}><Plus size={16} /> Add task</button>} />
    <Panel className="task-deadline-strip"><div><span className="eyebrow">VERIFIED CATALOG DEADLINE</span><strong>Generate a submission task from an application</strong><small>Only a usable deadline already stored in the program catalog can create a task.</small></div><div className="deadline-controls"><label className="sr-only" htmlFor="deadline-application">Application</label><select id="deadline-application" value={generationId} onChange={(event) => setGenerationId(event.target.value)}><option value="">Select application</option>{openApplications.map((application) => <option key={application.id} value={application.id}>{application.student_name} · {application.university}</option>)}</select><button className="button button-quiet" type="button" onClick={generateDeadline} disabled={!generationId || generationBusy}>{generationBusy ? 'Checking…' : 'Generate task'}</button></div></Panel>
    {creating && <Panel title="Create a staff task" className="create-panel"><form className="inline-form task-form" onSubmit={createTask}><label>Student<select required value={form.lead_id} onChange={(event) => setForm((value) => ({ ...value, lead_id: event.target.value, application_id: '' }))}><option value="">Choose student</option>{leads.map((lead) => <option key={lead.id} value={lead.id}>{lead.name}</option>)}</select></label><label>Related application<select value={form.application_id} onChange={(event) => setForm((value) => ({ ...value, application_id: event.target.value }))}><option value="">No application</option>{applications.filter((application) => String(application.lead_id) === form.lead_id).map((application) => <option key={application.id} value={application.id}>{application.university} · {application.program}</option>)}</select></label><label>Title<input required value={form.title} onChange={(event) => setForm((value) => ({ ...value, title: event.target.value }))} /></label><label>Task type<input required value={form.task_type} onChange={(event) => setForm((value) => ({ ...value, task_type: event.target.value }))} /></label><label>Due date/time<input required type="datetime-local" value={form.due_at} onChange={(event) => setForm((value) => ({ ...value, due_at: event.target.value }))} /></label><label>Priority<select value={form.priority} onChange={(event) => setForm((value) => ({ ...value, priority: event.target.value }))}><option>low</option><option>normal</option><option>high</option><option>urgent</option></select></label><label className="form-grow">Description<input value={form.description} onChange={(event) => setForm((value) => ({ ...value, description: event.target.value }))} /></label><button className="button button-primary" type="submit" disabled={!form.lead_id || !form.title || !form.due_at}>Create task</button></form></Panel>}
    <Panel className="table-panel"><div className="table-toolbar task-toolbar"><div className="tabs compact-tabs" role="tablist" aria-label="Filter tasks">{filters.map((item) => <button key={item} role="tab" aria-selected={filter === item} type="button" className={`tab-button${filter === item ? ' tab-active' : ''}`} onClick={() => setFilter(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div><span className="table-caption">{visible.length} tasks</span></div>{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}{loading ? <LoadingRows /> : visible.length ? <div className="task-list">{visible.map((task) => <article className={`task-row${task.is_overdue ? ' task-row-overdue' : ''}`} key={task.id}><span className={`task-check ${task.status === 'completed' ? 'task-check-complete' : ''}`}>{task.status === 'completed' ? <Check size={14} /> : <Clock3 size={14} />}</span><div className="task-copy"><div className="task-title-line"><strong>{task.title}</strong><StatusPill value={task.status} compact />{task.is_overdue && <span className="overdue-tag">OVERDUE</span>}</div><span>{task.student_name} {task.university ? `· ${task.university}` : ''} · {task.description || task.task_type}</span><small>Due {formatDate(task.due_at, true)} · {task.priority} priority</small></div>{task.status === 'pending' && <div className="task-actions"><button className="button button-quiet button-small" type="button" disabled={busyId === task.id} onClick={() => updateTask(task, 'complete')}>Complete</button><button className="icon-button" type="button" title="Cancel task" aria-label={`Cancel ${task.title}`} disabled={busyId === task.id} onClick={() => updateTask(task, 'cancel')}><X size={16} /></button></div>}</article>)}</div> : <EmptyState title="No tasks in this view" description="Add a staff task or switch the task filter." />}</Panel>
  </div>
}

export function FollowupsPage() {
  const toast = useToast()
  const [pending, setPending] = useState<Followup[]>([])
  const [sent, setSent] = useState<Followup[]>([])
  const [view, setView] = useState<'pending' | 'sent'>('pending')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.followups.pending(), api.followups.sent()]).then(([pendingResponse, sentResponse]) => {
      if (active) { setPending(pendingResponse.followups); setSent(sentResponse.followups); setError('') }
    }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])

  async function runDetection() {
    setRunning(true)
    try { const result = await api.followups.run(); toast(`${result.created} new reminder${result.created === 1 ? '' : 's'} drafted.`); setRevision((value) => value + 1) }
    catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setRunning(false) }
  }

  async function approve(id: number) {
    if (busyId !== null) return
    setBusyId(id)
    try {
      const result = await api.followups.approve(id)
      toast(result.already_sent ? 'This reminder was already sent.' : 'Reminder approved and sent.')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setBusyId(null) }
  }

  const rows = view === 'pending' ? pending : sent
  return <div className="page-stack"><PageHeader eyebrow="STAFF APPROVAL QUEUE" title="Follow-ups" description="Review a draft, then explicitly approve it for sending." action={null} />
    <div className="approval-banner"><span className="approval-mark"><ShieldCheck size={18} /></span><div><strong>AI drafts. Staff approves.</strong><span>Detection only creates pending reminders. Nothing is sent without your approval.</span></div></div>
    <Panel className="table-panel"><div className="table-toolbar"><div className="tabs compact-tabs" role="tablist" aria-label="Follow-up status">{(['pending', 'sent'] as const).map((item) => <button type="button" role="tab" aria-selected={view === item} className={`tab-button${view === item ? ' tab-active' : ''}`} onClick={() => setView(item)} key={item}>{item === 'pending' ? 'Pending approval' : 'Sent'}<span>{item === 'pending' ? pending.length : sent.length}</span></button>)}</div><span className="table-caption">{rows.length} reminders</span></div>{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}{loading ? <LoadingRows /> : rows.length ? <div className="followup-list">{rows.map((item) => <article className="followup-row" key={item.id}><div className="followup-avatar">{initials(item.student_name)}</div><div className="followup-main"><div className="followup-heading"><Link to={`/staff/students/${item.lead_id}`}><strong>{item.student_name}</strong></Link><span className="followup-date">Drafted {formatDate(item.created_at, true)}</span><StatusPill value={item.status} compact /></div><blockquote>{item.message}</blockquote><small>Student #{item.lead_id}</small></div>{view === 'pending' ? <button className="button button-primary approve-button" type="button" disabled={busyId !== null} onClick={() => approve(item.id)}>{busyId === item.id ? 'Sending…' : <><Check size={15} /> Approve &amp; send</>}</button> : <span className="sent-stamp"><CheckCircle2 size={15} /> Sent {formatDate(item.sent_at, true)}</span>}</article>)}</div> : <EmptyState title={view === 'pending' ? 'No reminders awaiting approval' : 'No sent reminders yet'} description={view === 'pending' ? 'Run detection to draft reminders for inactive students. Staff approval is always required.' : 'Approved reminders will appear here.'} action={view === 'pending' ? <button className="button button-quiet" type="button" disabled={running} onClick={runDetection}>{running ? 'Checking…' : 'Run detection'}</button> : undefined} />}</Panel>
  </div>
}

export function EscalationsPage() {
  const toast = useToast()
  const [escalations, setEscalations] = useState<Escalation[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [response, setResponse] = useState('')
  const [filter, setFilter] = useState<'active' | 'resolved'>('active')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    api.escalations.list().then((result) => {
      if (active) { setEscalations(result.escalations); setError('') }
    }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])

  const filtered = escalations.filter((item) => filter === 'active' ? item.status !== 'resolved' : item.status === 'resolved')
  const selected = escalations.find((item) => item.id === selectedId) ?? filtered[0] ?? null

  async function resolve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || response.trim().length < 10 || submitting) return
    setSubmitting(true)
    try {
      const result = await api.escalations.resolve(selected.id, response.trim())
      setResponse('')
      toast(result.escalation.status === 'resolved' ? 'Escalation resolved.' : 'Escalation was already resolved.')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setSubmitting(false) }
  }

  return <div className="page-stack"><PageHeader eyebrow="HUMAN HANDOFF" title="Escalations" description="Investigate what the verified catalog cannot answer, then leave a clear staff response." action={<span className="human-response-note"><ShieldCheck size={15} /> Human response · no catalog auto-update</span>} />
    <div className="escalation-workspace"><Panel className="escalation-inbox"><div className="tabs compact-tabs" role="tablist" aria-label="Escalation status">{(['active', 'resolved'] as const).map((item) => <button key={item} type="button" role="tab" aria-selected={filter === item} className={`tab-button${filter === item ? ' tab-active' : ''}`} onClick={() => { setFilter(item); setSelectedId(null) }}>{item === 'active' ? 'Open / in progress' : 'Resolved'}<span>{escalations.filter((row) => item === 'active' ? row.status !== 'resolved' : row.status === 'resolved').length}</span></button>)}</div>{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}{loading ? <LoadingRows rows={4} /> : filtered.length ? <div className="escalation-list">{filtered.map((item) => <button key={item.id} type="button" className={`escalation-list-item${(selected?.id === item.id ? ' escalation-selected' : '')}`} onClick={() => { setSelectedId(item.id); setResponse('') }}><span className="escalation-list-top"><StatusPill value={item.status} compact /><time>{formatDate(item.created_at, true)}</time></span><strong>{item.student_name || (item.lead_id ? `Lead #${item.lead_id}` : 'Student unavailable')}</strong><span>{item.question}</span><small>{item.source_agent ? item.source_agent.replaceAll('_', ' ') : 'Source unavailable'}</small></button>)}</div> : <EmptyState title={filter === 'active' ? 'No open handoffs' : 'No resolved handoffs'} description="Escalations raised from uncertain answers will appear here." />}</Panel>
      <section className="panel escalation-detail">{selected ? <><div className="escalation-detail-top"><div><span className="eyebrow">ESCALATION #{selected.id}</span><h2>{selected.student_name || (selected.lead_id ? `Lead #${selected.lead_id}` : 'Student unavailable')}</h2><span className="detail-subtitle">{selected.source_agent ? selected.source_agent.replaceAll('_', ' ') : 'Source unavailable'} · {formatDate(selected.created_at, true)}</span></div><StatusPill value={selected.status} /></div><div className="escalation-question"><span className="eyebrow">ORIGINAL STUDENT QUESTION</span><p>{selected.question}</p></div><div className="escalation-reason"><span className="eyebrow">WHY IT WAS HANDED OFF</span><p>{selected.reason}</p></div>{selected.conversation_id && <div className="conversation-delivery-note"><MessageSquareText size={16} /><span>When resolved, this response is added to the student's existing conversation.</span></div>}{selected.status === 'resolved' ? <div className="resolved-response"><span className="eyebrow">STAFF RESPONSE</span><p>{selected.staff_response}</p><small>Resolved {formatDate(selected.resolved_at, true)}</small></div> : <form className="resolve-form" onSubmit={resolve}><label htmlFor="staff-response">Staff response</label><textarea id="staff-response" rows={4} value={response} onChange={(event) => setResponse(event.target.value)} placeholder="Write a clear, verified response for the student…" minLength={10} required /><div className="resolve-form-footer"><span>{selected.conversation_id ? 'Delivered to chat on resolution' : 'No conversation is linked to this handoff'}</span><button className="button button-primary" type="submit" disabled={submitting || response.trim().length < 10}>{submitting ? 'Resolving…' : <><Send size={15} /> Resolve &amp; respond</>}</button></div></form>}</> : <EmptyState title="Select an escalation" description="Choose a handoff from the queue to review its question and respond." />}</section></div>
  </div>
}

export function ProgramsPage() {
  const [programs, setPrograms] = useState<Program[]>([])
  const [search, setSearch] = useState('')
  const [country, setCountry] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    api.programs.list().then((result) => { if (active) { setPrograms(result.programs); setError('') } }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])
  const countries = [...new Set(programs.map((program) => program.country))].sort()
  const visible = programs.filter((program) => {
    const matchesCountry = country === 'all' || program.country === country
    const needle = search.trim().toLowerCase()
    const matchesSearch = !needle || [program.university, program.program, program.country, program.documents_needed].some((value) => value.toLowerCase().includes(needle))
    return matchesCountry && matchesSearch
  })

  return <div className="page-stack"><PageHeader eyebrow="VERIFIED SOURCE OF TRUTH" title="Programs" description="University and program facts used by AdmitCrew's guidance and deadline workflows." action={<span className="catalog-seal"><ShieldCheck size={15} /> Verified catalog</span>} /><div className="catalog-note"><ShieldCheck size={16} /><span>This is the verified AdmitCrew catalog. No university facts are supplemented from external sources.</span></div><Panel className="table-panel"><div className="table-toolbar"><SearchBox value={search} onChange={setSearch} placeholder="Search university, program, or document" /><div className="toolbar-right"><label className="sr-only" htmlFor="country-filter">Filter by country</label><select id="country-filter" className="filter-select" value={country} onChange={(event) => setCountry(event.target.value)}><option value="all">All countries</option>{countries.map((item) => <option key={item}>{item}</option>)}</select><span className="table-caption">{visible.length} programs</span></div></div>{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}{loading ? <LoadingRows /> : visible.length ? <div className="table-scroll"><table className="data-table programs-table"><thead><tr><th>University / country</th><th>Program</th><th>Fee / year</th><th>Deadline</th><th>Minimum</th><th>Documents needed</th></tr></thead><tbody>{visible.map((program) => <tr key={program.id}><td className="university-cell"><span className="university-name">{program.university}</span><span className="university-country">{program.country}</span></td><td className="program-name">{program.program}</td><td className="fee-cell">{program.fee_per_year}</td><td>{program.deadline}</td><td>{program.min_marks}% marks <span className="dot-separator">·</span> IELTS {program.min_ielts}</td><td className="documents-needed-cell">{program.documents_needed}</td></tr>)}</tbody></table></div> : <EmptyState title="No catalog matches" description="Try a broader search or another country." />}</Panel></div>
}

export function ActivityPage() {
  const [items, setItems] = useState<ActivityItem[]>([])
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([api.dashboard.activity(100), api.leads.list()]).then(([activityResponse, leadResponse]) => {
      if (active) { setItems(activityResponse.activity); setLeads(leadResponse.leads); setError('') }
    }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])
  const leadMap = new Map(leads.map((lead) => [lead.id, lead.name]))

  return <div className="page-stack"><PageHeader eyebrow="AGENT AUDIT TRAIL" title="Agent Activity" description="Recent meaningful actions from AdmitCrew's agents and staff." action={<span className="count-chip"><Activity size={14} /> {items.length} events</span>} />{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}<Panel className="activity-feed-panel"><div className="activity-timeline">{loading ? <LoadingRows rows={7} /> : items.length ? items.map((item) => { const leadId = item.details?.match(/Lead ID:\s*(\d+)/i)?.[1]; const leadName = leadId ? leadMap.get(Number(leadId)) : undefined; const isSystemEvent = /^(scan|check|sync|poll|heartbeat|cleanup|refresh|automatic|scheduled|batch|cron)/i.test(item.action);
    return <div className={`timeline-item${isSystemEvent ? ' system-event' : ''}`} key={item.id}><span className="timeline-pin"><Activity size={14} /></span><div className="timeline-content"><div className="timeline-head"><strong>{item.action.replaceAll('_', ' ')}</strong><time>{formatDate(item.created_at, true)}</time></div><div className="timeline-meta"><span className="agent-tag">{item.agent.replaceAll('_', ' ')}</span>{leadName && <Link to={`/staff/students/${leadId}`}>{leadName}</Link>}</div></div></div> }) : <EmptyState title="No activity yet" description="Agent and staff actions will show up here." />}</div></Panel></div>
}

export function StaffPage() {
  const toast = useToast()
  const [staff, setStaff] = useState<StaffProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'counselor' as StaffProfile['role'] })
  const [busyId, setBusyId] = useState<number | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    api.staff.list().then((result) => { if (active) { setStaff(result.staff); setError('') } }).catch((reason: unknown) => { if (active) setError(errorMessage(reason)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [revision])

  async function createStaff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    try {
      await api.staff.create(form)
      toast('Staff account created.')
      setForm({ name: '', email: '', password: '', role: 'counselor' })
      setShowCreate(false)
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setSubmitting(false) }
  }

  async function updateMember(member: StaffProfile, changes: Partial<Pick<StaffProfile, 'role' | 'is_active'>>) {
    if ('is_active' in changes && changes.is_active === false && !window.confirm(`Deactivate ${member.name}? They will lose access immediately.`)) return
    setBusyId(member.id)
    try {
      await api.staff.update(member.id, changes)
      toast('Staff account updated.')
      setRevision((value) => value + 1)
    } catch (reason) { toast(errorMessage(reason), 'error') }
    finally { setBusyId(null) }
  }

  return <div className="page-stack"><PageHeader eyebrow="ADMINISTRATION" title="Staff Management" description="Manage counselor and administrator access to AdmitCrew." action={<button className="button button-primary" type="button" onClick={() => setShowCreate((value) => !value)}><UserRoundPlus size={16} /> Add staff</button>} />
    {showCreate && <Panel title="Create staff account" className="create-panel"><form className="inline-form staff-create-form" onSubmit={createStaff}><label>Name<input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} autoComplete="name" /></label><label>Email<input required type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} autoComplete="email" /></label><label>Role<select value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as StaffProfile['role'] }))}><option value="counselor">Counselor</option><option value="admin">Admin</option></select></label><label>Password<input required type="password" minLength={12} maxLength={1024} value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} autoComplete="new-password" /><small>At least 12 characters</small></label><button className="button button-primary" type="submit" disabled={submitting}>{submitting ? 'Creating…' : 'Create account'}</button></form></Panel>}
    <Panel className="table-panel"><div className="table-toolbar"><span className="table-caption">{staff.length} staff accounts · password hashes are never shown</span><span className="permissions-note"><ShieldCheck size={14} /> Active admins: {staff.filter((member) => member.role === 'admin' && member.is_active).length}</span></div>{error && <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} />}{loading ? <LoadingRows /> : staff.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Staff member</th><th>Email</th><th>Role</th><th>Access</th><th>Last updated</th></tr></thead><tbody>{staff.map((member) => <tr key={member.id}><td><span className="student-cell"><span className="student-avatar">{initials(member.name)}</span><span><strong>{member.name}</strong><small>Staff #{member.id}</small></span></span></td><td>{member.email}</td><td><label className="sr-only" htmlFor={`role-${member.id}`}>Role for {member.name}</label><select id={`role-${member.id}`} className="table-select" value={member.role} disabled={busyId === member.id} onChange={(event) => updateMember(member, { role: event.target.value as StaffProfile['role'] })}><option value="counselor">Counselor</option><option value="admin">Admin</option></select></td><td><button className={`account-state-button${member.is_active ? ' is-active' : ' is-inactive'}`} type="button" disabled={busyId === member.id} onClick={() => updateMember(member, { is_active: !member.is_active })}><span />{member.is_active ? 'Active' : 'Inactive'}</button></td><td>{formatDate(member.updated_at, true)}</td></tr>)}</tbody></table></div> : <EmptyState title="No staff accounts" description="Create the first counselor or administrator account." />}</Panel>
  </div>
}

export function LeadAvatar({ lead }: { lead: Lead }) {
  return <span className="student-avatar">{initials(lead.name)}</span>
}
