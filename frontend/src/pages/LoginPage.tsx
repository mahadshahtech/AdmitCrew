import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Eye, EyeOff, GraduationCap, LockKeyhole, ShieldCheck } from 'lucide-react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { ApiError, errorMessage } from '../api'
import { useAuth } from '../auth'
import { LoadingState } from '../components/ui'

export function LoginPage() {
  const { staff, loading, signIn } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  if (loading) return <div className="auth-loading"><LoadingState label="Verifying staff session" /></div>
  if (staff) return <Navigate to={from?.startsWith('/staff') ? from : '/staff'} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    setError('')
    setSubmitting(true)
    try {
      await signIn(email.trim(), password)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        setError('That email and password combination was not recognized.')
      } else {
        setError(errorMessage(reason))
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-topbar">
        <Link to="/chat" className="brand-lockup public-brand"><span className="brand-mark"><GraduationCap size={21} /></span><span className="brand-name">Admit<span>Crew</span></span></Link>
        <Link to="/chat" className="back-to-chat"><ArrowLeft size={15} /> Student admissions chat</Link>
      </div>
      <div className="login-grid">
        <motion.section className="login-story" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.45 }}>
          <span className="eyebrow"><span className="eyebrow-mark" /> STAFF CONTROL CENTER</span>
          <h1>Every case.<br /><span>In good hands.</span></h1>
          <p>A quieter, clearer view of each student journey—from first conversation to final outcome.</p>
          <div className="login-story-foot"><span className="story-line" /><span>Admissions, in motion.</span></div>
        </motion.section>
        <motion.section className="login-form-panel" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.08 }}>
          <div className="login-form-heading"><span className="login-lock"><LockKeyhole size={18} /></span><p className="eyebrow">WELCOME BACK</p><h2>Staff sign in</h2><p>Use your AdmitCrew staff account to continue.</p></div>
          <form onSubmit={submit} className="form-stack">
            <div className="field-group"><label htmlFor="staff-email">Work email</label><input id="staff-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@admitcrew.com" required disabled={submitting} /></div>
            <div className="field-group"><label htmlFor="staff-password">Password</label><div className="password-field"><input id="staff-password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required disabled={submitting} /><button className="icon-button password-toggle" type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></div>
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="button button-primary login-submit" type="submit" disabled={submitting || !email.trim() || !password}>{submitting ? <><span className="spinner spinner-small" /> Verifying…</> : <>Sign in securely <ArrowRight size={16} /></>}</button>
          </form>
          <div className="login-security-note"><ShieldCheck size={15} /><span>Secure staff access · Admin and counselor roles</span></div>
        </motion.section>
      </div>
      <footer className="login-footer"><span>© AdmitCrew</span><span>For authorized staff only</span></footer>
    </main>
  )
}
