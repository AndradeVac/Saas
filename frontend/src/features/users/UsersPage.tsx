import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { apiErrorMessage } from '../../services/api'
import { createUser, getUsers, setUserActive, type TeamUser } from '../../services/admin'
import type { UserRole } from '../../types'

export function UsersPage() {
  const [users, setUsers] = useState<TeamUser[]>([])
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'OPERATOR' as UserRole })
  const [error, setError] = useState('')

  const load = () => getUsers().then(setUsers).catch(() => setError('Não foi possível carregar a equipe.'))
  useEffect(() => { void load() }, [])

  async function add(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await createUser(form)
      setForm({ name: '', email: '', password: '', role: 'OPERATOR' })
      toast.success('Usuário criado.')
      await load()
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível criar o usuário.'))
    }
  }

  async function toggle(user: TeamUser) {
    try {
      await setUserActive(user.id, !user.active)
      await load()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Não foi possível alterar o usuário.'))
    }
  }

  return (
    <section className="page narrow">
      <div className="page-head"><div><h1>Equipe</h1><p className="muted">Quem acessa o painel. Operadores só cuidam dos pedidos.</p></div></div>
      {error && <div className="alert error">{error}</div>}
      <form className="card" onSubmit={add}>
        <h3>Novo usuário</h3>
        <div className="grid-2">
          <label className="field"><span>Nome</span><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label className="field"><span>E-mail</span><input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label className="field"><span>Senha (mín. 8)</span><input required minLength={8} type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          <label className="field"><span>Perfil</span>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
              <option value="OPERATOR">Operador</option>
              <option value="ADMIN">Administrador</option>
            </select>
          </label>
        </div>
        <button className="btn primary">Criar usuário</button>
      </form>
      <div className="card list">
        {users.map((u) => (
          <div className={`list-row ${u.active ? '' : 'muted-row'}`} key={u.id}>
            <div><strong>{u.name}</strong><span>{u.email} · {u.role === 'ADMIN' ? 'Administrador' : 'Operador'}</span></div>
            <button className="btn small" onClick={() => void toggle(u)}>{u.active ? 'Desativar' : 'Reativar'}</button>
          </div>
        ))}
      </div>
    </section>
  )
}
