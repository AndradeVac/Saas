import { Eye, EyeOff, MailCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { apiErrorMessage } from '../../services/api'
import { requestPasswordReset, resetPassword } from '../../services/auth'
import { useTenant } from '../tenant/TenantProvider'
import { Brand } from './LoginPage'

/** "Esqueci minha senha": asks for the e-mail and always answers the same (it never says if the e-mail exists). */
export function ForgotPasswordPage() {
  const { tenant } = useTenant()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Informe um e-mail válido.')
    setSending(true)
    try {
      await requestPasswordReset(email.trim())
      setSent(true)
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível enviar agora. Tente novamente em alguns minutos.'))
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="center-page">
      <form className="card auth-card" onSubmit={submit} noValidate>
        <Brand name={tenant.name} logo={tenant.logo_url} />
        {sent ? (
          <div className="success-hero">
            <div className="tick"><MailCheck size={28} /></div>
            <h1>Confira seu e-mail</h1>
            <p className="muted">Se <strong>{email.trim()}</strong> tiver acesso ao painel de {tenant.name}, enviamos um link para criar uma nova senha. Ele vale por 1 hora.</p>
            <p className="muted"><small>Não chegou? Veja a caixa de spam ou peça ajuda ao administrador da equipe.</small></p>
          </div>
        ) : (
          <>
            <h1>Esqueceu a senha?</h1>
            <p className="muted">Digite o e-mail que você usa para entrar. Vamos enviar um link para criar uma senha nova.</p>
            <label className="field">
              <span>E-mail</span>
              <input type="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            {error && <div className="alert error" role="alert">{error}</div>}
            <button className="btn primary block large" type="submit" disabled={sending}>{sending ? 'Enviando…' : 'Enviar link'}</button>
          </>
        )}
        <Link className="center-link" to="/login">← Voltar para o login</Link>
      </form>
    </main>
  )
}

/** Page opened from the e-mail link: /redefinir-senha?token=… */
export function ResetPasswordPage() {
  const { tenant } = useTenant()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (password.length < 8) return setError('A senha precisa ter pelo menos 8 caracteres.')
    if (password !== confirm) return setError('As senhas não conferem.')
    setSaving(true)
    try {
      await resetPassword(token, password)
      toast.success('Senha alterada! Entre com a nova senha.')
      navigate('/login', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível alterar a senha.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="center-page">
      <form className="card auth-card" onSubmit={submit} noValidate>
        <Brand name={tenant.name} logo={tenant.logo_url} />
        <h1>Criar nova senha</h1>
        {!token ? (
          <div className="alert error">Link incompleto. Abra o link do e-mail novamente ou <Link to="/esqueci-senha">peça um novo</Link>.</div>
        ) : (
          <>
            <label className="field">
              <span>Nova senha</span>
              <div className="input-with-button">
                <input type={show ? 'text' : 'password'} autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="icon-btn" onClick={() => setShow((v) => !v)} aria-label={show ? 'Ocultar senha' : 'Mostrar senha'}>
                  {show ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              <small className="muted">Pelo menos 8 caracteres.</small>
            </label>
            <label className="field">
              <span>Repita a nova senha</span>
              <input type={show ? 'text' : 'password'} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </label>
            {error && <div className="alert error" role="alert">{error}{error.includes('expirou') && <> <Link to="/esqueci-senha">Pedir novo link</Link></>}</div>}
            <button className="btn primary block large" type="submit" disabled={saving}>{saving ? 'Salvando…' : 'Salvar nova senha'}</button>
          </>
        )}
        <Link className="center-link" to="/login">← Voltar para o login</Link>
      </form>
    </main>
  )
}
