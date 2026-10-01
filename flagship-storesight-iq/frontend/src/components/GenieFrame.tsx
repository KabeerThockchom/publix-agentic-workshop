import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import { api } from '../api/client'
import { BRAND_CONFIG } from '../brand.config'

/**
 * Persistent Genie iframe.
 *
 * The iframe is mounted ONCE at the app root (outside <Routes>) so it survives
 * route changes — navigating between the Map and Compare tabs no longer unmounts
 * it, so the Genie chat session is preserved. Only a hard browser refresh resets it.
 *
 * It loads on app startup (hidden, off-screen) so it's already warm by the time the
 * user opens the Compare tab. When Compare mounts, it registers an "anchor" element
 * (a placeholder div) and the persistent iframe is positioned to overlay that anchor,
 * tracking its position on scroll/resize and clipping to the visible viewport band.
 */

interface GenieAnchorContextValue {
  setAnchor: (el: HTMLElement | null) => void
}

const GenieAnchorContext = createContext<GenieAnchorContextValue>({ setAnchor: () => {} })

export const useGenieAnchor = () => useContext(GenieAnchorContext)

// Height of the sticky top nav (h-16 = 64px) — used to clip the iframe so it
// tucks under the header instead of floating over it while scrolling.
const HEADER_OFFSET = 64

export function GenieProvider({ children }: { children: ReactNode }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [embedUrl, setEmbedUrl] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef<number | undefined>(undefined)

  // Fetch the embed URL once on startup so the iframe begins loading immediately.
  useEffect(() => {
    let cancelled = false
    api.getGenieStatus()
      .then((s) => { if (!cancelled) setEmbedUrl(s?.embed_url || null) })
      .catch(() => { /* leave null → nothing to embed */ })
    return () => { cancelled = true }
  }, [])

  // Position the persistent iframe: overlay the anchor when present, otherwise
  // park it off-screen (still mounted + loaded, so the session stays alive).
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const stop = () => {
      if (rafRef.current !== undefined) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = undefined
      }
    }

    if (!anchor) {
      // Hidden state: keep rendered + loaded, but off-screen and non-interactive.
      stop()
      el.style.pointerEvents = 'none'
      el.style.transform = 'translate(-200vw, 0)'
      el.style.clipPath = 'none'
      el.style.top = '0px'
      el.style.left = '0px'
      el.style.width = '1024px'
      el.style.height = '700px'
      return
    }

    // Visible state: track the anchor's rect every frame and clip to the viewport.
    el.style.pointerEvents = 'auto'
    el.style.transform = 'none'

    let last = ''
    const sync = () => {
      const r = anchor.getBoundingClientRect()
      const clipTop = Math.max(0, HEADER_OFFSET - r.top)
      const clipBottom = Math.max(0, r.bottom - window.innerHeight)
      const key = `${r.top}|${r.left}|${r.width}|${r.height}|${clipTop}|${clipBottom}`
      if (key !== last) {
        last = key
        el.style.top = `${r.top}px`
        el.style.left = `${r.left}px`
        el.style.width = `${r.width}px`
        el.style.height = `${r.height}px`
        el.style.clipPath = `inset(${clipTop}px 0px ${clipBottom}px 0px)`
      }
      rafRef.current = requestAnimationFrame(sync)
    }
    sync()
    return stop
  }, [anchor])

  return (
    <GenieAnchorContext.Provider value={{ setAnchor }}>
      {children}
      {/* The single, persistent Genie iframe. Never unmounted. */}
      <div
        ref={containerRef}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          zIndex: 30,
          transform: 'translate(-200vw, 0)',
          pointerEvents: 'none',
          overflow: 'hidden',
          borderBottomLeftRadius: '1rem',
          borderBottomRightRadius: '1rem',
        }}
      >
        {embedUrl && (
          <iframe
            src={embedUrl}
            title={`${BRAND_CONFIG.customerName} Store Analytics — Genie`}
            style={{ width: '100%', height: '100%', border: 0 }}
            allow="clipboard-write"
          />
        )}
      </div>
    </GenieAnchorContext.Provider>
  )
}
