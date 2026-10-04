import { ChevronLeft, ChevronRight } from 'lucide-react'

type Props = { page: number; pageSize: number; total: number; onChange: (page: number) => void }

export function Pagination({ page, pageSize, total, onChange }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div className="pagination">
      <span className="muted">{from}–{to} de {total}</span>
      <div>
        <button className="icon-btn bordered" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Página anterior"><ChevronLeft size={16} /></button>
        <span className="page-number">{page} / {pages}</span>
        <button className="icon-btn bordered" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Próxima página"><ChevronRight size={16} /></button>
      </div>
    </div>
  )
}
