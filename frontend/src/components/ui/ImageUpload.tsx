import { ImagePlus, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { mediaUrl } from '../../lib/media'
import { apiErrorMessage } from '../../services/api'
import { uploadImage } from '../../services/tenant'

type Props = {
  value: string | null
  onChange: (url: string | null) => void
  label: string
  /** Visual shape of the preview: square thumbnail or wide banner. */
  shape?: 'square' | 'banner'
  hint?: string
}

/** Click-to-upload image field. Files go to the API (resized and compressed there). */
export function ImageUpload({ value, onChange, label, shape = 'square', hint }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  async function pick(file: File | undefined) {
    if (!file) return
    setBusy(true)
    try {
      const result = await uploadImage(file)
      onChange(result.url)
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Não foi possível enviar a imagem.'))
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <div className="field">
      <span>{label}</span>
      <div className={`image-upload ${shape}`}>
        <button type="button" className="image-drop" onClick={() => input.current?.click()} disabled={busy} aria-label={`Enviar ${label}`}>
          {value ? <img src={mediaUrl(value)} alt="" /> : <ImagePlus size={24} />}
          <em>{busy ? 'Enviando…' : value ? 'Trocar' : 'Enviar foto'}</em>
        </button>
        {value && (
          <button type="button" className="btn small ghost" onClick={() => onChange(null)}>
            <Trash2 size={14} /> Remover
          </button>
        )}
      </div>
      {hint && <small className="muted">{hint}</small>}
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => void pick(e.target.files?.[0])} />
    </div>
  )
}
