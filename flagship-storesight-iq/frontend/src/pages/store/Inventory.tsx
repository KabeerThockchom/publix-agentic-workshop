import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Package, Truck, AlertTriangle, TrendingDown, Loader2, X, CheckCircle, ShoppingCart, DollarSign, Check } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../../api/client'
import { Card, CardHeader, StatCard } from '../../components/ui/Card'
import { Badge, StatusBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'

interface StoreContext {
  storeId: number
  orderedItems: OrderedItem[]
  submitInventoryOrders: (items: {
    ingredient_id: number
    ingredient_name: string
    suggested_quantity?: number
    estimated_cost?: number
    urgency?: string
  }[]) => Promise<void>
  clearInventoryOrders: () => Promise<void>
}

interface OrderedItem {
  ingredient_id: number
  orderedAt: string
}

// Order Modal Component with selectable items
const OrderModal = ({ 
  isOpen, 
  onClose, 
  suggestions,
  orderedItems,
  onSubmitOrder
}: { 
  isOpen: boolean
  onClose: () => void
  suggestions: any[]
  orderedItems: OrderedItem[]
  onSubmitOrder: (selectedIds: number[]) => void
}) => {
  const [orderSubmitted, setOrderSubmitted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set())
  // Store the submitted order details for the confirmation screen
  const [submittedOrderInfo, setSubmittedOrderInfo] = useState<{ count: number; total: number } | null>(null)

  // Filter out already ordered items
  const availableItems = suggestions?.filter(
    s => !orderedItems.some(o => o.ingredient_id === s.ingredient_id)
  ) || []

  const toggleItem = (id: number) => {
    const newSelected = new Set(selectedItems)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedItems(newSelected)
  }

  const selectAll = () => {
    setSelectedItems(new Set(availableItems.map(i => i.ingredient_id)))
  }

  const selectNone = () => {
    setSelectedItems(new Set())
  }

  const handleSubmitOrder = async () => {
    if (selectedItems.size === 0) return
    // Calculate and store the totals BEFORE submission
    const selectedSuggestions = availableItems.filter(s => selectedItems.has(s.ingredient_id))
    const totalCost = selectedSuggestions.reduce((sum, s) => sum + s.estimated_cost, 0)
    setSubmittedOrderInfo({ count: selectedItems.size, total: totalCost })
    
    setIsSubmitting(true)
    await new Promise(resolve => setTimeout(resolve, 1500))
    onSubmitOrder(Array.from(selectedItems))
    setIsSubmitting(false)
    setOrderSubmitted(true)
  }

  const handleClose = () => {
    setOrderSubmitted(false)
    setSubmittedOrderInfo(null)
    setSelectedItems(new Set()) // Start with nothing selected
    onClose()
  }

  if (!isOpen) return null

  const selectedSuggestions = availableItems.filter(s => selectedItems.has(s.ingredient_id))
  const totalCost = selectedSuggestions.reduce((sum, s) => sum + s.estimated_cost, 0)

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
              <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center">
                <ShoppingCart className="w-5 h-5 text-brand-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-text-primary">Generate Purchase Order</h3>
                <p className="text-sm text-text-secondary">Select items to order</p>
              </div>
            </div>
            <button onClick={handleClose} className="p-2 rounded-lg hover:bg-gray-100">
              <X className="w-5 h-5 text-text-secondary" />
            </button>
          </div>

          {/* Content */}
          <div className="p-5 max-h-96 overflow-y-auto">
            {orderSubmitted && submittedOrderInfo ? (
              <motion.div 
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="text-center py-8"
              >
                <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
                <h4 className="text-lg font-semibold text-text-primary mb-2">Order Submitted!</h4>
                <p className="text-text-secondary">
                  {submittedOrderInfo.count} items ordered for ${submittedOrderInfo.total.toFixed(2)}
                </p>
                <p className="text-sm text-text-tertiary mt-2">Order #PO-{Math.floor(Math.random() * 10000)}</p>
              </motion.div>
            ) : availableItems.length === 0 ? (
              <div className="text-center py-8">
                <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-gray-400" />
                </div>
                <h4 className="text-lg font-semibold text-text-primary mb-2">All Items Ordered</h4>
                <p className="text-text-secondary">All suggested items have already been ordered.</p>
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
                
                {availableItems.map((item) => (
                  <div 
                    key={item.ingredient_id}
                    onClick={() => toggleItem(item.ingredient_id)}
                    className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all ${
                      selectedItems.has(item.ingredient_id) 
                        ? 'bg-brand-primary/10 border-2 border-brand-primary/30' 
                        : 'bg-surface-secondary border-2 border-transparent hover:border-gray-200'
                    }`}
                  >
                    <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-colors ${
                      selectedItems.has(item.ingredient_id) 
                        ? 'bg-brand-primary border-brand-primary' 
                        : 'border-gray-300'
                    }`}>
                      {selectedItems.has(item.ingredient_id) && (
                        <Check className="w-3 h-3 text-white" />
                      )}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-text-primary text-sm">{item.ingredient_name}</p>
                      <p className="text-xs text-text-secondary">
                        Current: {item.current_stock} • Order: {item.suggested_quantity}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-brand-primary">${item.estimated_cost.toFixed(2)}</p>
                      <Badge variant={item.urgency === 'critical' ? 'error' : item.urgency === 'high' ? 'warning' : 'default'} size="sm">
                        {item.urgency}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-5 border-t border-gray-100 bg-surface-secondary">
            {!orderSubmitted && availableItems.length > 0 ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-text-secondary">Total Order</p>
                  <p className="text-xl font-bold text-text-primary">${totalCost.toFixed(2)}</p>
                </div>
                <div className="flex gap-3">
                  <Button variant="secondary" onClick={handleClose}>Cancel</Button>
                  <Button onClick={handleSubmitOrder} disabled={isSubmitting || selectedItems.size === 0}>
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Submitting...
                      </>
                    ) : (
                      `Submit Order (${selectedItems.size})`
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

// Skeleton loader for stat cards
const StatCardSkeleton = () => (
  <motion.div 
    className="bg-white rounded-2xl p-5 shadow-soft border border-gray-100"
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
    <div className="mt-2 text-xs text-text-tertiary flex items-center gap-1">
      <Loader2 className="w-3 h-3 animate-spin" />
      <span>Loading from Databricks SQL Warehouse...</span>
    </div>
  </motion.div>
)

// Category filter tabs — keys must match domain.yaml `ingredient_categories`.
// generate.py regenerates this list from the customer's domain (patch below).
const categories = [
  { key: null, label: 'All' },
  { key: 'produce', label: 'Produce' },
  { key: 'deli', label: 'Deli' },
  { key: 'bakery', label: 'Bakery' },
  { key: 'meat', label: 'Meat' },
  { key: 'dairy', label: 'Dairy' },
  { key: 'frozen', label: 'Frozen' },
  { key: 'grocery', label: 'Grocery' },
]

export default function Inventory() {
  const { storeId, orderedItems, submitInventoryOrders, clearInventoryOrders } = useOutletContext<StoreContext>()
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [showOrderModal, setShowOrderModal] = useState(false)
  const [isClearing, setIsClearing] = useState(false)

  const handleSubmitOrder = async (selectedIds: number[]) => {
    const suggestions_data = suggestions || []
    const items = selectedIds.map(id => {
      const sug = suggestions_data.find((s: any) => s.ingredient_id === id)
      return {
        ingredient_id: id,
        ingredient_name: sug?.ingredient_name || `Item #${id}`,
        suggested_quantity: sug?.suggested_quantity,
        estimated_cost: sug?.estimated_cost,
        urgency: sug?.urgency,
      }
    })
    await submitInventoryOrders(items)
  }

  const handleClearOrders = async () => {
    setIsClearing(true)
    await clearInventoryOrders()
    setIsClearing(false)
  }

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['inventory-summary', storeId],
    queryFn: () => api.getInventorySummary(storeId),
  })

  const { data: levels, isLoading: loadingLevels } = useQuery({
    queryKey: ['inventory-levels', storeId, selectedCategory],
    queryFn: () => api.getInventoryLevels(storeId, selectedCategory || undefined),
  })

  const { data: deliveries, isLoading: loadingDeliveries } = useQuery({
    queryKey: ['deliveries', storeId],
    queryFn: () => api.getDeliveries(storeId),
  })

  const { data: suggestions, isLoading: loadingSuggestions } = useQuery({
    queryKey: ['order-suggestions', storeId],
    queryFn: () => api.getOrderSuggestions(storeId),
  })

  const getStatusColor = (status: string) => ({
    good: 'bg-green-500',
    low: 'bg-amber-500',
    critical: 'bg-red-500',
    overstocked: 'bg-blue-500',
  }[status] || 'bg-gray-500')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-text-primary">Inventory</h2>
        <p className="text-text-secondary">Stock levels and reorder suggestions</p>
      </div>

      {/* Summary Stats */}
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
                label="Total Items"
                value={summary?.total_items || '—'}
                icon={<Package className="w-5 h-5" />}
              />
              <StatCard
                label="Low Stock"
                value={summary?.items_low || '—'}
                icon={<AlertTriangle className="w-5 h-5" />}
                trend={summary?.items_low > 5 ? 'down' : 'up'}
              />
              <StatCard
                label="Critical"
                value={summary?.items_critical || '—'}
                icon={<TrendingDown className="w-5 h-5" />}
                trend="down"
              />
              <StatCard
                label="Inventory Value"
                value={summary?.total_inventory_value ? `$${summary.total_inventory_value.toLocaleString()}` : '—'}
                icon={<DollarSign className="w-5 h-5" />}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Inventory Levels */}
        <Card className="lg:col-span-2">
          <CardHeader 
            title="Stock Levels" 
            icon={<Package className="w-5 h-5" />}
            action={
              <div className="flex gap-1.5 overflow-x-auto">
                {categories.map((cat) => (
                  <button
                    key={cat.key || 'all'}
                    onClick={() => setSelectedCategory(cat.key)}
                    className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
                      selectedCategory === cat.key
                        ? 'bg-brand-primary text-white'
                        : 'bg-gray-100 text-text-secondary hover:bg-gray-200'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            }
          />
          <AnimatePresence mode="wait">
            {loadingLevels ? (
              <LoadingState message="Loading inventory from Databricks SQL Warehouse..." />
            ) : levels?.length ? (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }}
                className="space-y-2 max-h-96 overflow-y-auto"
              >
                {levels.map((item, index) => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.02 }}
                    className="flex items-center gap-4 p-3 bg-surface-secondary rounded-xl"
                  >
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColor(item.status)}`} />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-text-primary text-sm">{item.name}</p>
                      <p className="text-xs text-text-tertiary">{item.category}</p>
                    </div>
                    <div className="w-28 flex-shrink-0 text-right">
                      <p className="font-medium text-text-primary tabular-nums">
                        {item.current_stock} {item.unit}
                      </p>
                      <p className="text-xs text-text-secondary">
                        {item.days_supply} days supply
                      </p>
                    </div>
                    <div className="w-20 flex-shrink-0">
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${getStatusColor(item.status)}`}
                          style={{ width: `${Math.min(100, (item.current_stock / item.par_level) * 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-text-tertiary mt-1 text-right tabular-nums">
                        Par: {item.par_level}
                      </p>
                    </div>
                    <div className="w-16 flex-shrink-0">
                      <StatusBadge status={item.status} />
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No inventory data</div>
            )}
          </AnimatePresence>
        </Card>

        {/* Upcoming Deliveries */}
        <Card>
          <CardHeader 
            title="Deliveries" 
            icon={<Truck className="w-5 h-5" />}
          />
          <AnimatePresence mode="wait">
            {loadingDeliveries ? (
              <LoadingState message="Loading deliveries from Databricks SQL Warehouse..." />
            ) : deliveries?.length ? (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                {deliveries.map((delivery, index) => (
                  <motion.div
                    key={delivery.id}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="p-4 border border-gray-100 rounded-xl"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-text-primary">{delivery.supplier}</span>
                      <Badge 
                        variant={delivery.status === 'delivered' ? 'success' : 'info'}
                        size="sm"
                      >
                        {delivery.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-text-secondary mb-2">
                      {delivery.expected_date} • {delivery.expected_time}
                    </p>
                    <div className="text-xs text-text-tertiary">
                      {delivery.items.slice(0, 3).map((item: any) => item.name).join(', ')}
                      {delivery.items.length > 3 && ` +${delivery.items.length - 3} more`}
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No deliveries scheduled</div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* Order Suggestions */}
      <Card>
        <CardHeader 
          title="ML Order Suggestions" 
          subtitle="Based on demand forecast and usage patterns"
          icon={<AlertTriangle className="w-5 h-5" />}
          action={
            <div className="flex gap-2">
              {orderedItems.length > 0 && (
                <Button size="sm" variant="secondary" onClick={handleClearOrders} disabled={isClearing}>
                  {isClearing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                  Clear Orders
                </Button>
              )}
              <Button size="sm" onClick={() => setShowOrderModal(true)}>Generate Order</Button>
            </div>
          }
        />
        
        {/* Order Modal */}
        <OrderModal 
          isOpen={showOrderModal} 
          onClose={() => setShowOrderModal(false)} 
          suggestions={suggestions || []}
          orderedItems={orderedItems}
          onSubmitOrder={handleSubmitOrder}
        />
        <AnimatePresence mode="wait">
          {loadingSuggestions ? (
            <LoadingState message="Generating order suggestions from Databricks Model Serving..." />
          ) : suggestions?.length ? (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }}
              className="overflow-x-auto max-h-96 overflow-y-auto"
            >
              <table className="w-full">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="text-left text-sm text-text-secondary border-b border-gray-100">
                    <th className="pb-3 font-medium">Ingredient</th>
                    <th className="pb-3 font-medium">Current</th>
                    <th className="pb-3 font-medium">Suggested Qty</th>
                    <th className="pb-3 font-medium">Est. Cost</th>
                    <th className="pb-3 font-medium">Urgency</th>
                    <th className="pb-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {suggestions.map((sug, index) => {
                    const orderedItem = orderedItems.find(o => o.ingredient_id === sug.ingredient_id)
                    const isOrdered = !!orderedItem
                    
                    return (
                      <motion.tr
                        key={sug.ingredient_id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: index * 0.05 }}
                        className={`border-b border-gray-50 last:border-0 relative ${isOrdered ? 'bg-gradient-to-r from-green-50/80 via-emerald-50/60 to-teal-50/40' : ''}`}
                        style={isOrdered ? {
                          backdropFilter: 'blur(8px)',
                        } : {}}
                      >
                        <td className="py-3 font-medium text-text-primary">
                          <div className="flex items-center gap-2">
                            {isOrdered && <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />}
                            {sug.ingredient_name}
                          </div>
                        </td>
                        <td className="py-3 text-text-secondary">{sug.current_stock}</td>
                        <td className="py-3 font-medium text-brand-primary">{sug.suggested_quantity}</td>
                        <td className="py-3 text-text-secondary">${sug.estimated_cost.toFixed(2)}</td>
                        <td className="py-3">
                          <Badge 
                            variant={sug.urgency === 'critical' ? 'error' : sug.urgency === 'high' ? 'warning' : 'default'}
                            size="sm"
                          >
                            {sug.urgency}
                          </Badge>
                        </td>
                        <td className="py-3">
                          {isOrdered ? (
                            <div className="flex items-center gap-1.5">
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">
                                <CheckCircle className="w-3 h-3" />
                                Order placed
                              </span>
                              <span className="text-xs text-text-tertiary">{orderedItem.orderedAt}</span>
                            </div>
                          ) : (
                            <span className="text-text-tertiary text-xs">{sug.reason}</span>
                          )}
                        </td>
                      </motion.tr>
                    )
                  })}
                </tbody>
              </table>
            </motion.div>
          ) : (
            <div className="py-8 text-center text-text-tertiary">No order suggestions</div>
          )}
        </AnimatePresence>
      </Card>
    </div>
  )
}


