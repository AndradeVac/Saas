// Uploaded images are stored by the API as "/media/<id>"; external links are used as they are.
const apiBaseUrl = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')

export function mediaUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined
  return url.startsWith('/media/') ? `${apiBaseUrl}${url}` : url
}
