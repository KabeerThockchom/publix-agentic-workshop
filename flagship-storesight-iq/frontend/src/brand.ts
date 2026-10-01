/**
 * Brand palette resolved from the CSS custom properties in index.css (:root).
 *
 * Charts (recharts) and inline SVG need real color strings, not Tailwind
 * classes. Reading them from the same CSS variables that drive the `brand-*`
 * Tailwind tokens keeps every color in sync with the SINGLE-SOURCE palette —
 * so a re-skin only edits index.css :root (which is all generate.py rewrites).
 *
 * Resolved lazily on first use (after the stylesheet is applied) and memoized.
 * Fallbacks are the neutral reference-QSR palette, matching index.css defaults.
 */

let _palette: BrandPalette | null = null

export interface BrandPalette {
  primary: string
  primaryDark: string
  primaryLight: string
  secondary: string
  secondaryDark: string
  secondaryLight: string
  /** Ordered series colors for categorical charts. */
  series: string[]
}

function readVar(name: string, fallback: string): string {
  if (typeof window === 'undefined' || !document?.documentElement) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export function brand(): BrandPalette {
  if (_palette) return _palette
  const primary = readVar('--brand-primary', '#2D6BE0')
  const primaryDark = readVar('--brand-primary-dark', '#1F4FAD')
  const primaryLight = readVar('--brand-primary-light', '#5A8DEB')
  const secondary = readVar('--brand-secondary', '#F5A623')
  const secondaryDark = readVar('--brand-secondary-dark', '#D18B12')
  const secondaryLight = readVar('--brand-secondary-light', '#F8BD57')
  _palette = {
    primary,
    primaryDark,
    primaryLight,
    secondary,
    secondaryDark,
    secondaryLight,
    series: [primary, primaryLight, secondary, secondaryLight],
  }
  return _palette
}
