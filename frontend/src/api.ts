import type {
  ActivityItem,
  Application,
  ApplicationStatus,
  AttentionItem,
  DashboardOverview,
  DocumentRecord,
  Escalation,
  Followup,
  Lead,
  Pipeline,
  Program,
  StaffProfile,
  StaffRole,
  StudentCase,
  Task,
} from './types'

const TOKEN_KEY = 'admitcrew.staff.access-token'
const SESSION_EXPIRED_EVENT = 'admitcrew:session-expired'

type RequestOptions = RequestInit & { auth?: boolean }

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export const tokenStore = {
  get(): string | null {
    return window.localStorage.getItem(TOKEN_KEY)
  },
  set(token: string): void {
    window.localStorage.setItem(TOKEN_KEY, token)
  },
  clear(): void {
    window.localStorage.removeItem(TOKEN_KEY)
  },
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object') {
      const record = detail as Record<string, unknown>
      if (typeof record.message === 'string') return record.message
      if (typeof record.detail === 'string') return record.detail
      if (typeof record.error === 'string') return record.error
    }
    return error.message
  }
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, headers: suppliedHeaders, ...rest } = options
  const headers = new Headers(suppliedHeaders)
  headers.set('Accept', 'application/json')
  if (rest.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const token = auth ? tokenStore.get() : null
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(path, { ...rest, headers, credentials: 'omit' })
  } catch {
    throw new ApiError(0, null, 'Could not reach AdmitCrew. Check that the backend is running and try again.')
  }

  const contentType = response.headers.get('content-type') ?? ''
  const payload: unknown = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '')

  if (response.status === 401) {
    tokenStore.clear()
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT))
  }

  if (!response.ok) {
    const detail = payload && typeof payload === 'object' && 'detail' in payload
      ? (payload as { detail: unknown }).detail
      : payload
    throw new ApiError(response.status, detail, `Request failed (${response.status}).`)
  }
  return payload as T
}

const jsonBody = (value: unknown) => JSON.stringify(value)
const queryString = (values: Record<string, string | number | undefined>) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const result = query.toString()
  return result ? `?${result}` : ''
}

export const api = {
  health: () => request<{ status: string }>('/health', { auth: false }),
  auth: {
    login: (email: string, password: string) => request<{
      access_token: string
      token_type: 'bearer'
      expires_in: number
      staff: StaffProfile
    }>('/api/auth/login', { method: 'POST', body: jsonBody({ email, password }), auth: false }),
    me: () => request<{ staff: StaffProfile }>('/api/auth/me'),
  },
  dashboard: {
    overview: (upcomingDays = 7) => request<DashboardOverview>(`/api/dashboard/overview?upcoming_days=${upcomingDays}`),
    pipeline: () => request<{ pipeline: Pipeline; total_applications: number }>('/api/dashboard/pipeline'),
    attention: (limit = 50) => request<{ items: AttentionItem[]; total: number }>(`/api/dashboard/attention?limit=${limit}`),
    activity: (limit = 20) => request<{ activity: ActivityItem[] }>(`/api/dashboard/activity?limit=${limit}`),
    student: (leadId: number) => request<StudentCase>(`/api/dashboard/students/${leadId}`),
  },
  leads: {
    list: (search = '') => request<{ leads: Lead[]; total: number }>(`/api/leads${queryString({ search, limit: 500 })}`),
    get: (phone: string) => request<{ found: boolean; lead?: Lead }>(`/api/leads/${encodeURIComponent(phone)}`),
    save: (value: Partial<Lead> & Pick<Lead, 'name' | 'phone'>) => request('/api/leads', { method: 'POST', body: jsonBody(value) }),
  },
  applications: {
    list: (status?: ApplicationStatus) => request<{ applications: Application[]; total: number }>(`/api/applications${queryString({ status, limit: 500 })}`),
    create: (leadId: number, university: string, program: string, notes?: string) => request<{ application: Application; created: boolean }>('/api/applications', { method: 'POST', body: jsonBody({ lead_id: leadId, university, program, notes }) }),
    updateStatus: (id: number, status: ApplicationStatus) => request<{ application: Application }>(`/api/applications/${id}/status`, { method: 'PATCH', body: jsonBody({ status }) }),
    addNote: (id: number, note: string) => request<{ application: Application }>(`/api/applications/${id}/notes`, { method: 'POST', body: jsonBody({ note }) }),
  },
  documents: {
    list: () => request<{ documents: DocumentRecord[] }>('/api/documents'),
    check: (value: { lead_id: number; document_type: string; filename: string; document_name: string; expiry_date?: string; ielts_score?: number }) => request<{ status: string; document: DocumentRecord; problems: string[] }>('/api/documents/check', { method: 'POST', body: jsonBody(value) }),
  },
  tasks: {
    list: (status?: string) => request<{ tasks: Task[] }>(`/api/tasks${queryString({ status })}`),
    create: (value: { lead_id: number; application_id?: number; title: string; description?: string; task_type: string; due_at: string; priority: string }) => request<{ task: Task }>('/api/tasks', { method: 'POST', body: jsonBody(value) }),
    upcoming: (days = 7) => request<{ tasks: Task[] }>(`/api/tasks/upcoming?days=${days}`),
    overdue: () => request<{ tasks: Task[] }>('/api/tasks/overdue'),
    generateDeadline: (applicationId: number) => request<{ generated: boolean; duplicate?: boolean; reason?: string; task?: Task }>('/api/tasks/generate-application-deadline', { method: 'POST', body: jsonBody({ application_id: applicationId }) }),
    complete: (id: number) => request<{ task: Task }>(`/api/tasks/${id}/complete`, { method: 'PATCH' }),
    cancel: (id: number) => request<{ task: Task }>(`/api/tasks/${id}/cancel`, { method: 'PATCH' }),
  },
  followups: {
    pending: () => request<{ followups: Followup[] }>('/api/followups/pending'),
    sent: () => request<{ followups: Followup[] }>('/api/followups/sent'),
    run: () => request<{ created: number }>('/api/followups/run', { method: 'POST' }),
    approve: (id: number) => request<{ already_sent?: boolean; followup: Followup }>(`/api/followups/${id}/approve`, { method: 'POST' }),
  },
  escalations: {
    list: (status?: string) => request<{ escalations: Escalation[] }>(`/api/escalations${queryString({ status })}`),
    open: () => request<{ escalations: Escalation[] }>('/api/escalations/open'),
    resolve: (id: number, staffResponse: string) => request<{ escalation: Escalation }>(`/api/escalations/${id}/resolve`, { method: 'PATCH', body: jsonBody({ staff_response: staffResponse }) }),
    start: (id: number) => request<{ escalation: Escalation }>(`/api/escalations/${id}/start`, { method: 'PATCH' }),
  },
  programs: {
    list: (search = '', country = '') => request<{ programs: Program[]; total: number }>(`/api/programs${queryString({ search, country })}`),
  },
  staff: {
    list: () => request<{ staff: StaffProfile[] }>('/api/staff'),
    create: (value: { name: string; email: string; password: string; role: StaffRole }) => request<{ staff: StaffProfile }>('/api/staff', { method: 'POST', body: jsonBody(value) }),
    update: (id: number, value: Partial<Pick<StaffProfile, 'name' | 'role' | 'is_active'>> & { password?: string }) => request<{ staff: StaffProfile }>(`/api/staff/${id}`, { method: 'PATCH', body: jsonBody(value) }),
  },
  chat: {
    start: (sessionId: string) => request<{ session_id: string; agent: string; message: string }>(`/api/chat/start?session_id=${encodeURIComponent(sessionId)}`, { method: 'POST', auth: false }),
    send: (sessionId: string, message: string) => request<{ agent?: string; message: string; conversation_id?: number; error?: string; details?: unknown }>('/api/chat/message', { method: 'POST', body: jsonBody({ session_id: sessionId, message }), auth: false }),
    history: (sessionId: string) => request<{ messages: Array<{ id: string; role: 'student' | 'admitcrew' | 'staff'; text: string; agent: string; timestamp: string }> }>(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`, { auth: false }),
  },
}
