import { useEffect, useRef, useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { ArrowDown, ArrowUp, Bot, GraduationCap, ShieldCheck, Sparkles, SquarePen } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api'
import type { ChatMessage as Message } from '../types'

const STORAGE_KEY = 'admitcrew.student.chat'
interface SavedChat { sessionId: string; messages: Message[] }

function readSavedChat(): SavedChat | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    if (!value) return null
    const parsed = JSON.parse(value) as SavedChat
    if (typeof parsed.sessionId !== 'string' || !Array.isArray(parsed.messages)) return null
    return parsed
  } catch {
    return null
  }
}

function makeMessage(role: Message['role'], text: string, agent: string): Message {
  return { id: crypto.randomUUID(), role, text, agent, timestamp: new Date().toISOString() }
}

function agentLabel(agent?: string): string {
  const labels: Record<string, string> = {
    lead_agent: 'Lead Agent',
    coordinator_agent: 'Coordinator',
    university_agent: 'University Agent',
    document_agent: 'Document Agent',
    followup_agent: 'Follow-up Agent',
    unrelated: 'Coordinator',
    staff: 'Staff',
  }
  return agent ? (labels[agent] ?? agent.replaceAll('_', ' ')) : 'AdmitCrew'
}

export function ChatPage() {
  const [saved] = useState(readSavedChat)
  const [sessionId, setSessionId] = useState<string | null>(saved?.sessionId ?? null)
  const [messages, setMessages] = useState<Message[]>(saved?.messages ?? [])
  const [draft, setDraft] = useState('')
  const [starting, setStarting] = useState(!saved)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const sessionSeed = useRef(saved?.sessionId ?? crypto.randomUUID())
  const startPromise = useRef<Promise<{ session_id: string; agent: string; message: string }> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (sessionId) {
      // Fetch history from server
      api.chat.history(sessionId)
        .then((response) => {
          if (response.messages && response.messages.length > 0) {
            setMessages(response.messages)
          } else {
            setStarting(false)
          }
        })
        .catch(() => {
          // If history fetch fails, start fresh
          setStarting(false)
        })
      return
    }
    let active = true
    startPromise.current ??= api.chat.start(sessionSeed.current)
    startPromise.current
      .then((response) => {
        if (!active) return
        setSessionId(response.session_id)
        setMessages([makeMessage('admitcrew', response.message, 'lead_agent')])
        setError('')
        setStarting(false)
      })
      .catch((reason: unknown) => {
        if (!active) return
        setError(errorMessage(reason))
        setStarting(false)
      })
    return () => { active = false }
  }, [sessionId])

  useEffect(() => {
    if (sessionId) {
      const value: SavedChat = { sessionId, messages: messages.slice(-150) }
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    }
  }, [sessionId, messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  async function startNewConversation() {
    setStarting(true)
    setSending(false)
    setError('')
    startPromise.current = null
    const nextId = crypto.randomUUID()
    sessionSeed.current = nextId
    setSessionId(null)
    try {
      const request = api.chat.start(nextId)
      startPromise.current = request
      const response = await request
      setSessionId(response.session_id)
      setMessages([makeMessage('admitcrew', response.message, 'lead_agent')])
    } catch (reason) {
      setError(errorMessage(reason))
      setStarting(false)
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || !sessionId || sending || starting) return
    setDraft('')
    setError('')
    setMessages((current) => [...current, makeMessage('student', text, 'student')])
    setSending(true)
    try {
      const reply = await api.chat.send(sessionId, text)
      if (reply.error) throw new Error(reply.message || reply.error)
      const agent = reply.agent ?? 'coordinator_agent'
      setMessages((current) => [...current, makeMessage('admitcrew', reply.message, agent)])
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setSending(false)
      composerRef.current?.focus()
    }
  }

  return (
    <div className="chat-page">
      <header className="public-header">
        <Link to="/chat" className="brand-lockup public-brand" aria-label="AdmitCrew home">
          <span className="brand-mark"><GraduationCap size={21} strokeWidth={1.8} /></span>
          <span className="brand-name">Admit<span>Crew</span></span>
        </Link>
        <div className="public-header-right">
          <span className="public-secure"><ShieldCheck size={14} /> Verified guidance, real people when needed</span>
          <Link to="/staff/login" className="staff-entry-link">Staff sign in <ArrowDown className="staff-entry-arrow" size={13} /></Link>
        </div>
      </header>

      <div className="chat-layout">
        <aside className="chat-aside">
          <div className="chat-aside-top">
            <span className="eyebrow">YOUR ADMISSIONS DESK</span>
            <h1>One clear next step, at a time.</h1>
            <p>Talk through your study plans with the AdmitCrew team. Answers about universities come from our verified catalog.</p>
          </div>
          <div className="chat-capability-list">
            <div><span className="capability-icon capability-blue"><GraduationCap size={17} /></span><span><strong>University guidance</strong><small>Catalog-backed program details</small></span></div>
            <div><span className="capability-icon capability-teal"><Bot size={17} /></span><span><strong>Application support</strong><small>Profile and document questions</small></span></div>
            <div><span className="capability-icon capability-violet"><ShieldCheck size={17} /></span><span><strong>Human handoff</strong><small>Unverified questions go to staff</small></span></div>
          </div>
          <div className="chat-aside-foot"><span className="online-dot" /> Catalog-backed guidance <span className="aside-foot-separator">·</span> staff handoff when needed</div>
        </aside>

        <section className="chat-workspace" aria-label="Admissions conversation">
          <div className="chat-workspace-header">
            <div className="chat-contact">
              <span className="coordinator-avatar"><Sparkles size={18} /></span>
              <div><strong>AdmitCrew Admissions</strong><span><span className="online-dot" /> AI team · human support</span></div>
            </div>
            <button className="icon-button chat-new-button" type="button" onClick={startNewConversation} disabled={starting || sending} title="Start a new conversation" aria-label="Start a new conversation"><SquarePen size={17} /></button>
          </div>

          <div className="conversation-scroll" aria-live="polite" aria-label="Conversation messages">
            {starting && messages.length === 0 && <div className="chat-start-loading"><span className="spinner" />Opening your admissions conversation…</div>}
            {error && !messages.length && <div className="chat-connection-error" role="alert"><span>{error}</span><button className="button button-small button-quiet" type="button" onClick={startNewConversation}>Reconnect</button></div>}
            {messages.map((message) => (
              <motion.article key={message.id} className={`message-row message-${message.role}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
                {message.role === 'admitcrew' && <span className="message-avatar"><Bot size={15} /></span>}
                {message.role === 'staff' && <span className="message-avatar"><GraduationCap size={15} /></span>}
                <div className="message-stack">
                  {message.role === 'admitcrew' && <span className="message-agent">{agentLabel(message.agent)}</span>}
                  {message.role === 'staff' && <span className="message-agent">{agentLabel(message.agent)}</span>}
                  <div className="message-bubble"><p>{message.text}</p></div>
                  <time>{new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(message.timestamp))}</time>
                </div>
              </motion.article>
            ))}
            {sending && <div className="message-row message-admitcrew typing-row"><span className="message-avatar"><Bot size={15} /></span><div className="message-stack"><span className="message-agent">Coordinator</span><div className="message-bubble typing-bubble" role="status" aria-label="AdmitCrew is responding"><i /><i /><i /></div></div></div>}
            <div ref={bottomRef} />
          </div>

          {error && messages.length > 0 && <div className="chat-inline-error" role="alert">{error}</div>}
          <form className="chat-composer" onSubmit={submitMessage}>
            <label className="sr-only" htmlFor="chat-message">Your message</label>
            <textarea
              id="chat-message"
              ref={composerRef}
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder="Ask about your study plans, programs, or next steps…"
              disabled={!sessionId || starting || sending}
            />
            <div className="composer-footer"><span>Enter to send <span className="keycap">↵</span><span className="composer-hint"> · Shift + Enter for a new line</span></span><button className="send-button" type="submit" aria-label="Send message" disabled={!draft.trim() || !sessionId || starting || sending}><ArrowUp size={18} /></button></div>
          </form>
          <p className="chat-disclaimer">AdmitCrew uses verified catalog information. Admissions decisions are made by universities.</p>
        </section>
      </div>
    </div>
  )
}
