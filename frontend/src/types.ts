export type StaffRole = 'admin' | 'counselor'

export interface StaffProfile {
  id: number
  name: string
  email: string
  role: StaffRole
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Lead {
  id: number
  name: string
  phone: string
  preferred_country: string | null
  marks: number | null
  ielts_score: number | null
  budget: string | null
  last_reply_at: string | null
  created_at: string
  updated_at: string
}

export type ApplicationStatus =
  | 'preparing'
  | 'ready'
  | 'submitted'
  | 'under_review'
  | 'offer_received'
  | 'rejected'
  | 'withdrawn'

export interface Application {
  id: number
  lead_id: number
  program_id: number
  university: string
  program: string
  country: string
  status: ApplicationStatus
  notes: string
  submitted_at: string | null
  decision_at: string | null
  created_at: string
  updated_at: string
  student_name?: string
}

export interface DocumentRecord {
  id: number
  lead_id: number
  student_name?: string
  student_phone?: string
  document_type: string | null
  filename: string
  status: string
  result: string | null
  uploaded_at: string
}

export type TaskStatus = 'pending' | 'completed' | 'cancelled'
export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface Task {
  id: number
  lead_id: number
  application_id: number | null
  student_name?: string
  university?: string | null
  program?: string | null
  title: string
  description: string | null
  task_type: string
  due_at: string
  status: TaskStatus
  priority: TaskPriority
  completed_at: string | null
  created_at: string
  updated_at: string
  is_overdue: boolean
}

export interface Followup {
  id: number
  lead_id: number
  student_name: string
  student_phone?: string
  message: string
  status: string
  approved_at: string | null
  sent_at: string | null
  created_at: string
}

export interface Escalation {
  id: number
  lead_id: number | null
  student_name: string | null
  conversation_id: number | null
  question: string
  reason: string
  source_agent: string | null
  status: 'open' | 'in_progress' | 'resolved' | string
  staff_response: string | null
  created_at: string
  resolved_at: string | null
}

export interface Program {
  id: number
  university: string
  country: string
  program: string
  fee_per_year: string
  deadline: string
  min_marks: number
  min_ielts: number
  documents_needed: string
}

export interface ActivityItem {
  id: number
  type: string
  agent: string
  action: string
  details: string | null
  created_at: string
}

export interface DashboardOverview {
  total_leads: number
  total_applications: number
  active_applications: number
  submitted_applications: number
  offers_received: number
  rejected_applications: number
  applications_needing_attention: number
  open_escalations: number
  pending_followups: number
  overdue_tasks: number
  upcoming_tasks: number
  document_problems: number
  upcoming_days: number
}

export interface Pipeline {
  preparing: number
  ready: number
  submitted: number
  under_review: number
  offer_received: number
  rejected: number
  withdrawn: number
}

export interface AttentionItem {
  type: string
  severity: string
  lead_id: number | null
  student_name?: string | null
  application_id: number | null
  title: string
  description: string | null
  created_at: string | null
  due_at: string | null
  source_record_id: number
  is_overdue?: boolean
  missing_documents?: string[]
  problematic_documents?: Array<{ document_type: string; status: string; details: string | null }>
}

export interface StudentCase {
  lead: Lead
  applications: Application[]
  documents: DocumentRecord[]
  tasks: Task[]
  followups: Followup[]
  escalations: Escalation[]
  recent_activity: ActivityItem[]
}

export interface ChatMessage {
  id: string
  role: 'student' | 'admitcrew' | 'staff'
  text: string
  agent: string
  timestamp: string
}
