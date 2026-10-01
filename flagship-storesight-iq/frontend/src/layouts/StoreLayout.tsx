import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, TrendingUp, Users, Package, ChefHat,
  ChevronLeft, Settings, Store, ChevronDown, Check, Loader2, Home
} from 'lucide-react'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useQueryClient, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { BRAND_CONFIG } from '../brand.config'

const navItems = [
  { path: 'operations', label: 'Operations', icon: Activity, description: 'Real-time sales & alerts' },
  { path: 'forecast', label: 'Forecast', icon: TrendingUp, description: 'Demand predictions' },
  { path: 'labor', label: 'Labor', icon: Users, description: 'Staffing optimization' },
  { path: 'inventory', label: 'Inventory', icon: Package, description: 'Stock management' },
  // The 5th "prep/production scheduler" surface is configurable — hidden when
  // features.prep_scheduler_enabled is false. Label comes from brand.config.
  ...(BRAND_CONFIG.prepSchedulerEnabled
    ? [{ path: 'prep', label: BRAND_CONFIG.prepPageTitle, icon: ChefHat, description: 'Production prep schedule' }]
    : []),
]

// Reference stores (id/name/city). generate.py regenerates this list from
// accelerator/domain.yaml (stores). Neutral reference fleet below.
const STORES = [
  { id: 1, name: "Miami Central", city: "Miami" },
  { id: 2, name: "Islamorada", city: "Islamorada" },
  { id: 3, name: "Polo Club Shops", city: "Boca Raton" },
  { id: 4, name: "Punta Gorda Crossing", city: "Punta Gorda" },
  { id: 5, name: "Beachway Plaza", city: "Bradenton" },
  { id: 6, name: "Kings Crossing", city: "Sun City Center" },
  { id: 7, name: "Osceola Village", city: "Kissimmee" },
  { id: 8, name: "Casselberry Commons", city: "Casselberry" },
  { id: 9, name: "Indialantic", city: "Indialantic" },
  { id: 10, name: "Hays Road Town Center", city: "Hudson" },
  { id: 11, name: "Lakewood Ranch", city: "Lakewood Ranch" },
  { id: 12, name: "Howell Mill Village", city: "Atlanta" },
  { id: 13, name: "Medlock Corners", city: "Johns Creek" },
  { id: 14, name: "Milstead Crossing", city: "Conyers" },
  { id: 15, name: "Acworth", city: "Acworth" },
  { id: 16, name: "Rainbow Landing", city: "Rainbow City" },
  { id: 17, name: "Smoky Mountain Gateway", city: "Sevierville" },
  { id: 18, name: "Raleigh Wade Ave", city: "Raleigh" },
  { id: 19, name: "Greenville", city: "Greenville" },
  { id: 20, name: "Charleston East Bay", city: "Charleston" },
  { id: 21, name: "Charlotte Park Rd", city: "Charlotte" },
  { id: 22, name: "Knoxville Kingston Pike", city: "Knoxville" },
  { id: 23, name: "Richmond West Main", city: "Richmond" },
  { id: 24, name: "Louisville Brownsboro", city: "Louisville" },
]

// Types for persisted state
interface OrderedItem {
  ingredient_id: number
  orderedAt: string
}

interface AddedToScheduleItem {
  crust_type: string
  addedAt: string
}

export default function StoreLayout() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [storeId, setStoreId] = useState(1)
  const [showStoreDropdown, setShowStoreDropdown] = useState(false)
  const [showSettingsMenu, setShowSettingsMenu] = useState(false)
  const [isPrefetching, setIsPrefetching] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const settingsRef = useRef<HTMLDivElement>(null)
  
  // Local UI state derived from persisted Lakebase data
  const [appliedPrepTasks, setAppliedPrepTasks] = useState<any[]>([])
  
  const selectedStore = STORES.find(s => s.id === storeId) || STORES[0]
  const storeName = selectedStore.name

  // Load persisted inventory orders from Lakebase
  const { data: persistedOrders = [], refetch: refetchOrders } = useQuery({
    queryKey: ['persisted-inventory-orders', storeId],
    queryFn: () => api.getInventoryOrders(storeId).catch(() => []),
    staleTime: 0,
  })

  // Load persisted prep prep items from Lakebase
  const { data: persistedPrepItems = [], refetch: refetchPrepItems } = useQuery({
    queryKey: ['persisted-prep-items', storeId],
    queryFn: () => api.getPrepState(storeId).catch(() => []),
    staleTime: 0,
  })

  // Derive orderedItems from persisted data for backward compatibility
  const orderedItems: OrderedItem[] = persistedOrders.map((o: any) => ({
    ingredient_id: o.ingredient_id,
    orderedAt: o.ordered_at,
  }))

  // Derive addedToScheduleItems from persisted data
  const addedToScheduleItems: AddedToScheduleItem[] = persistedPrepItems.map((p: any) => ({
    crust_type: p.crust_type,
    addedAt: p.added_at,
  }))

  // Wrapper: submit inventory orders to Lakebase, then refetch
  const submitInventoryOrders = useCallback(async (items: {
    ingredient_id: number
    ingredient_name: string
    suggested_quantity?: number
    estimated_cost?: number
    urgency?: string
  }[]) => {
    await api.submitInventoryOrders(storeId, items)
    await refetchOrders()
  }, [storeId, refetchOrders])

  // Wrapper: submit prep prep items to Lakebase, then refetch
  const submitPrepItems = useCallback(async (items: {
    crust_type: string
    recommended_quantity?: number
    suggested_prep_time?: string
    confidence?: number
  }[]) => {
    await api.submitPrepItems(storeId, items)
    await refetchPrepItems()
  }, [storeId, refetchPrepItems])

  // Clear state functions
  const clearInventoryOrders = useCallback(async () => {
    await api.clearInventoryOrders(storeId)
    await refetchOrders()
  }, [storeId, refetchOrders])

  const clearPrepItems = useCallback(async () => {
    await api.clearPrepState(storeId)
    setAppliedPrepTasks([])
    await refetchPrepItems()
  }, [storeId, refetchPrepItems])

  const handleStoreChange = (newStoreId: number) => {
    setStoreId(newStoreId)
    setAppliedPrepTasks([])
  }

  // Prefetch all data for a store
  const prefetchStoreData = useCallback(async (id: number) => {
    setIsPrefetching(true)
    
    try {
      // Prefetch all data in parallel - query keys MUST match what pages use
      await Promise.all([
        // Operations page data
        queryClient.prefetchQuery({
          queryKey: ['operations-summary', id],
          queryFn: () => api.getOperationsSummary(id),
          staleTime: 1000 * 60 * 5, // 5 minutes
        }),
        queryClient.prefetchQuery({
          queryKey: ['hourly-sales', id],
          queryFn: () => api.getHourlySales(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['transactions', id],
          queryFn: () => api.getTransactions(id, 8),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['alerts', id],
          queryFn: () => api.getAlerts(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['weather', id],
          queryFn: () => api.getCurrentWeather(id),
          staleTime: 1000 * 60 * 10, // 10 minutes
        }),
        queryClient.prefetchQuery({
          queryKey: ['events', id],
          queryFn: () => api.getLocalEvents(id),
          staleTime: 1000 * 60 * 30, // 30 minutes
        }),
        
        // Forecast page data
        queryClient.prefetchQuery({
          queryKey: ['weekly-forecast', id],
          queryFn: () => api.getWeeklyForecast(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['hourly-forecast', id],
          queryFn: () => api.getHourlyForecast(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['prep-recommendations', id],
          queryFn: () => api.getPrepRecommendations(id, 'lunch'),
          staleTime: 1000 * 60 * 5,
        }),
        
        // Labor page data
        queryClient.prefetchQuery({
          queryKey: ['labor-summary', id],
          queryFn: () => api.getLaborSummary(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['schedule', id],
          queryFn: () => api.getSchedule(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['hourly-labor', id],
          queryFn: () => api.getHourlyLabor(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['staffing-recommendations', id],
          queryFn: () => api.getStaffingRecommendations(id),
          staleTime: 1000 * 60 * 5,
        }),
        
        // Inventory page data
        queryClient.prefetchQuery({
          queryKey: ['inventory-summary', id],
          queryFn: () => api.getInventorySummary(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['inventory-levels', id, null],
          queryFn: () => api.getInventoryLevels(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['deliveries', id],
          queryFn: () => api.getDeliveries(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['order-suggestions', id],
          queryFn: () => api.getOrderSuggestions(id),
          staleTime: 1000 * 60 * 5,
        }),
        
        // Prep Scheduler page data
        queryClient.prefetchQuery({
          queryKey: ['dough-inventory', id],
          queryFn: () => api.getDoughInventory(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['prep-schedule', id],
          queryFn: () => api.getPrepSchedule(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['prep-batch-recommendations', id],
          queryFn: () => api.getPrepBatchRecommendations(id),
          staleTime: 1000 * 60 * 5,
        }),
        queryClient.prefetchQuery({
          queryKey: ['prep-alerts', id],
          queryFn: () => api.getPrepAlerts(id),
          staleTime: 1000 * 60 * 5,
        }),
      ])
      console.log(`✓ Prefetched all data for store ${id}`)
    } catch (error) {
      console.warn('Some prefetch queries failed:', error)
    } finally {
      setIsPrefetching(false)
    }
  }, [queryClient])

  // Prefetch data when store changes
  useEffect(() => {
    // Invalidate old cache and prefetch new store data
    queryClient.invalidateQueries()
    prefetchStoreData(storeId)
  }, [storeId, prefetchStoreData, queryClient])

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowStoreDropdown(false)
      }
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setShowSettingsMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="min-h-screen bg-surface-secondary">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
          {/* Left: Back + Logo + Store Selector */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 -ml-2 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <ChevronLeft className="w-5 h-5 text-text-secondary" />
            </button>
            
            {/* Brand logo (replaced per-customer by generate.py) */}
            <img src={BRAND_CONFIG.logoSrc} alt="StoreSight IQ" className="h-8" />
            
            <div className="h-8 w-px bg-gray-200" />
            
            {/* Store Selector Dropdown */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowStoreDropdown(!showStoreDropdown)}
                className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-gray-100 transition-colors"
              >
                <div className="w-9 h-9 rounded-xl brand-gradient flex items-center justify-center">
                  <Store className="w-4 h-4 text-white" />
                </div>
                <div className="text-left">
                  <p className="font-medium text-text-primary text-sm">{storeName}</p>
                  <p className="text-xs text-text-secondary">Store #{storeId}</p>
                </div>
                <ChevronDown className={`w-4 h-4 text-text-secondary transition-transform ${showStoreDropdown ? 'rotate-180' : ''}`} />
              </button>
              
              {/* Dropdown Menu */}
              <AnimatePresence>
                {showStoreDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="absolute top-full left-0 mt-2 w-72 bg-white rounded-2xl shadow-strong border border-gray-100 py-2 max-h-80 overflow-y-auto z-50"
                  >
                    <p className="px-4 py-2 text-xs font-medium text-text-tertiary uppercase tracking-wide">Select Store</p>
                    {STORES.map((store) => (
                      <button
                        key={store.id}
                        onClick={() => {
                          handleStoreChange(store.id)
                          setShowStoreDropdown(false)
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors ${
                          store.id === storeId ? 'bg-brand-primary/5' : ''
                        }`}
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-medium ${
                          store.id === storeId ? 'bg-brand-primary text-white' : 'bg-gray-100 text-text-secondary'
                        }`}>
                          {store.id}
                        </div>
                        <div className="flex-1 text-left">
                          <p className="text-sm font-medium text-text-primary">{store.name}</p>
                          <p className="text-xs text-text-secondary">{store.city}</p>
                        </div>
                        {store.id === storeId && (
                          <Check className="w-4 h-4 text-brand-primary" />
                        )}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Center: Navigation */}
          <nav className="hidden lg:flex items-center bg-surface-secondary rounded-2xl p-1.5">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) => `
                  flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all
                  ${isActive 
                    ? 'bg-white text-brand-primary shadow-soft' 
                    : 'text-text-secondary hover:text-text-primary'
                  }
                `}
              >
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>

          {/* Right: Settings */}
          <div className="relative" ref={settingsRef}>
            <button 
              onClick={() => setShowSettingsMenu(!showSettingsMenu)}
              className="p-2.5 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <motion.div
                animate={{ rotate: showSettingsMenu ? 180 : 0 }}
                transition={{ duration: 0.4, ease: "easeInOut" }}
              >
                <Settings className="w-5 h-5 text-text-secondary" />
              </motion.div>
            </button>
            
            {/* Settings Dropdown */}
            <AnimatePresence>
              {showSettingsMenu && (
                <motion.div
                  initial={{ opacity: 0, y: -10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95 }}
                  transition={{ duration: 0.15 }}
                  className="absolute top-full right-0 mt-2 w-48 bg-white rounded-xl shadow-strong border border-gray-100 py-1 z-50"
                >
                  <button
                    onClick={() => {
                      setShowSettingsMenu(false)
                      navigate('/')
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
                  >
                    <Home className="w-4 h-4 text-text-secondary" />
                    <span className="text-sm font-medium text-text-primary">Home Page</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </header>

      {/* Mobile Navigation */}
      <nav className="lg:hidden sticky top-16 z-40 bg-white border-b border-gray-100 overflow-x-auto">
        <div className="flex items-center gap-1 px-4 py-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `
                flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all
                ${isActive 
                  ? 'bg-brand-primary/10 text-brand-primary' 
                  : 'text-text-secondary hover:text-text-primary'
                }
              `}
            >
              <item.icon className="w-4 h-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-[1600px] mx-auto px-6 py-6">
        {/* Persona Label + Prefetching Indicator */}
        <div className="mb-4 flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-brand-primary/10 rounded-full border border-brand-primary/20">
            <Store className="w-4 h-4 text-brand-primary" />
            <span className="text-sm font-medium text-brand-primary">Store Manager View</span>
          </div>
          
          {/* Prefetching indicator */}
          <AnimatePresence>
            {isPrefetching && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-full border border-blue-200"
              >
                <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin" />
                <span className="text-xs font-medium text-blue-600">Loading store data...</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Outlet context={{ 
            storeId, 
            storeName,
            orderedItems,
            submitInventoryOrders,
            clearInventoryOrders,
            addedToScheduleItems,
            submitPrepItems,
            clearPrepItems,
            appliedPrepTasks,
            setAppliedPrepTasks,
          }} />
        </motion.div>
      </main>
    </div>
  )
}


