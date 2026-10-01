import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { ChefHat, Clock, AlertTriangle, CheckCircle, Timer, Loader2, X, Calendar, Check, Plus } from 'lucide-react'
import { BRAND_CONFIG } from '../../brand.config'
import { useOutletContext } from 'react-router-dom'
import { api } from '../../api/client'
import { Card, CardHeader } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'

interface StoreContext {
  storeId: number
  addedToScheduleItems: AddedToScheduleItem[]
  submitPrepItems: (items: {
    crust_type: string
    recommended_quantity?: number
    suggested_prep_time?: string
    confidence?: number
  }[]) => Promise<void>
  clearPrepItems: () => Promise<void>
  appliedPrepTasks: any[]
  setAppliedPrepTasks: React.Dispatch<React.SetStateAction<any[]>>
}

interface AddedToScheduleItem {
  crust_type: string
  addedAt: string
}

// Add to Schedule Modal with selectable items
const AddToScheduleModal = ({
  isOpen,
  onClose,
  recommendations,
  addedItems,
  onSubmit
}: {
  isOpen: boolean
  onClose: () => void
  recommendations: any[]
  addedItems: AddedToScheduleItem[]
  onSubmit: (selectedTypes: string[]) => void
}) => {
  const [applied, setApplied] = useState(false)
  const [isApplying, setIsApplying] = useState(false)
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  // Store the submitted info for the confirmation screen
  const [submittedInfo, setSubmittedInfo] = useState<{ count: number; doughBalls: number } | null>(null)

  // Filter out already added items
  const availableItems = recommendations?.filter(
    r => !addedItems.some(a => a.crust_type === r.crust_type)
  ) || []

  const toggleItem = (crustType: string) => {
    const newSelected = new Set(selectedItems)
    if (newSelected.has(crustType)) {
      newSelected.delete(crustType)
    } else {
      newSelected.add(crustType)
    }
    setSelectedItems(newSelected)
  }

  const selectAll = () => {
    setSelectedItems(new Set(availableItems.map(i => i.crust_type)))
  }

  const selectNone = () => {
    setSelectedItems(new Set())
  }

  const handleApply = async () => {
    if (selectedItems.size === 0) return
    // Calculate and store the totals BEFORE submission
    const selectedRecs = availableItems.filter(r => selectedItems.has(r.crust_type))
    const totalDoughBalls = selectedRecs.reduce((sum, r) => sum + r.recommended_quantity, 0)
    setSubmittedInfo({ count: selectedItems.size, doughBalls: totalDoughBalls })

    setIsApplying(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    onSubmit(Array.from(selectedItems))
    setIsApplying(false)
    setApplied(true)
  }

  const handleClose = () => {
    setApplied(false)
    setSubmittedInfo(null)
    setSelectedItems(new Set()) // Start with nothing selected
    onClose()
  }

  if (!isOpen) return null

  const selectedRecs = availableItems.filter(r => selectedItems.has(r.crust_type))
  const totalDoughBalls = selectedRecs.reduce((sum, r) => sum + r.recommended_quantity, 0)

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={handleClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="bg-white rounded-2xl shadow-strong max-w-lg w-full max-h-[80vh] overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-secondary/20 flex items-center justify-center">
                <Calendar className="w-5 h-5 text-brand-secondary-dark" />
              </div>
              <div>
                <h3 className="font-semibold text-text-primary">Add to Schedule</h3>
                <p className="text-sm text-text-secondary">Select items to add to prep schedule</p>
              </div>
            </div>
            <button onClick={handleClose} className="p-2 rounded-lg hover:bg-gray-100">
              <X className="w-5 h-5 text-text-secondary" />
            </button>
          </div>

          {/* Content */}
          <div className="p-5 max-h-96 overflow-y-auto">
            {applied && submittedInfo ? (
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="text-center py-8"
              >
                <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
                <h4 className="text-lg font-semibold text-text-primary mb-2">Added to Schedule!</h4>
                <p className="text-text-secondary">
                  {submittedInfo.count} items ({submittedInfo.doughBalls} {BRAND_CONFIG.prepNounPlural}) added to today's prep schedule.
                </p>
                <p className="text-sm text-text-tertiary mt-2">Staff has been notified</p>
              </motion.div>
            ) : availableItems.length === 0 ? (
              <div className="text-center py-8">
                <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-gray-400" />
                </div>
                <h4 className="text-lg font-semibold text-text-primary mb-2">All Items Added</h4>
                <p className="text-text-secondary">All recommended items have been added to the schedule.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Selection controls */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">{selectedItems.size} of {availableItems.length} selected</span>
                  <div className="flex gap-2">
                    <button onClick={selectAll} className="text-xs text-brand-primary hover:underline">Select All</button>
                    <span className="text-text-tertiary">|</span>
                    <button onClick={selectNone} className="text-xs text-text-secondary hover:underline">Clear</button>
                  </div>
                </div>

                {availableItems.map((rec) => (
                  <div
                    key={rec.crust_type}
                    onClick={() => toggleItem(rec.crust_type)}
                    className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all ${
                      selectedItems.has(rec.crust_type)
                        ? 'bg-brand-primary/10 border-2 border-brand-primary/30'
                        : 'bg-surface-secondary border-2 border-transparent hover:border-gray-200'
                    }`}
                  >
                    <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-colors ${
                      selectedItems.has(rec.crust_type)
                        ? 'bg-brand-primary border-brand-primary'
                        : 'border-gray-300'
                    }`}>
                      {selectedItems.has(rec.crust_type) && (
                        <Check className="w-3 h-3 text-white" />
                      )}
                    </div>
                    <span className="text-2xl">{BRAND_CONFIG.prepEmoji}</span>
                    <div className="flex-1">
                      <p className="font-medium text-text-primary text-sm">{rec.crust_type}</p>
                      <p className="text-xs text-text-secondary">Prep at {rec.suggested_prep_time}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-bold text-brand-primary">{rec.recommended_quantity}</p>
                      <p className="text-xs text-text-tertiary">{BRAND_CONFIG.prepNounPlural}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-5 border-t border-gray-100 bg-surface-secondary">
            {!applied && availableItems.length > 0 ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-text-secondary">Total {BRAND_CONFIG.prepNounPlural}</p>
                  <p className="text-xl font-bold text-text-primary">{totalDoughBalls}</p>
                </div>
                <div className="flex gap-3">
                  <Button variant="secondary" onClick={handleClose}>Cancel</Button>
                  <Button onClick={handleApply} disabled={isApplying || selectedItems.size === 0}>
                    {isApplying ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Adding...
                      </>
                    ) : (
                      `Add to Schedule (${selectedItems.size})`
                    )}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex justify-end">
                <Button onClick={handleClose}>Done</Button>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// Loading component
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

// Inventory skeleton loader
const InventorySkeleton = () => (
  <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
    {[1, 2, 3, 4, 5].map((i) => (
      <motion.div
        key={i}
        className="p-4 bg-surface-secondary rounded-xl text-center"
        initial={{ opacity: 0.6 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
      >
        <div className="text-3xl mb-2 animate-pulse">{BRAND_CONFIG.prepEmoji}</div>
        <div className="h-4 w-20 mx-auto bg-gray-200 rounded animate-pulse mb-2" />
        <div className="h-8 w-12 mx-auto bg-gray-200 rounded animate-pulse mb-2" />
        <div className="h-3 w-16 mx-auto bg-gray-100 rounded animate-pulse" />
      </motion.div>
    ))}
    <div className="col-span-full text-center text-xs text-text-tertiary flex items-center justify-center gap-1">
      <Loader2 className="w-3 h-3 animate-spin" />
      <span>Loading from Databricks SQL Warehouse...</span>
    </div>
  </div>
)

export default function PrepScheduler() {
  const {
    storeId,
    addedToScheduleItems,
    submitPrepItems,
    clearPrepItems,
    appliedPrepTasks: appliedTasks,
    setAppliedPrepTasks: setAppliedTasks
  } = useOutletContext<StoreContext>()
  const [showApplyModal, setShowApplyModal] = useState(false)
  const [isClearing, setIsClearing] = useState(false)

  const { data: inventory, isLoading: loadingInventory } = useQuery({
    queryKey: ['dough-inventory', storeId],
    queryFn: () => api.getDoughInventory(storeId),
  })

  const { data: schedule, isLoading: loadingSchedule } = useQuery({
    queryKey: ['prep-schedule', storeId],
    queryFn: () => api.getPrepSchedule(storeId),
  })

  const { data: recommendations, isLoading: loadingRecs } = useQuery({
    queryKey: ['prep-batch-recommendations', storeId],
    queryFn: () => api.getPrepBatchRecommendations(storeId),
  })

  const { data: alerts } = useQuery({
    queryKey: ['prep-alerts', storeId],
    queryFn: () => api.getPrepAlerts(storeId),
  })

  // Reconstruct appliedTasks from persisted state when recommendations load
  useEffect(() => {
    if (addedToScheduleItems.length > 0 && recommendations && appliedTasks.length === 0) {
      const baseId = (schedule?.tasks?.length || 0) + 1000
      const tasks = addedToScheduleItems
        .map((item, index) => {
          const rec = recommendations.find((r: any) => r.crust_type === item.crust_type)
          if (!rec) return null
          return {
            id: baseId + index,
            crust_type: rec.crust_type,
            quantity: rec.recommended_quantity,
            scheduled_time: rec.suggested_prep_time,
            ready_time: calculateReadyTime(rec.suggested_prep_time, rec.crust_type),
            status: 'pending',
            priority: 'high',
            isMLRecommendation: true,
          }
        })
        .filter(Boolean)
      if (tasks.length > 0) setAppliedTasks(tasks)
    }
  }, [addedToScheduleItems, recommendations, schedule])

  // Combine original schedule tasks with applied ML recommendation tasks, sorted by time
  const combinedSchedule = schedule ? {
    ...schedule,
    tasks: [
      ...(schedule.tasks || []),
      ...appliedTasks
    ].sort((a, b) => {
      // Parse times and sort chronologically
      const parseTime = (timeStr: string) => {
        const match = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/i)
        if (!match) return 0
        let hours = parseInt(match[1])
        const minutes = parseInt(match[2])
        const period = match[3].toUpperCase()
        if (period === 'PM' && hours !== 12) hours += 12
        if (period === 'AM' && hours === 12) hours = 0
        return hours * 60 + minutes
      }
      return parseTime(a.scheduled_time) - parseTime(b.scheduled_time)
    }),
    total_dough_balls: (schedule.total_dough_balls || 0) + appliedTasks.reduce((sum, t) => sum + t.quantity, 0)
  } : null

  const handleApplyRecommendations = async (selectedCrustTypes: string[]) => {
    const selectedRecs = recommendations?.filter(r => selectedCrustTypes.includes(r.crust_type)) || []

    // Persist to Lakebase
    const items = selectedRecs.map(rec => ({
      crust_type: rec.crust_type,
      recommended_quantity: rec.recommended_quantity,
      suggested_prep_time: rec.suggested_prep_time,
      confidence: rec.confidence,
    }))
    await submitPrepItems(items)

    // Also add as local tasks for the schedule view
    const baseId = (schedule?.tasks?.length || 0) + appliedTasks.length + 1000
    const newTasks = selectedRecs.map((rec, index) => ({
      id: baseId + index,
      crust_type: rec.crust_type,
      quantity: rec.recommended_quantity,
      scheduled_time: rec.suggested_prep_time,
      ready_time: calculateReadyTime(rec.suggested_prep_time, rec.crust_type),
      status: 'pending',
      priority: 'high',
      isMLRecommendation: true,
    }))
    setAppliedTasks(prev => [...prev, ...newTasks])
  }

  const handleClearSchedule = async () => {
    setIsClearing(true)
    await clearPrepItems()
    setIsClearing(false)
  }

  // Calculate ready time based on crust type prep/proof times
  const calculateReadyTime = (startTime: string, _crustType: string) => {
    // Prep-time estimate fallback (real per-subtype times come from the backend
    // recommendation). Kept generic so it works for any customer's subtypes.
    const prepMinutes = 20

    // Parse start time and add prep minutes
    const match = startTime.match(/(\d+):(\d+)\s*(AM|PM)/i)
    if (!match) return startTime

    let hours = parseInt(match[1])
    const minutes = parseInt(match[2])
    const period = match[3].toUpperCase()

    if (period === 'PM' && hours !== 12) hours += 12
    if (period === 'AM' && hours === 12) hours = 0

    const totalMinutes = hours * 60 + minutes + prepMinutes
    const readyHours = Math.floor(totalMinutes / 60) % 24
    const readyMinutes = totalMinutes % 60

    const readyPeriod = readyHours >= 12 ? 'PM' : 'AM'
    const displayHours = readyHours > 12 ? readyHours - 12 : (readyHours === 0 ? 12 : readyHours)

    return `${displayHours}:${readyMinutes.toString().padStart(2, '0')} ${readyPeriod}`
  }

  const getFreshnessColor = (status: string) => ({
    fresh: 'text-green-600 bg-green-50',
    aging: 'text-amber-600 bg-amber-50',
    expired: 'text-red-600 bg-red-50',
  }[status] || 'text-gray-600 bg-gray-50')

  const getStatusIcon = (status: string) => {
    if (status === 'complete') return <CheckCircle className="w-4 h-4 text-green-500" />
    if (status === 'prepping') return <Timer className="w-4 h-4 text-amber-500 animate-pulse" />
    return <Clock className="w-4 h-4 text-gray-400" />
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-text-primary">Prep Scheduler</h2>
          <p className="text-text-secondary">Production prep schedule and inventory</p>
        </div>
        {(combinedSchedule?.next_prep || appliedTasks.find(t => t.status === 'pending')) && (
          <div className="flex items-center gap-3 px-4 py-2 bg-brand-primary/10 rounded-xl">
            <Timer className="w-5 h-5 text-brand-primary" />
            <div>
              <p className="text-sm font-medium text-text-primary">Next Prep</p>
              <p className="text-xs text-text-secondary">
                {combinedSchedule?.next_prep
                  ? `${combinedSchedule.next_prep.crust_type} at ${combinedSchedule.next_prep.scheduled_time}`
                  : appliedTasks.find(t => t.status === 'pending')
                    ? `${appliedTasks.find(t => t.status === 'pending')?.crust_type} at ${appliedTasks.find(t => t.status === 'pending')?.scheduled_time}`
                    : ''
                }
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Current Inventory */}
      <Card>
        <CardHeader
          title="Current Inventory"
          subtitle="Freshness and stock levels"
          icon={<ChefHat className="w-5 h-5" />}
        />
        <AnimatePresence mode="wait">
          {loadingInventory ? (
            <InventorySkeleton />
          ) : inventory?.length ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4"
            >
              {inventory.map((dough, index) => (
                <motion.div
                  key={dough.crust_type}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 bg-surface-secondary rounded-xl text-center"
                >
                  <div className="text-3xl mb-2">{BRAND_CONFIG.prepEmoji}</div>
                  <h4 className="font-medium text-text-primary text-sm mb-1">{dough.crust_type}</h4>
                  <p className="text-2xl font-bold text-brand-primary mb-2">{dough.quantity}</p>
                  <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${getFreshnessColor(dough.freshness_status)}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      dough.freshness_status === 'fresh' ? 'bg-green-500' :
                      dough.freshness_status === 'aging' ? 'bg-amber-500' : 'bg-red-500'
                    }`} />
                    {dough.freshness_status === 'fresh'
                      ? `${dough.hours_until_stale.toFixed(1)}h fresh`
                      : dough.freshness_status === 'aging'
                      ? 'Use soon'
                      : 'Expired'}
                  </div>
                  <p className="text-xs text-text-tertiary mt-2">
                    Last prepped: {dough.last_prepped}
                  </p>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <div className="py-8 text-center text-text-tertiary">No inventory data</div>
          )}
        </AnimatePresence>
      </Card>

      {/* Main Grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Today's Prep Schedule */}
        <Card>
          <CardHeader
            title="Today's Prep Schedule"
            subtitle={`${combinedSchedule?.total_dough_balls || 0} total ${BRAND_CONFIG.prepNounPlural}${appliedTasks.length > 0 ? ` (${appliedTasks.reduce((s, t) => s + t.quantity, 0)} from ML)` : ''}`}
            icon={<Clock className="w-5 h-5" />}
          />
          <AnimatePresence mode="wait">
            {loadingSchedule ? (
              <LoadingState message="Loading prep schedule from Databricks SQL Warehouse..." />
            ) : combinedSchedule?.tasks?.length ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-3 max-h-80 overflow-y-auto"
              >
                {combinedSchedule.tasks.map((task: any, index: number) => (
                  <motion.div
                    key={task.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03 }}
                    className={`flex items-center gap-4 p-3 rounded-xl ${
                      task.status === 'prepping' ? 'bg-amber-50 border border-amber-200' :
                      task.status === 'complete' ? 'bg-green-50' : 'bg-surface-secondary'
                    }`}
                  >
                    <div className="relative">
                      {getStatusIcon(task.status)}
                      {task.isMLRecommendation && (
                        <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-brand-primary flex items-center justify-center border border-white">
                          <span className="text-white text-[6px] font-bold">ML</span>
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{BRAND_CONFIG.prepEmoji}</span>
                        <span className="font-medium text-text-primary text-sm">{task.crust_type}</span>
                        {task.isMLRecommendation && (
                          <Badge variant="success" size="sm">ML Added</Badge>
                        )}
                      </div>
                      <p className="text-xs text-text-secondary">
                        {task.scheduled_time} → Ready {task.ready_time}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-brand-primary">{task.quantity}</p>
                      <p className="text-xs text-text-tertiary">{BRAND_CONFIG.prepNounPlural}</p>
                    </div>
                    <Badge
                      variant={task.priority === 'high' ? 'warning' : 'default'}
                      size="sm"
                    >
                      {task.priority}
                    </Badge>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No prep tasks scheduled</div>
            )}
          </AnimatePresence>
        </Card>

        {/* AI Recommendations */}
        <Card>
          <CardHeader
            title="ML Prep Recommendations"
            subtitle="Based on demand forecast"
            action={
              <div className="flex gap-2">
                {addedToScheduleItems.length > 0 && (
                  <Button size="sm" variant="secondary" onClick={handleClearSchedule} disabled={isClearing}>
                    {isClearing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                    Clear Schedule
                  </Button>
                )}
                <Button size="sm" onClick={() => setShowApplyModal(true)}><Plus className="w-4 h-4 mr-1" />Add to Schedule</Button>
              </div>
            }
          />

          {/* Add to Schedule Modal */}
          <AddToScheduleModal
            isOpen={showApplyModal}
            onClose={() => setShowApplyModal(false)}
            recommendations={recommendations || []}
            addedItems={addedToScheduleItems}
            onSubmit={handleApplyRecommendations}
          />
          <AnimatePresence mode="wait">
            {loadingRecs ? (
              <LoadingState message="Generating prep recommendations from Databricks Model Serving..." />
            ) : recommendations?.length ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-3"
              >
                {recommendations.map((rec, index) => {
                  const addedItem = addedToScheduleItems.find(a => a.crust_type === rec.crust_type)
                  const isAdded = !!addedItem

                  return (
                    <motion.div
                      key={rec.crust_type}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.1 }}
                      className={`p-4 rounded-xl border relative overflow-hidden ${
                        isAdded
                          ? 'border-green-200'
                          : 'bg-gradient-to-r from-brand-primary/5 to-transparent border-brand-primary/10'
                      }`}
                    >
                      {/* Glass overlay for added items */}
                      {isAdded && (
                        <div
                          className="absolute inset-0 bg-gradient-to-r from-green-100/70 via-emerald-50/60 to-teal-50/50 backdrop-blur-[2px]"
                          style={{ mixBlendMode: 'overlay' }}
                        />
                      )}

                      <div className="relative z-10">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{BRAND_CONFIG.prepEmoji}</span>
                            <span className="font-medium text-text-primary">{rec.crust_type}</span>
                            {isAdded && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">
                                <CheckCircle className="w-3 h-3" />
                                Added to schedule
                              </span>
                            )}
                          </div>
                          <span className="text-2xl font-bold text-brand-primary">{rec.recommended_quantity}</span>
                        </div>
                        <p className="text-sm text-text-secondary">{rec.reason}</p>
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
                          {isAdded ? (
                            <span className="text-xs text-green-600 font-medium">
                              {addedItem.addedAt}
                            </span>
                          ) : (
                            <span className="text-xs text-text-tertiary">
                              Suggested: {rec.suggested_prep_time}
                            </span>
                          )}
                          <Badge variant="success" size="sm">
                            {(rec.confidence * 100).toFixed(0)}% conf
                          </Badge>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No recommendations available</div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* Alerts */}
      {alerts && alerts.length > 0 && (
        <Card>
          <CardHeader
            title="Prep Alerts"
            icon={<AlertTriangle className="w-5 h-5" />}
          />
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {alerts.map((alert: any, index: number) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.05 }}
                className={`p-4 rounded-xl ${
                  alert.severity === 'critical' ? 'bg-red-50 border border-red-200' :
                  alert.severity === 'warning' ? 'bg-amber-50 border border-amber-200' :
                  'bg-blue-50 border border-blue-200'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{BRAND_CONFIG.prepEmoji}</span>
                  <span className="font-medium text-text-primary text-sm">{alert.crust_type}</span>
                  <Badge
                    variant={alert.severity === 'critical' ? 'error' : 'warning'}
                    size="sm"
                  >
                    {alert.type}
                  </Badge>
                </div>
                <p className="text-sm text-text-secondary mb-2">{alert.message}</p>
                <p className="text-xs text-brand-primary font-medium">{alert.action}</p>
              </motion.div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
