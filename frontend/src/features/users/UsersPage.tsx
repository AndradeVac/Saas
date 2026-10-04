import { KeyRound, Pencil, Plus } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { useConfirm } from '../../components/ui/Confirm'
import { Modal } from '../../components/ui/Modal'
import { ErrorBanner, PageHeader, Skeleton } from '../../components/ui/parts'
import { apiErrorMessage } from '../../services/api'
import { createUser, getUsers, resetUserPassword, setUserActive, updateUser, type TeamUser } from '../../services/people'
import type { UserRole } from '../../types'
import { useAuth } from '../auth/AuthProvider'

type Dialog =
  | { kind: 'create'; name: string; email: string; password: string; role: UserRole }
  | { kind: 'edit'; user: TeamUser; name: string; role: UserRole }
  | { kind: 'password'; user: TeamUser; password: string }
  | null

const roleLabels: Record<UserRole, string> = { ADMIN: 'Administrador', OPERATOR: 'Operador' }

export function UsersPage() {
  const confirm = useConfirm()
  const { user: me } = useAuth()
  const [users, setUsers] = useState<TeamUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState<Dialog>(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => getUsers()
    .then((u) => { setUsers(u); setError('') })
    .catch(() => setError('Não foi possível carregar a equipe.'))
    .finally(() => setLoading(false)), [])
  useEffect(() => { void load() }, [load])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!dialog) return
    setSaving(true)
    setFormError('')
    try {
      if (dialog.kind === 'create') {
        await createUser({ name: dialog.name, email: dialog.email, password: dialog.password, role: dialog.role })
        toast.success('Usuário criado')
      } else if (dialog.kind === 'edit') {
        await updateUser(dialog.user.id, { name: dialog.name, role: dialog.role })
        toast.success('Usuário atualizado')
      } else {
        await resetUserPassword(dialog.user.id, dialog.password)
        toast.success('Senha redefinida')
      }
      setDialog(null)
      await load()
    } catch (err) {
      setFormError(apiErrorMessage(err, 'Não foi possível concluir.'))
    } finally {
      setSaving(false)
    }
  }

  async function toggle(user: TeamUser) {
    if (user.active) {
      const result = await confirm({
        title: `Desativar ${user.name}?`,
        message: 'Essa pessoa perde o acesso ao painel imediatamente. Você pode reativar depois.',
        confirmLabel: 'Desativar',
        danger: true,
      })
      if (!result.ok) return
    }
    try {
      await setUserActive(user.id, !user.active)
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar o usuário.'))
    }
  }

  const title = dialog?.kind === 'create' ? 'Novo usuário' : dialog?.kind === 'edit' ? 'Editar usuário' : `Nova senha de ${dialog?.user.name}`

  return (
    <section className="page narrow">
      <PageHeader
        title="Equipe"
        subtitle="Quem acessa o painel. Operadores cuidam dos pedidos; administradores controlam tudo."
        actions={<button className="btn primary" onClick={() => { setFormError(''); setDialog({ kind: 'create', name: '', email: '', password: '', role: 'OPERATOR' }) }}><Plus size={16} /> Novo usuário</button>}
      />
      <ErrorBanner message={error} onRetry={() => void load()} />
      <div className="card" style={{ padding: '4px 20px' }}>
        {loading ? <Skeleton lines={3} height={44} /> : users.map((u) => (
          <div className={`list-row ${u.active ? '' : 'off'}`} key={u.id}>
            <div>
              <strong>{u.name} {u.id === me?.id && <span className="badge">você</span>}</strong>
              <small>{u.email} · {roleLabels[u.role]}{!u.active && ' · desativado'}</small>
            </div>
            <div className="row-actions">
              <button className="icon-btn" onClick={() => { setFormError(''); setDialog({ kind: 'edit', user: u, name: u.name, role: u.role }) }} aria-label={`Editar ${u.name}`}><Pencil size={16} /></button>
              <button className="icon-btn" onClick={() => { setFormError(''); setDialog({ kind: 'password', user: u, password: '' }) }} aria-label={`Redefinir senha de ${u.name}`}><KeyRound size={16} /></button>
              {u.id !== me?.id && <button className="btn small" onClick={() => void toggle(u)}>{u.active ? 'Desativar' : 'Reativar'}</button>}
            </div>
          </div>
        ))}
      </div>

      {dialog && (
        <Modal
          title={title}
          size="sm"
          onClose={() => setDialog(null)}
          footer={<><button type="button" className="btn" onClick={() => setDialog(null)}>Cancelar</button><button type="submit" form="user-form" className="btn primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button></>}
        >
          <form id="user-form" onSubmit={submit}>
            {formError && <div className="alert error" role="alert">{formError}</div>}
            {dialog.kind !== 'password' && (
              <label className="field"><span>Nome</span><input required autoFocus value={dialog.name} onChange={(e) => setDialog({ ...dialog, name: e.target.value })} /></label>
            )}
            {dialog.kind === 'create' && (
              <label className="field"><span>E-mail</span><input required type="email" value={dialog.email} onChange={(e) => setDialog({ ...dialog, email: e.target.value })} /></label>
            )}
            {(dialog.kind === 'create' || dialog.kind === 'password') && (
              <label className="field"><span>{dialog.kind === 'create' ? 'Senha inicial' : 'Nova senha'} (mín. 8 caracteres)</span>
                <input required minLength={8} type="password" autoComplete="new-password" autoFocus={dialog.kind === 'password'} value={dialog.password} onChange={(e) => setDialog({ ...dialog, password: e.target.value })} />
              </label>
            )}
            {dialog.kind !== 'password' && (
              <label className="field"><span>Perfil</span>
                <select value={dialog.role} onChange={(e) => setDialog({ ...dialog, role: e.target.value as UserRole })}>
                  <option value="OPERATOR">Operador — pedidos e clientes</option>
                  <option value="ADMIN">Administrador — acesso total</option>
                </select>
              </label>
            )}
          </form>
        </Modal>
      )}
    </section>
  )
}
