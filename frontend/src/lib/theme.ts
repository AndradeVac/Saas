// Applies a tenant's brand color as CSS variables (--brand, --brand-ink).
export function applyBrand(color: string) {
  const hex = /^#[0-9a-f]{6}$/i.test(color) ? color : '#c2410c'
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  const luminance = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  const root = document.documentElement.style
  root.setProperty('--brand', hex)
  root.setProperty('--brand-ink', luminance > 0.5 ? '#1c1917' : '#ffffff')
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', hex)
}
