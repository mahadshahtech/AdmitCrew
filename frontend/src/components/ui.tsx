import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, Check, Info, X } from 'lucide-react'

export type ToastKind = 'success' | 'error' | 'info'
interface ToastValue { id: number; message: string; kind: ToastKind }
interface ToastContextValue { toast: (message: string, kind?: ToastKind) => void }
const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastValue[]>([])
  const toast = useCallback((message: string, kind: ToastKind = 'success') => {
    const id = Date.now() + Math.random()
    setItems((current) => [...current, { id, message, kind }])
    window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), 4200)
  }, [])
  const value = useMemo(() => ({ toast }), [toast])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        <AnimatePresence>
          {items.map((item) => {
            const Icon = item.kind === 'success' ? Check : item.kind === 'error' ? AlertCircle : Info
            return (
              <motion.div key={item.id} className={`toast toast-${item.kind}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} role={item.kind === 'error' ? 'alert' : 'status'}>
                <Icon size={16} aria-hidden="true" />
                <span>{item.message}</span>
                <button type="button" className="icon-button toast-dismiss" aria-label="Dismiss notification" onClick={() => setItems((current) => current.filter((toastItem) => toastItem.id !== item.id))}><X size={14} /></button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within ToastProvider.')
  return context.toast
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </header>
  )
}

export function Panel({ children, className = '', title, aside }: { children: ReactNode; className?: string; title?: string; aside?: ReactNode }) {
  return (
    <section className={`panel ${className}`}>
      {(title || aside) && <div className="panel-heading">{title && <h2>{title}</h2>}{aside}</div>}
      {children}
    </section>
  )
}

export function LoadingState({ label = 'Loading records' }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="spinner" aria-hidden="true" /><span>{label}</span></div>
}

export function LoadingRows({ rows = 5 }: { rows?: number }) {
  return <div className="skeleton-list" aria-label="Loading">
    {Array.from({ length: rows }, (_, index) => <div key={index} className="skeleton-row"><span /><span /><span /></div>)}
  </div>
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-mark"><Info size={18} /></span><h3>{title}</h3><p>{description}</p>{action}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-state" role="alert"><AlertCircle size={18} /><span>{message}</span>{onRetry && <button className="button button-quiet button-small" type="button" onClick={onRetry}>Try again</button>}</div>
}

export function StatusPill({ value, compact = false }: { value: string; compact?: boolean }) {
  const normalized = value.toLowerCase().replaceAll('_', '-')
  return <span className={`status-pill status-${normalized}${compact ? ' status-compact' : ''}`}><span className="status-dot" />{value.replaceAll('_', ' ')}</span>
}

export function formatDate(value: string | null | undefined, includeTime = false): string {
  if (!value) return '—'
  const date = new Date(value.replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, includeTime
    ? { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }
    : { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('')
}
