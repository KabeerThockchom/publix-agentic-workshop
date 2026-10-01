import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { 
  DollarSign, ShoppingCart, Users, TrendingUp, 
  AlertTriangle, Clock, ChevronRight, Wind, Loader2,
  Calendar, Ticket, MapPin, ExternalLink
} from 'lucide-react'
import { useOutletContext, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { BRAND_CONFIG } from '../../brand.config'
import { Card, CardHeader, StatCard } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { SalesChart } from '../../components/charts/SalesChart'
import { ChannelBreakdown } from '../../components/charts/ChannelChart'

interface StoreContext {
  storeId: number
  storeName: string
}

interface Transaction {
  txn_id: string
  timestamp: string
  items: string[]
  total: number
  channel: string
  payment_method: string
}

// Track incremental data from new transactions during the session
interface IncrementalData {
  sales: number
  transactions: number
  channels: Record<string, number>
}

// Loading component with Databricks branding
const LoadingState = ({ message = "Retrieving data from Databricks..." }: { message?: string }) => (
  <motion.div 
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="flex flex-col items-center justify-center py-8 gap-3"
  >
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    >
      <Loader2 className="w-8 h-8 text-brand-primary" />
    </motion.div>
    <div className="text-center">
      <p className="text-sm text-text-secondary">{message}</p>
      <motion.div 
        className="flex items-center justify-center gap-1 mt-2"
        initial={{ opacity: 0.5 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-brand-primary" />
        <span className="w-1.5 h-1.5 rounded-full bg-brand-primary/60" />
        <span className="w-1.5 h-1.5 rounded-full bg-brand-primary/30" />
      </motion.div>
    </div>
  </motion.div>
)

// Skeleton loader for stat cards
const StatCardSkeleton = () => (
  <motion.div 
    className="bg-white rounded-2xl p-5 shadow-soft"
    initial={{ opacity: 0.6 }}
    animate={{ opacity: 1 }}
    transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
  >
    <div className="flex items-start justify-between">
      <div className="space-y-3 flex-1">
        <div className="h-3 w-20 bg-gray-200 rounded animate-pulse" />
        <div className="h-8 w-24 bg-gray-200 rounded animate-pulse" />
        <div className="h-2 w-16 bg-gray-100 rounded animate-pulse" />
      </div>
      <div className="w-10 h-10 bg-gray-100 rounded-xl animate-pulse" />
    </div>
  </motion.div>
)

export default function Operations() {
  const { storeId } = useOutletContext<StoreContext>()
  const navigate = useNavigate()
  
  // Get user's local hour for time-aware data generation
  // Include in query key to ensure fresh data when hour changes
  const localHour = useMemo(() => new Date().getHours(), [])

  // Base summary data - fetched once per store/date, NO periodic refresh
  const { data: baseSummary, isLoading: loadingSummary } = useQuery({
    queryKey: ['operations-summary', storeId, localHour],
    queryFn: () => api.getOperationsSummary(storeId),
    staleTime: Infinity, // Never refetch automatically - data is consistent for the day
    refetchOnWindowFocus: false,
  })

  const { data: hourlyData, isLoading: loadingHourly } = useQuery({
    queryKey: ['hourly-sales', storeId, localHour],
    queryFn: () => api.getHourlySales(storeId),
    staleTime: Infinity, // Never refetch automatically
    refetchOnWindowFocus: false,
  })

  // Get today's date for session storage key (data resets each day)
  const todayKey = useMemo(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  }, [])
  
  // Session storage key for this store+date combo
  const storageKey = useMemo(() => `ops_incremental_${storeId}_${todayKey}`, [storeId, todayKey])
  
  // Load incremental data from session storage on mount (persists within browser session)
  const [incrementalData, setIncrementalData] = useState<IncrementalData>(() => {
    try {
      const stored = sessionStorage.getItem(storageKey)
      if (stored) {
        return JSON.parse(stored)
      }
    } catch (e) {
      console.warn('Failed to load incremental data from session storage:', e)
    }
    return {
      sales: 0,
      transactions: 0,
      channels: { in_store: 0, delivery: 0, app: 0, third_party: 0 }
    }
  })
  
  // Persist incremental data to session storage whenever it changes
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(incrementalData))
    } catch (e) {
      console.warn('Failed to save incremental data to session storage:', e)
    }
  }, [incrementalData, storageKey])

  // Transaction storage keys
  const txnStorageKey = useMemo(() => `ops_transactions_${storeId}_${todayKey}`, [storeId, todayKey])
  const txnIndexKey = useMemo(() => `ops_txn_index_${storeId}_${todayKey}`, [storeId, todayKey])
  
  // Track the next streaming index (for deterministic transaction generation)
  const [nextStreamIndex, setNextStreamIndex] = useState<number>(() => {
    try {
      const stored = sessionStorage.getItem(txnIndexKey)
      return stored ? parseInt(stored, 10) : 8 // Start after initial 8 transactions
    } catch {
      return 8
    }
  })
  
  // Load transactions from session storage on mount
  const [transactions, setTransactions] = useState<Transaction[]>(() => {
    try {
      const stored = sessionStorage.getItem(txnStorageKey)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })
  const [loadingTransactions, setLoadingTransactions] = useState(true)
  const initializedStoreRef = useRef<number | null>(null)
  const MAX_TRANSACTIONS = 15 // Keep last 15 transactions

  // Persist transactions to session storage
  useEffect(() => {
    try {
      sessionStorage.setItem(txnStorageKey, JSON.stringify(transactions))
    } catch (e) {
      console.warn('Failed to save transactions to session storage:', e)
    }
  }, [transactions, txnStorageKey])
  
  // Persist stream index to session storage
  useEffect(() => {
    try {
      sessionStorage.setItem(txnIndexKey, String(nextStreamIndex))
    } catch (e) {
      console.warn('Failed to save txn index to session storage:', e)
    }
  }, [nextStreamIndex, txnIndexKey])

  // Helper to add a transaction's data to incremental totals
  const addTransactionToIncrements = useCallback((txn: Transaction) => {
    setIncrementalData(prev => ({
      sales: prev.sales + txn.total,
      transactions: prev.transactions + 1,
      channels: {
        ...prev.channels,
        [txn.channel]: (prev.channels[txn.channel] || 0) + txn.total
      }
    }))
  }, [])

  // Computed summary with incremental updates applied
  const summary = useMemo(() => {
    if (!baseSummary) return null
    
    const newSalesTotal = baseSummary.sales_today + incrementalData.sales
    const newTransactions = baseSummary.transactions_today + incrementalData.transactions
    
    // Recalculate vs_forecast with new sales
    const forecastSales = baseSummary.forecast_sales || baseSummary.sales_today / (1 + baseSummary.vs_forecast_pct / 100)
    const newVsForecast = forecastSales > 0 ? ((newSalesTotal - forecastSales) / forecastSales) * 100 : 0
    
    // Merge channel data
    const updatedChannels = baseSummary.channels ? baseSummary.channels.map((ch: any) => ({
      ...ch,
      amount: ch.amount + (incrementalData.channels[ch.channel] || 0)
    })) : []
    
    return {
      ...baseSummary,
      sales_today: newSalesTotal,
      transactions_today: newTransactions,
      vs_forecast_pct: newVsForecast,
      channels: updatedChannels,
    }
  }, [baseSummary, incrementalData])

  // Initial fetch - only if we don't have cached transactions
  useEffect(() => {
    if (initializedStoreRef.current === storeId) {
      setLoadingTransactions(false)
      return
    }
    
    // Check if we already have transactions from session storage
    if (transactions.length > 0) {
      setLoadingTransactions(false)
      initializedStoreRef.current = storeId
      return
    }
    
    setLoadingTransactions(true)
    api.getTransactions(storeId, 8, true, 0).then((initialTxns) => {
      setTransactions(initialTxns)
      setLoadingTransactions(false)
      initializedStoreRef.current = storeId
    }).catch(() => {
      setLoadingTransactions(false)
    })
  }, [storeId, transactions.length])

  // Streaming updates - append 1-2 new transactions every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const newTxns = await api.getTransactions(storeId, 2, false, nextStreamIndex)
        if (newTxns && newTxns.length > 0) {
          // Add each new transaction to incremental totals
          newTxns.forEach(txn => addTransactionToIncrements(txn))
          
          setTransactions(prev => {
            // Prepend new transactions and keep only the most recent MAX_TRANSACTIONS
            const updated = [...newTxns, ...prev].slice(0, MAX_TRANSACTIONS)
            return updated
          })
          
          // Update stream index for next batch
          setNextStreamIndex(prev => prev + newTxns.length)
        }
      } catch (error) {
        console.error('Error fetching new transactions:', error)
      }
    }, 30000) // Every 30 seconds

    return () => clearInterval(interval)
  }, [storeId, nextStreamIndex, addTransactionToIncrements])

  // Track previous store to detect store changes
  const prevStoreRef = useRef<number | null>(null)
  
  // Reset state when store changes, loading cached data for new store from session
  useEffect(() => {
    // Only reset if we're actually changing stores (not initial mount)
    if (prevStoreRef.current !== null && prevStoreRef.current !== storeId) {
      initializedStoreRef.current = null
      setLoadingTransactions(true)
      
      // Load transactions for new store from session storage
      try {
        const storedTxns = sessionStorage.getItem(txnStorageKey)
        const storedIndex = sessionStorage.getItem(txnIndexKey)
        
        if (storedTxns) {
          setTransactions(JSON.parse(storedTxns))
          setNextStreamIndex(storedIndex ? parseInt(storedIndex, 10) : 8)
          setLoadingTransactions(false)
          initializedStoreRef.current = storeId
        } else {
          setTransactions([])
          setNextStreamIndex(8)
        }
      } catch (e) {
        setTransactions([])
        setNextStreamIndex(8)
      }
      
      // Load incremental data for new store from session storage
      try {
        const stored = sessionStorage.getItem(storageKey)
        if (stored) {
          setIncrementalData(JSON.parse(stored))
        } else {
          setIncrementalData({
            sales: 0,
            transactions: 0,
            channels: { in_store: 0, delivery: 0, app: 0, third_party: 0 }
          })
        }
      } catch (e) {
        setIncrementalData({
          sales: 0,
          transactions: 0,
          channels: { in_store: 0, delivery: 0, app: 0, third_party: 0 }
        })
      }
    }
    prevStoreRef.current = storeId
  }, [storeId, storageKey])

  const { data: alerts, isLoading: loadingAlerts } = useQuery({
    queryKey: ['alerts', storeId],
    queryFn: () => api.getAlerts(storeId),
    refetchInterval: 60000, // Refresh every minute
  })

  const { data: weather, isLoading: loadingWeather } = useQuery({
    queryKey: ['weather', storeId],
    queryFn: () => api.getCurrentWeather(storeId),
    refetchInterval: 300000, // Refresh every 5 minutes
  })

  const { data: events, isLoading: loadingEvents } = useQuery({
    queryKey: ['events', storeId],
    queryFn: () => api.getLocalEvents(storeId),
    refetchInterval: 3600000, // Refresh every hour
  })

  const formatCurrency = (value: number) => 
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)

  const formatChannel = (channel: string) => ({
    in_store: 'Carryout',
    delivery: 'Delivery',
    app: "Mobile App",
    third_party: '3rd Party',
  }[channel] || channel)

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-text-primary">Operations</h2>
          <p className="text-text-secondary">Real-time sales, staffing, and alerts</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live updates
        </div>
      </div>

      {/* Current Weather Card */}
      <AnimatePresence mode="wait">
        {loadingWeather ? (
          <motion.div
            key="weather-loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="bg-gradient-to-r from-brand-primary/10 via-brand-primary/5 to-brand-secondary/10 rounded-2xl p-5 border border-brand-primary/20"
          >
            <div className="flex items-center gap-4">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="text-4xl"
              >
                🌤️
              </motion.div>
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 text-brand-primary animate-spin" />
                  <span className="text-text-secondary">Fetching live weather from Open-Meteo API...</span>
                </div>
                <p className="text-xs text-text-tertiary mt-1">Connecting to external weather service</p>
              </div>
            </div>
          </motion.div>
        ) : weather ? (
          <motion.div
            key="weather-data"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="bg-gradient-to-r from-brand-primary/10 via-brand-primary/5 to-brand-secondary/10 rounded-2xl p-5 border border-brand-primary/20"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="text-5xl">{weather.condition_icon}</div>
                <div>
                  <div className="flex items-center gap-3">
                    <span className="text-4xl font-bold text-text-primary">{weather.temperature}°F</span>
                    <Badge variant={weather.sales_impact?.severity === 'high' ? 'warning' : 'default'}>
                      {weather.condition_label}
                    </Badge>
                  </div>
                  <p className="text-text-secondary mt-1">{weather.location}</p>
                </div>
              </div>
              
              <div className="hidden md:flex items-center gap-6">
                <div className="flex items-center gap-2 text-text-secondary">
                  <Wind className="w-4 h-4" />
                  <span>{weather.wind_speed} mph</span>
                </div>
                
                <div className="h-10 w-px bg-gray-200" />
                
                <div className="text-right">
                  <p className="text-sm font-medium text-text-primary">Sales Impact</p>
                  <p className={`text-sm ${
                    weather.sales_impact?.trend === 'up' ? 'text-green-600' :
                    weather.sales_impact?.trend === 'mixed' ? 'text-amber-600' :
                    'text-text-secondary'
                  }`}>
                    {weather.sales_impact?.message}
                  </p>
                </div>
              </div>
            </div>
            
            {/* Mobile sales impact */}
            <div className="md:hidden mt-3 pt-3 border-t border-brand-primary/20">
              <p className="text-sm">
                <span className="text-text-secondary">Sales Impact: </span>
                <span className={
                  weather.sales_impact?.trend === 'up' ? 'text-green-600 font-medium' :
                  weather.sales_impact?.trend === 'mixed' ? 'text-amber-600 font-medium' :
                  'text-text-secondary'
                }>
                  {weather.sales_impact?.message}
                </span>
              </p>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <AnimatePresence mode="wait">
          {loadingSummary ? (
            <>
              <StatCardSkeleton key="skel-1" />
              <StatCardSkeleton key="skel-2" />
              <StatCardSkeleton key="skel-3" />
              <StatCardSkeleton key="skel-4" />
            </>
          ) : (
            <motion.div 
              className="contents"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <StatCard
                label="Sales Today"
                value={summary ? formatCurrency(summary.sales_today) : '—'}
                change={summary?.vs_yesterday_pct}
                changeLabel="vs yesterday"
                icon={<DollarSign className="w-5 h-5" />}
                trend={summary?.vs_yesterday_pct >= 0 ? 'up' : 'down'}
              />
              <StatCard
                label="Transactions"
                value={summary?.transactions_today?.toLocaleString() || '—'}
                icon={<ShoppingCart className="w-5 h-5" />}
              />
              <StatCard
                label="Staff On Duty"
                value={summary?.staff?.on_duty || '—'}
                changeLabel={`of ${summary?.staff?.scheduled || 0} scheduled`}
                icon={<Users className="w-5 h-5" />}
              />
              <StatCard
                label="vs Forecast"
                value={summary ? `${summary.vs_forecast_pct >= 0 ? '+' : ''}${summary.vs_forecast_pct.toFixed(1)}%` : '—'}
                icon={<TrendingUp className="w-5 h-5" />}
                trend={summary?.vs_forecast_pct >= 0 ? 'up' : 'down'}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main Content Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Sales Chart - Takes 2 columns */}
        <Card className="lg:col-span-2">
          <CardHeader 
            title="Today's Sales" 
            subtitle="Hourly breakdown"
            action={
              <Badge variant="success" dot>
                {summary?.current_hour_sales ? formatCurrency(summary.current_hour_sales) : '—'} this hour
              </Badge>
            }
          />
          <AnimatePresence mode="wait">
            {loadingHourly ? (
              <div className="h-[280px]">
                <LoadingState message="Loading sales data from Databricks SQL Warehouse..." />
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                <SalesChart data={hourlyData || []} height={280} />
              </motion.div>
            )}
          </AnimatePresence>
        </Card>

        {/* Channel Breakdown */}
        <Card>
          <CardHeader title="Sales by Channel" />
          <AnimatePresence mode="wait">
            {loadingSummary ? (
              <div className="h-48">
                <LoadingState message="Retrieving channel data..." />
              </div>
            ) : summary?.channels ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <ChannelBreakdown data={summary.channels} />
              </motion.div>
            ) : (
              <div className="h-48 flex items-center justify-center text-text-tertiary">
                No data available
              </div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* Bottom Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Live Transaction Feed */}
        <Card>
          <CardHeader 
            title="Recent Transactions" 
            subtitle="Last few orders"
            icon={<ShoppingCart className="w-5 h-5" />}
          />
          <AnimatePresence mode="wait">
            {loadingTransactions ? (
              <LoadingState message="Streaming transactions from Databricks..." />
            ) : transactions?.length ? (
              <motion.div 
                className={`space-y-3 ${transactions.length > 8 ? 'max-h-[420px] overflow-y-auto pr-2' : ''}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {transactions.map((txn, index) => (
                  <motion.div
                    key={txn.txn_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(index * 0.05, 0.4) }}
                    className="flex items-center justify-between p-3 bg-surface-secondary rounded-xl"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white flex items-center justify-center shadow-soft">
                        <span className="text-lg">{BRAND_CONFIG.prepEmoji}</span>
                      </div>
                      <div>
                        <p className="font-medium text-text-primary text-sm">
                          {txn.items.slice(0, 2).join(', ')}
                          {txn.items.length > 2 && ` +${txn.items.length - 2}`}
                        </p>
                        <p className="text-xs text-text-secondary">
                          {txn.timestamp} • {formatChannel(txn.channel)}
                        </p>
                      </div>
                    </div>
                    <span className="font-medium text-text-primary tabular-nums">
                      {formatCurrency(txn.total)}
                    </span>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">
                <p>No transactions yet</p>
              </div>
            )}
          </AnimatePresence>
        </Card>

        {/* Alerts */}
        <Card>
          <CardHeader 
            title="Active Alerts" 
            subtitle="Weather, events, and inventory"
            icon={<AlertTriangle className="w-5 h-5" />}
            action={
              alerts?.length ? (
                <Badge variant="warning">{alerts.length} active</Badge>
              ) : null
            }
          />
          <AnimatePresence mode="wait">
            {loadingAlerts ? (
              <LoadingState message="Fetching alerts from weather & event APIs..." />
            ) : alerts?.length ? (
              <motion.div 
                className="space-y-3"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {alerts.map((alert, index) => (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className={`p-4 rounded-xl border-l-4 ${
                      alert.severity === 'critical' 
                        ? 'bg-red-50 border-red-500'
                        : alert.severity === 'warning'
                        ? 'bg-amber-50 border-amber-500'
                        : 'bg-blue-50 border-blue-500'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-1.5 rounded-lg ${
                        alert.severity === 'critical' ? 'bg-red-100' :
                        alert.severity === 'warning' ? 'bg-amber-100' : 'bg-blue-100'
                      }`}>
                        {alert.type === 'weather' ? '🌤️' : 
                         alert.type === 'event' ? '🎉' : 
                         alert.type === 'inventory' ? '📦' : '⚠️'}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-text-primary text-sm">{alert.title}</p>
                        <p className="text-sm text-text-secondary mt-0.5">{alert.message}</p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">
                <div className="text-3xl mb-2">✓</div>
                <p>No active alerts</p>
              </div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* Local Events Card */}
      <Card>
        <CardHeader 
          title="Local Events" 
          subtitle="Ticketmaster events within 50 miles (next 7 days)"
          icon={<Ticket className="w-5 h-5" />}
          action={
            events?.event_count ? (
              <Badge variant="info">{events.event_count} events</Badge>
            ) : null
          }
        />
        <AnimatePresence mode="wait">
          {loadingEvents ? (
            <LoadingState message="Fetching events from Ticketmaster API..." />
          ) : events?.events?.length ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-2"
            >
              {/* Scrollable events list */}
              <ul className="space-y-2 max-h-96 overflow-y-auto pr-2">
                {events.events.map((event: any, index: number) => (
                  <motion.li
                    key={event.id || index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(index * 0.05, 0.5) }}
                    className="flex items-start gap-3 p-3 bg-surface-secondary rounded-xl hover:bg-gray-100 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center text-purple-600 flex-shrink-0">
                      {event.type === 'sports' ? '🏟️' : 
                       event.type === 'music' ? '🎵' : 
                       event.type === 'arts' ? '🎭' : '📅'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-text-primary text-sm truncate">{event.name}</p>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-text-secondary">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {event.date}
                        </span>
                        {event.time && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {event.time}
                          </span>
                        )}
                        <span className="flex items-center gap-1 truncate">
                          <MapPin className="w-3 h-3" />
                          {event.venue}
                        </span>
                      </div>
                    </div>
                    {event.url && (
                      <a 
                        href={event.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded-lg hover:bg-gray-200 text-text-tertiary hover:text-purple-600 transition-colors flex-shrink-0"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </motion.li>
                ))}
              </ul>
              {events.traffic_impact !== 'none' && (
                <div className={`mt-3 p-3 rounded-lg text-sm ${
                  events.traffic_impact === 'high' ? 'bg-amber-50 text-amber-800' :
                  events.traffic_impact === 'medium' ? 'bg-blue-50 text-blue-800' :
                  'bg-gray-50 text-gray-600'
                }`}>
                  <span className="font-medium">Traffic Impact: </span>
                  {events.traffic_impact === 'high' ? 'Expect significant increased traffic during event times' :
                   events.traffic_impact === 'medium' ? 'Moderate traffic increase expected' :
                   'Minor impact on local traffic'}
                </div>
              )}
            </motion.div>
          ) : (
            <div className="py-8 text-center text-text-tertiary">
              <div className="text-3xl mb-2">📅</div>
              <p>No major events this week</p>
            </div>
          )}
        </AnimatePresence>
      </Card>

      {/* Staffing Preview */}
      <Card>
        <div className="flex items-center justify-between">
          <CardHeader 
            title="Current Staffing" 
            icon={<Clock className="w-5 h-5" />}
          />
          <button 
            onClick={() => navigate('/store/labor')}
            className="flex items-center gap-1 text-sm text-brand-primary font-medium hover:underline"
          >
            View full schedule
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex -space-x-2">
            {[1, 2, 3, 4, 5].slice(0, summary?.staff?.on_duty || 3).map((i) => (
              <div 
                key={i}
                className="w-10 h-10 rounded-full bg-brand-primary/10 border-2 border-white flex items-center justify-center text-sm font-medium text-brand-primary"
              >
                {['MG', 'JD', 'SK', 'MR', 'EC'][i - 1]}
              </div>
            ))}
          </div>
          <div className="text-sm">
            <p className="text-text-primary font-medium">
              {summary?.staff?.on_duty || 0} on duty
            </p>
            <p className="text-text-secondary">
              Next: {summary?.staff?.next_shift_employee} at {summary?.staff?.next_shift_time}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}


