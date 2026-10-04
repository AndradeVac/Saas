import { zodResolver } from '@hookform/resolvers/zod'
import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { apiErrorMessage } from '../../services/api'
import { useTenant } from '../tenant/TenantProvider'
import { useAuth } from './AuthProvider'

const schema = z.object({
  username: z.email('Informe um e-mail válido.'),
  password: z.string().min(1, 'Informe a senha.'),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { tenant } = useTenant()
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(schema) })

  if (user) return <Navigate to={user.role === 'ADMIN' ? '/painel' : '/painel/pedidos'} replace />

  async function onSubmit(values: FormValues) {
    setServerError('')
    try {
      const loggedIn = await login(values)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? (loggedIn.role === 'ADMIN' ? '/painel' : '/painel/pedidos'), { replace: true })
    } catch (error) {
      setServerError(apiErrorMessage(error, 'Não foi possível entrar. Tente novamente.'))
    }
  }

  return (
    <main className="center-page">
      <form className="card auth-card" onSubmit={handleSubmit(onSubmit)} noValidate>
        <Brand name={tenant.name} logo={tenant.logo_url} />
        <h1>Entrar no painel</h1>
        <p className="muted">Acesso da equipe de {tenant.name}.</p>
        <label className="field">
          <span>E-mail</span>
          <input type="email" autoComplete="email" {...register('username')} />
          {errors.username && <small className="field-error">{errors.username.message}</small>}
        </label>
        <label className="field">
          <span>Senha</span>
          <div className="input-with-button">
            <input type={showPassword ? 'text' : 'password'} autoComplete="current-password" {...register('password')} />
            <button type="button" className="icon-btn" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}>
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {errors.password && <small className="field-error">{errors.password.message}</small>}
        </label>
        {serverError && <div className="alert error">{serverError}</div>}
        <button className="btn primary block" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Entrando…' : 'Entrar'}</button>
        <Link className="muted center-link" to="/">← Voltar ao cardápio</Link>
      </form>
    </main>
  )
}

export function Brand({ name, logo }: { name: string; logo: string | null }) {
  return (
    <div className="brand-mark">
      {logo ? <img src={logo} alt="" /> : <span className="brand-initial">{name.charAt(0).toUpperCase()}</span>}
      <strong>{name}</strong>
    </div>
  )
}
