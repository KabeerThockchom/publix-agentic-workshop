import { useQuery } from '@tanstack/react-query'
import { brand } from '../../brand'
import { motion, AnimatePresence } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Users, Clock, DollarSign, TrendingUp, AlertCircle, Loader2 } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../../api/client'
import { Card, CardHeader, StatCard } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'

interface StoreContext {
  storeId: number
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

export default function Labor() {
  const palette = brand()
  const { storeId } = useOutletContext<StoreContext>()

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['labor-summary', storeId],
    queryFn: () => api.getLaborSummary(storeId),
  })

  const { data: schedule, isLoading: loadingSchedule } = useQuery({
    queryKey: ['schedule', storeId],
    queryFn: () => api.getSchedule(storeId),
  })

  const { data: hourlyLabor, isLoading: loadingHourly } = useQuery({
    queryKey: ['hourly-labor', storeId],
    queryFn: () => api.getHourlyLabor(storeId),
  })

  const { data: recommendations, isLoading: loadingRecs } = useQuery({
    queryKey: ['staffing-recommendations', storeId],
    queryFn: () => api.getStaffingRecommendations(storeId),
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-text-primary">Labor Management</h2>
        <p className="text-text-secondary">Scheduling and optimization</p>
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
                label="Hours Scheduled"
                value={summary?.total_scheduled_hours?.toFixed(1) || '—'}
                icon={<Clock className="w-5 h-5" />}
              />
              <StatCard
                label="Hours Worked"
                value={summary?.total_actual_hours?.toFixed(1) || '—'}
                icon={<Users className="w-5 h-5" />}
              />
              <StatCard
                label="Labor Cost"
                value={summary?.labor_cost ? `$${summary.labor_cost.toLocaleString()}` : '—'}
                icon={<DollarSign className="w-5 h-5" />}
              />
              <StatCard
                label="Labor Cost %"
                value={summary?.labor_cost_pct ? `${summary.labor_cost_pct.toFixed(1)}%` : '—'}
                changeLabel="of sales"
                icon={<TrendingUp className="w-5 h-5" />}
                trend={summary?.labor_cost_pct <= 26 ? 'up' : 'down'}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Hourly Staffing Chart */}
        <Card className="lg:col-span-2">
          <CardHeader 
            title="Hourly Staffing" 
            subtitle="Scheduled vs optimal staffing levels"
            icon={<Users className="w-5 h-5" />}
          />
          <AnimatePresence mode="wait">
            {loadingHourly ? (
              <div className="h-64">
                <LoadingState message="Loading staffing data from Databricks SQL Warehouse..." />
              </div>
            ) : (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hourlyLabor || []} barGap={2}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                      <XAxis 
                        dataKey="hour_label"
                        tick={{ fontSize: 11, fill: '#9CA3AF' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis 
                        tick={{ fontSize: 12, fill: '#9CA3AF' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(255, 255, 255, 0.95)',
                          border: 'none',
                          borderRadius: '12px',
                          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
                        }}
                      />
                      <Bar 
                        dataKey="scheduled_staff" 
                        name="Scheduled"
                        fill={palette.primary} 
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar 
                        dataKey="optimal_staff" 
                        name="Optimal"
                        fill={palette.secondary} 
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Status Legend */}
                <div className="flex gap-4 mt-4 pt-4 border-t border-gray-100">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded bg-brand-primary" />
                    <span className="text-sm text-text-secondary">Scheduled</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded bg-brand-secondary" />
                    <span className="text-sm text-text-secondary">ML Optimal</span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </Card>

        {/* Today's Schedule */}
        <Card>
          <CardHeader title="Today's Schedule" subtitle={`${schedule?.length || 0} shifts`} />
          <AnimatePresence mode="wait">
            {loadingSchedule ? (
              <LoadingState message="Loading schedule from Databricks SQL Warehouse..." />
            ) : schedule?.length ? (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }}
                className="space-y-2 max-h-80 overflow-y-auto"
              >
                {schedule.map((shift, index) => (
                  <motion.div
                    key={shift.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="flex items-center gap-3 p-3 bg-surface-secondary rounded-xl"
                  >
                    <div className="w-10 h-10 rounded-full bg-brand-primary/10 flex items-center justify-center text-sm font-medium text-brand-primary">
                      {shift.employee_name.split(' ').map((n: string) => n[0]).join('')}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-text-primary text-sm truncate">
                        {shift.employee_name}
                      </p>
                      <p className="text-xs text-text-secondary">
                        {shift.start_time} - {shift.end_time}
                      </p>
                    </div>
                    <Badge variant={shift.status === 'in_progress' ? 'success' : 'default'} size="sm">
                      {shift.status === 'in_progress' ? 'Active' : shift.status}
                    </Badge>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <div className="py-8 text-center text-text-tertiary">No shifts scheduled</div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* ML Recommendations */}
      <Card>
        <CardHeader 
          title="AI Staffing Recommendations" 
          subtitle="Optimization suggestions based on forecast"
          icon={<AlertCircle className="w-5 h-5" />}
          action={
            <Badge variant="info">
              {recommendations?.filter((r: any) => r.action !== 'optimal').length || 0} adjustments needed
            </Badge>
          }
        />
        <AnimatePresence mode="wait">
          {loadingRecs ? (
            <LoadingState message="Generating recommendations from Databricks Model Serving..." />
          ) : recommendations?.filter((r: any) => r.action !== 'optimal').length ? (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }}
              className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4"
            >
              {recommendations.filter((r: any) => r.action !== 'optimal').slice(0, 6).map((rec: any, index: number) => (
                <motion.div
                  key={rec.hour}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={`p-4 rounded-xl border-l-4 ${
                    rec.action === 'add_staff' 
                      ? 'bg-red-50 border-red-500'
                      : 'bg-amber-50 border-amber-500'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-text-primary">{rec.hour_label}</span>
                    <Badge 
                      variant={rec.action === 'add_staff' ? 'error' : 'warning'} 
                      size="sm"
                    >
                      {rec.action === 'add_staff' ? '+' : '-'}{Math.abs(rec.recommended_staff - rec.current_scheduled)} staff
                    </Badge>
                  </div>
                  <p className="text-sm text-text-secondary">{rec.reason}</p>
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <span className="text-text-tertiary">Demand: {rec.forecasted_demand} txn/hr</span>
                    <span className="text-text-tertiary">•</span>
                    <span className="text-text-tertiary">{(rec.confidence * 100).toFixed(0)}% conf</span>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <div className="py-8 text-center text-text-tertiary">
              <div className="text-3xl mb-2">✓</div>
              <p>Staffing is optimally scheduled</p>
            </div>
          )}
        </AnimatePresence>
      </Card>
    </div>
  )
}


