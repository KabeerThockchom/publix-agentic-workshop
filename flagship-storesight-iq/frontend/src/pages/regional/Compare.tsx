import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { brand } from '../../brand'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  BarChart3, MessageSquare, Sparkles, ExternalLink,
  TrendingUp, TrendingDown, ChevronDown, ChevronUp,
  DollarSign, Percent, Loader2
} from 'lucide-react'
import { api } from '../../api/client'
import { Card, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { useGenieAnchor } from '../../components/GenieFrame'

// Height reserved for the embedded Genie iframe (matches GenieFrame overlay).
const GENIE_HEIGHT = 640

export default function Compare() {
  const palette = brand()
  const [expandedTopPerformer, setExpandedTopPerformer] = useState<number | null>(null)
  const [expandedNeedsAttention, setExpandedNeedsAttention] = useState<number | null>(null)

  // Register this page's placeholder as the anchor for the persistent Genie iframe.
  // The iframe itself lives at the app root (GenieProvider) so it survives tab
  // changes; here we just tell it where to render. Clearing on unmount parks it
  // off-screen (still loaded) so the chat session is preserved.
  const { setAnchor } = useGenieAnchor()
  const genieAnchorRef = useCallback((node: HTMLElement | null) => {
    setAnchor(node)
  }, [setAnchor])

  const { data: stores, isLoading: loadingStores } = useQuery({
    queryKey: ['stores'],
    queryFn: () => api.getStores(),
  })

  const { data: genieStatus } = useQuery({
    queryKey: ['genie-status'],
    queryFn: () => api.getGenieStatus(),
  })

  // Embed URL for the Genie space (built server-side in /genie/status).
  const genieEmbedUrl: string | undefined = genieStatus?.embed_url || undefined

  // Top performers for chart - sorted by weekly sales in descending order
  const chartData = stores?.stores
    ? [...stores.stores]
        .sort((a: any, b: any) => (b.sales_wtd || 0) - (a.sales_wtd || 0))
        .slice(0, 10)
        .map((s: any, index: number) => ({
          name: s.name.split(' - ')[0],
          fullName: s.name,
          sales: s.sales_wtd || 0,
          rank: index + 1,
          store_id: s.store_id,
        }))
    : []
  
  // Sort stores for top performers (by vs_forecast_pct descending)
  const topPerformers = stores?.stores
    ? [...stores.stores]
        .sort((a: any, b: any) => (b.vs_forecast_pct || 0) - (a.vs_forecast_pct || 0))
        .slice(0, 5)
    : []
  
  // Sort stores for needs attention (by vs_forecast_pct ascending - worst performers)
  const needsAttention = stores?.stores
    ? [...stores.stores]
        .sort((a: any, b: any) => (a.vs_forecast_pct || 0) - (b.vs_forecast_pct || 0))
        .slice(0, 5)
    : []

  const formatCurrency = (value: number) => 
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-text-primary">Compare & Analyze</h2>
        <p className="text-text-secondary">Store rankings and AI-powered insights</p>
      </div>

      {/* AI Insights — Embedded Genie */}
      <Card padding="none">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-secondary to-brand-secondary-light flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-text-primary">AI Insights</h3>
                <p className="text-sm text-text-secondary">Ask questions about your store data</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {genieEmbedUrl && (
                <a
                  href={genieEmbedUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-dark transition-colors"
                >
                  Open in new tab
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
              <Badge variant={genieStatus?.configured ? 'success' : 'warning'}>
                {genieStatus?.configured ? 'Genie Connected' : 'Demo Mode'}
              </Badge>
            </div>
          </div>
        </div>

        {/* Anchor for the persistent Genie iframe (mounted once at the app root).
            The iframe is positioned to overlay this placeholder, so navigating away
            and back preserves the Genie chat session — only a hard refresh resets it. */}
        {genieEmbedUrl ? (
          <div ref={genieAnchorRef} style={{ height: GENIE_HEIGHT }} />
        ) : (
          <div className="h-96 flex flex-col items-center justify-center text-center p-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-100 to-blue-100 flex items-center justify-center mb-4">
              <MessageSquare className="w-8 h-8 text-purple-500" />
            </div>
            <h4 className="font-medium text-text-primary mb-2">Genie not configured</h4>
            <p className="text-sm text-text-secondary max-w-sm">
              Set the Genie Space ID (and ensure external embedding is enabled on the workspace)
              to load the embedded AI Insights assistant here.
            </p>
          </div>
        )}
      </Card>

      {/* Performance Chart */}
      <Card>
        <CardHeader
          title="Top 10 Weekly Sales Performance"
          subtitle="Week-to-date sales by store (ranked)"
          icon={<BarChart3 className="w-5 h-5" />}
        />
        <AnimatePresence mode="wait">
          {loadingStores ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-64 flex flex-col items-center justify-center"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Loader2 className="w-8 h-8 text-brand-primary" />
              </motion.div>
              <p className="text-sm text-text-secondary mt-3">Loading store data from Databricks SQL Warehouse...</p>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="h-64"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis type="number" tickFormatter={(value) => `$${(value/1000).toFixed(0)}k`} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={130}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(value: number) => [`$${value.toLocaleString()}`, 'Weekly Sales']}
                    labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: 'none',
                      borderRadius: '12px',
                      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
                    }}
                  />
                  <Bar
                    dataKey="sales"
                    fill={palette.primary}
                    radius={[0, 6, 6, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>

      {/* Store Comparison Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Top Performers */}
        <Card>
          <CardHeader 
            title="Top Performers" 
            subtitle="Best performing vs forecast"
            icon={<TrendingUp className="w-5 h-5" />}
          />
          <div className="space-y-3">
            {topPerformers.map((store: any, index: number) => (
              <motion.div
                key={store.store_id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="rounded-xl overflow-hidden"
              >
                <div 
                  className="flex items-center gap-4 p-3 bg-green-50 cursor-pointer hover:bg-green-100 transition-colors"
                  onClick={() => setExpandedTopPerformer(
                    expandedTopPerformer === store.store_id ? null : store.store_id
                  )}
                >
                  <div className="w-10 h-10 rounded-xl bg-green-500 text-white flex items-center justify-center font-bold flex-shrink-0">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary truncate">{store.name}</p>
                    <p className="text-sm text-text-secondary">
                      +{store.vs_forecast_pct?.toFixed(1) || 0}% vs forecast
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="font-semibold text-green-600">
                      ${store.sales_today?.toLocaleString() || 0}
                    </p>
                    <p className="text-xs text-text-tertiary">today</p>
                  </div>
                  <div className="ml-2 flex-shrink-0">
                    {expandedTopPerformer === store.store_id ? (
                      <ChevronUp className="w-5 h-5 text-green-600" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-green-600" />
                    )}
                  </div>
                </div>
                
                {/* Expanded KPI Details */}
                <AnimatePresence>
                  {expandedTopPerformer === store.store_id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="p-4 bg-green-50/50 border-t border-green-100">
                        <div className="grid grid-cols-3 gap-3">
                          <div className="bg-white rounded-lg p-3 text-center">
                            <div className="flex items-center justify-center gap-1 text-green-600 mb-1">
                              <DollarSign className="w-3 h-3" />
                              <span className="text-xs font-medium">Weekly</span>
                            </div>
                            <p className="text-base font-bold text-text-primary">
                              {formatCurrency(store.sales_wtd || 0)}
                            </p>
                          </div>
                          <div className="bg-white rounded-lg p-3 text-center">
                            <div className="flex items-center justify-center gap-1 text-blue-600 mb-1">
                              <DollarSign className="w-3 h-3" />
                              <span className="text-xs font-medium">Monthly</span>
                            </div>
                            <p className="text-base font-bold text-text-primary">
                              {formatCurrency(store.sales_mtd || 0)}
                            </p>
                          </div>
                          <div className="bg-white rounded-lg p-3 text-center">
                            <div className="flex items-center justify-center gap-1 text-amber-600 mb-1">
                              <Percent className="w-3 h-3" />
                              <span className="text-xs font-medium">Labor %</span>
                            </div>
                            <p className="text-base font-bold text-text-primary">
                              {(store.labor_cost_pct || 0).toFixed(1)}%
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 flex items-center justify-between text-sm">
                          <span className="text-text-secondary">Regional Rank</span>
                          <Badge variant="success">#{store.rank || '?'} of 25</Badge>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </Card>

        {/* Needs Attention */}
        <Card>
          <CardHeader 
            title="Needs Attention" 
            subtitle="Underperforming vs forecast"
            icon={<TrendingDown className="w-5 h-5" />}
          />
          <div className="space-y-3">
            {needsAttention.map((store: any, index: number) => (
              <motion.div
                key={store.store_id}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="rounded-xl overflow-hidden"
              >
                <div 
                  className="flex items-center gap-4 p-3 bg-red-50 cursor-pointer hover:bg-red-100 transition-colors"
                  onClick={() => setExpandedNeedsAttention(
                    expandedNeedsAttention === store.store_id ? null : store.store_id
                  )}
                >
                  <div className="w-10 h-10 rounded-xl bg-red-100 text-red-600 flex items-center justify-center font-bold flex-shrink-0">
                    {store.rank || 25}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary truncate">{store.name}</p>
                    <p className="text-sm text-text-secondary">
                      {store.vs_forecast_pct?.toFixed(1) || 0}% vs forecast
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="font-semibold text-red-600">
                      ${store.sales_today?.toLocaleString() || 0}
                    </p>
                    <p className="text-xs text-text-tertiary">today</p>
                  </div>
                  <div className="ml-2 flex-shrink-0">
                    {expandedNeedsAttention === store.store_id ? (
                      <ChevronUp className="w-5 h-5 text-red-600" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-red-600" />
                    )}
                  </div>
                </div>
                
                {/* Expanded KPI Details */}
                <AnimatePresence>
                  {expandedNeedsAttention === store.store_id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="p-4 bg-red-50/50 border-t border-red-100">
                        <div className="grid grid-cols-3 gap-3">
                          <div className="bg-white rounded-lg p-3 text-center">
                            <div className="flex items-center justify-center gap-1 text-red-600 mb-1">
                              <DollarSign className="w-3 h-3" />
                              <span className="text-xs font-medium">Weekly</span>
                            </div>
                            <p className="text-base font-bold text-text-primary">
                              {formatCurrency(store.sales_wtd || 0)}
                            </p>
                          </div>
                          <div className="bg-white rounded-lg p-3 text-center">
                            <div className="flex items-center justify-center gap-1 text-blue-600 mb-1">
                              <DollarSign className="w-3 h-3" />
                              <span className="text-xs font-medium">Monthly</span>
                            </div>
                            <p className="text-base font-bold text-text-primary">
                              {formatCurrency(store.sales_mtd || 0)}
                            </p>
                          </div>
                          <div className="bg-white rounded-lg p-3 text-center">
                            <div className="flex items-center justify-center gap-1 text-amber-600 mb-1">
                              <Percent className="w-3 h-3" />
                              <span className="text-xs font-medium">Labor %</span>
                            </div>
                            <p className="text-base font-bold text-text-primary">
                              {(store.labor_cost_pct || 0).toFixed(1)}%
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 flex items-center justify-between text-sm">
                          <span className="text-text-secondary">Regional Rank</span>
                          <Badge variant="error">#{store.rank || '?'} of 25</Badge>
                        </div>
                        <div className="mt-2 p-2 bg-red-100 rounded-lg text-xs text-red-700">
                          <span className="font-medium">Action needed:</span> Review staffing and inventory levels
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}


