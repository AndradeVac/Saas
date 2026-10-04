import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import { businessTypeLabels, slugify } from '../../lib/format'
import { APP_NAME, ROOT_DOMAIN, tenantUrl } from '../../lib/tenant'
import { apiErrorMessage } from '../../services/api'
import { checkSlug, signup } from '../../services/platform'
import type { BusinessType } from '../../types'

const schema = z.object({
  business_name: z.string().min(2, 'Informe o nome do estabelecimento.'),
  business_type: z.enum(['RESTAURANT', 'BAKERY', 'CAFE', 'SNACK_BAR', 'PIZZERIA', 'OTHER']),
  slug: z.string().min(3, 'Mínimo de 3 caracteres.'),
  admin_name: z.string().min(2, 'Informe seu nome.'),
  email: z.email('Informe um e-mail válido.'),
  password: z.string().min(8, 'A senha deve ter pelo menos 8 caracteres.'),
})
type FormValues = z.infer<typeof schema>

export function SignupPage() {
  const [serverError, setServerError] = useState('')
  const [slugState, setSlugState] = useState<{ available: boolean; reason: string | null } | null>(null)
  const [slugTouched, setSlugTouched] = useState(false)
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { business_type: 'RESTAURANT' },
  })
  const name = watch('business_name')
  const slug = watch('slug')

  // Suggest an address from the business name until the user edits it by hand.
  useEffect(() => {
    if (!slugTouched) setValue('slug', slugify(name ?? ''))
  }, [name, slugTouched, setValue])

  useEffect(() => {
    setSlugState(null)
    if (!slug || slug.length < 3) return
    const timer = window.setTimeout(() => {
      checkSlug(slug).then(setSlugState).catch(() => setSlugState(null))
    }, 400)
    return () => window.clearTimeout(timer)
  }, [slug])

  async function onSubmit(values: FormValues) {
    setServerError('')
    try {
      const created = await signup(values)
      window.location.href = tenantUrl(created.slug, '/login')
    } catch (error) {
      setServerError(apiErrorMessage(error, 'Não foi possível criar a conta. Tente novamente.'))
    }
  }

  return (
    <main className="center-page">
      <form className="card auth-card wide" onSubmit={handleSubmit(onSubmit)} noValidate>
        <strong className="landing-logo">{APP_NAME}</strong>
        <h1>Crie sua conta</h1>
        <p className="muted">Teste grátis. Em poucos minutos seu cardápio está no ar.</p>

        <label className="field">
          <span>Nome do estabelecimento</span>
          <input autoComplete="organization" autoFocus {...register('business_name')} />
          {errors.business_name && <small className="field-error">{errors.business_name.message}</small>}
        </label>

        <label className="field">
          <span>Tipo de negócio</span>
          <select {...register('business_type')}>
            {(Object.keys(businessTypeLabels) as BusinessType[]).map((type) => (
              <option key={type} value={type}>{businessTypeLabels[type]}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Endereço do seu cardápio</span>
          <div className="slug-input">
            <input {...register('slug', { onChange: () => setSlugTouched(true) })} />
            <span>.{ROOT_DOMAIN}</span>
          </div>
          {errors.slug && <small className="field-error">{errors.slug.message}</small>}
          {!errors.slug && slugState && (
            <small className={slugState.available ? 'field-ok' : 'field-error'}>
              {slugState.available ? '✓ Endereço disponível' : slugState.reason}
            </small>
          )}
        </label>

        <div className="grid-2">
          <label className="field">
            <span>Seu nome</span>
            <input autoComplete="name" {...register('admin_name')} />
            {errors.admin_name && <small className="field-error">{errors.admin_name.message}</small>}
          </label>
          <label className="field">
            <span>E-mail</span>
            <input type="email" autoComplete="email" {...register('email')} />
            {errors.email && <small className="field-error">{errors.email.message}</small>}
          </label>
        </div>

        <label className="field">
          <span>Senha</span>
          <input type="password" autoComplete="new-password" {...register('password')} />
          {errors.password && <small className="field-error">{errors.password.message}</small>}
        </label>

        {serverError && <div className="alert error" role="alert">{serverError}</div>}
        <button className="btn primary block large" type="submit" disabled={isSubmitting || slugState?.available === false}>
          {isSubmitting ? 'Criando…' : 'Criar conta'}
        </button>
        <Link className="center-link" to="/">← Voltar</Link>
      </form>
    </main>
  )
}
