import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  Radio, Database, BrainCircuit, Server, MessagesSquare,
  LayoutDashboard, ArrowLeft, ChevronRight,
} from 'lucide-react'
import { BRAND_CONFIG } from '../brand.config'

// The live data flow behind StoreSight IQ, left -> right.
const STAGES = [
  {
    key: 'producer', icon: Radio, title: 'Real-Time Producer',
    sub: 'Zerobus streaming ingest', detail: 'POS + curbside events pushed to Delta',
  },
  {
    key: 'lakeflow', icon: Database, title: 'Lakeflow + Unity Catalog',
    sub: 'bronze → silver → gold', detail: 'Declarative pipeline + governed metric views',
  },
  {
    key: 'mosaic', icon: BrainCircuit, title: 'Mosaic AI',
    sub: '4 ML models (MLflow)', detail: 'Demand · Labor · Inventory · Prep — served',
  },
  {
    key: 'lakebase', icon: Server, title: 'Lakebase',
    sub: 'Postgres serving', detail: 'Sub-second reads + manager write-back',
  },
  {
    key: 'genie', icon: MessagesSquare, title: 'AI/BI Genie',
    sub: 'natural-language analytics', detail: 'Ask in English, grounded on the metric views',
  },
  {
    key: 'app', icon: LayoutDashboard, title: 'StoreSight IQ',
    sub: 'Databricks App', detail: 'Ops · Forecast · Labor · Inventory · Fresh Production',
  },
]

function useLiveStats() {
  const [stats, setStats] = useState<{ stores?: number; events?: number; genie?: string }>({})
  useEffect(() => {
    const load = async () => {
      try {
        const s = await fetch('/api/stores/').then((r) => r.json())
        const stores = Array.isArray(s) ? s.length : (s.stores?.length ?? s.count)
        const g = await fetch('/api/genie/status').then((r) => r.json()).catch(() => ({}))
        let events
        try {
          const e = await fetch('/api/operations/events/1').then((r) => r.json())
          events = e.event_count
        } catch { /* ignore */ }
        setStats({ stores, events, genie: g.configured ? 'connected' : g.status })
      } catch { /* ignore */ }
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])
  return stats
}

export default function Architecture() {
  const stats = useLiveStats()

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-surface-secondary to-green-50">
      {/* Header */}
      <header className="border-b border-black/5 bg-white/70 backdrop-blur">
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src={BRAND_CONFIG.markSrc} alt={BRAND_CONFIG.customerName} className="h-8 w-8" />
            <div>
              <p className="font-semibold text-navy-900 leading-tight">{BRAND_CONFIG.productName}</p>
              <p className="text-xs text-gray-500 leading-tight">{BRAND_CONFIG.customerName} · Live Architecture</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <span className="hidden sm:flex items-center gap-2 text-xs font-medium text-gray-500">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
              </span>
              LIVE
            </span>
            <img src="/databricks-logo.svg" alt="Databricks" className="h-5" />
            <Link to="/" className="flex items-center gap-1 text-sm text-gray-500 hover:text-brand-primary">
              <ArrowLeft className="h-4 w-4" /> Back
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-bold text-navy-900">How {BRAND_CONFIG.customerName} labor forecasting flows</h1>
          <p className="mt-2 text-gray-600 max-w-3xl">
            Real-time store signals become an ML-driven staffing recommendation and a natural-language
            answer — end to end on Databricks. Data flows left to right, live.
          </p>

          {/* Live stat chips */}
          <div className="mt-6 flex flex-wrap gap-3">
            <Stat label="Stores" value={stats.stores != null ? String(stats.stores) : '—'} />
            <Stat label="ML models served" value="4" />
            <Stat label="Live events (store 1)" value={stats.events != null ? String(stats.events) : '—'} />
            <Stat label="Genie" value={stats.genie ?? '—'} />
          </div>
        </motion.div>

        {/* Flow */}
        <div className="mt-12 flex flex-col lg:flex-row lg:items-stretch gap-4 lg:gap-0">
          {STAGES.map((s, i) => (
            <div key={s.key} className="flex flex-col lg:flex-row lg:items-center flex-1 min-w-0">
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: i * 0.12 }}
                className="flex-1 rounded-2xl border border-black/5 bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-primary/10 text-brand-primary">
                    <s.icon className="h-6 w-6" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-navy-900 leading-tight">{s.title}</p>
                    <p className="text-xs text-brand-primary font-medium">{s.sub}</p>
                  </div>
                </div>
                <p className="mt-3 text-sm text-gray-500 leading-snug">{s.detail}</p>
              </motion.div>

              {/* Connector with an animated flowing dot */}
              {i < STAGES.length - 1 && (
                <div className="relative flex items-center justify-center lg:w-10 h-8 lg:h-auto lg:self-center">
                  <div className="hidden lg:block h-0.5 w-full bg-gradient-to-r from-brand-primary/30 to-brand-primary/30" />
                  <div className="lg:hidden w-0.5 h-full bg-brand-primary/30" />
                  <motion.div
                    className="absolute h-2.5 w-2.5 rounded-full bg-brand-primary shadow"
                    animate={{ x: ['-14px', '14px'], opacity: [0, 1, 1, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut', delay: i * 0.2 }}
                  />
                  <ChevronRight className="hidden lg:block absolute right-0 h-4 w-4 text-brand-primary/50" />
                </div>
              )}
            </div>
          ))}
        </div>

        <p className="mt-12 text-center text-sm text-gray-400">
          Powered by Databricks · Zerobus · Lakeflow · Unity Catalog · Mosaic AI · Lakebase · AI/BI Genie
        </p>
      </main>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-black/5 bg-white px-4 py-2.5 shadow-sm">
      <p className="text-[11px] uppercase tracking-wide text-gray-400">{label}</p>
      <p className="text-lg font-semibold text-navy-900 leading-tight">{value}</p>
    </div>
  )
}
