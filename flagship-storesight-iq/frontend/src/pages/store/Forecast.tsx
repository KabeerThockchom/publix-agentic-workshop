import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { brand } from '../../brand'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line
} from 'recharts'
import { TrendingUp, Calendar, Sun, CloudRain, Ticket, ChefHat, Loader2, MapPin, Thermometer, Wind, Gauge } from 'lucide-react'
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
      <span>Loading from Databricks Model Serving...</span>
    </div>
  </motion.div>
)

export default function Forecast() {
  const palette = brand()
  const { storeId } = useOutletContext<StoreContext>()

  const { data: weeklyForecast, isLoading: loadingWeekly } = useQuery({
    queryKey: ['weekly-forecast', storeId],
    queryFn: () => api.getWeeklyForecast(storeId),
  })

  const { data: hourlyForecast, isLoading: loadingHourly } = useQuery({
    queryKey: ['hourly-forecast', storeId],
    queryFn: () => api.getHourlyForecast(storeId),
  })

  const { data: prepRecs, isLoading: loadingPrep } = useQuery({
    queryKey: ['prep-recommendations', storeId],
    queryFn: () => api.getPrepRecommendations(storeId, 'lunch'),
  })

  // Fetch weather and events for hover tooltips
  const { data: weather } = useQuery({
    queryKey: ['weather', storeId],
    queryFn: () => api.getCurrentWeather(storeId),
    staleTime: 300000, // 5 minutes
  })

  const { data: events } = useQuery({
    queryKey: ['events', storeId],
    queryFn: () => api.getLocalEvents(storeId),
    staleTime: 3600000, // 1 hour
  })

  // Hover state for tooltips
  const [showWeatherTooltip, setShowWeatherTooltip] = useState(false)
  const [showEventsTooltip, setShowEventsTooltip] = useState(false)
  const [showSeasonalityTooltip, setShowSeasonalityTooltip] = useState(false)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-text-primary">Demand Forecast</h2>
          <p className="text-text-secondary">ML-powered predictions for your store</p>
        </div>
        <Badge variant="success">
          Model accuracy: {weeklyForecast?.model_accuracy ? `${(weeklyForecast.model_accuracy * 100).toFixed(0)}%` : '—'}
        </Badge>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <AnimatePresence mode="wait">
          {loadingWeekly ? (
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
                label="Today's Forecast"
                value={weeklyForecast?.daily_forecasts?.[0]?.predicted_transactions?.toLocaleString() || '—'}
                changeLabel="transactions"
                icon={<TrendingUp className="w-5 h-5" />}
              />
              <StatCard
                label="Today's Revenue"
                value={weeklyForecast?.daily_forecasts?.[0]?.predicted_revenue 
                  ? `$${weeklyForecast.daily_forecasts[0].predicted_revenue.toLocaleString()}`
                  : '—'}
                icon={<Calendar className="w-5 h-5" />}
              />
              <StatCard
                label="Week Total"
                value={weeklyForecast?.daily_forecasts
                  ? `$${weeklyForecast.daily_forecasts.reduce((sum: number, d: any) => sum + d.predicted_revenue, 0).toLocaleString()}`
                  : '—'}
                icon={<TrendingUp className="w-5 h-5" />}
              />
              <StatCard
                label="Confidence"
                value={weeklyForecast?.daily_forecasts?.[0]?.confidence 
                  ? `${(weeklyForecast.daily_forecasts[0].confidence * 100).toFixed(0)}%`
                  : '—'}
                icon={<Gauge className="w-5 h-5" />}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* 7-Day Forecast */}
        <Card>
          <CardHeader 
            title="7-Day Forecast" 
            subtitle="Daily transaction predictions"
            icon={<Calendar className="w-5 h-5" />}
          />
          <AnimatePresence mode="wait">
            {loadingWeekly ? (
              <div className="h-64">
                <LoadingState message="Loading forecast from ML model endpoint..." />
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={weeklyForecast?.daily_forecasts || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                      <XAxis 
                        dataKey="day_of_week" 
                        tick={{ fontSize: 12, fill: '#9CA3AF' }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(day) => day.slice(0, 3)}
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
                        formatter={(value: number) => [value.toLocaleString(), 'Transactions']}
                      />
                      <Bar 
                        dataKey="predicted_transactions" 
                        fill={palette.primary} 
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Weather & Event Impacts */}
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs text-text-secondary mb-2">Factors impacting forecast:</p>
                  <div className="flex flex-wrap gap-2">
                    {weeklyForecast?.daily_forecasts?.some((d: any) => d.weather_impact !== 'neutral') && (
                      <div 
                        className="relative"
                        onMouseEnter={() => setShowWeatherTooltip(true)}
                        onMouseLeave={() => setShowWeatherTooltip(false)}
                      >
                        <div className="cursor-pointer">
                          <Badge variant="info" size="md">
                            <Sun className="w-3 h-3" /> Weather adjusted
                          </Badge>
                        </div>
                        <AnimatePresence>
                          {showWeatherTooltip && weather && (
                            <motion.div
                              initial={{ opacity: 0, y: 5, scale: 0.95 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: 5, scale: 0.95 }}
                              className="absolute bottom-full left-0 mb-2 w-64 p-4 bg-white rounded-xl shadow-strong border border-gray-100 z-50"
                            >
                              <div className="flex items-center gap-3 mb-3">
                                <span className="text-3xl">{weather.condition_icon}</span>
                                <div>
                                  <p className="font-semibold text-text-primary text-lg">{weather.temperature}°F</p>
                                  <p className="text-sm text-text-secondary">{weather.condition_label}</p>
                                </div>
                              </div>
                              <div className="space-y-2 text-sm">
                                <div className="flex items-center gap-2 text-text-secondary">
                                  <MapPin className="w-4 h-4" />
                                  <span>{weather.location}</span>
                                </div>
                                <div className="flex items-center gap-2 text-text-secondary">
                                  <Wind className="w-4 h-4" />
                                  <span>{weather.wind_speed} mph</span>
                                </div>
                                {weather.sales_impact && (
                                  <div className={`mt-2 p-2 rounded-lg text-xs ${
                                    weather.sales_impact.trend === 'up' ? 'bg-green-50 text-green-700' :
                                    weather.sales_impact.trend === 'mixed' ? 'bg-amber-50 text-amber-700' :
                                    'bg-gray-50 text-gray-600'
                                  }`}>
                                    <span className="font-medium">Sales Impact: </span>
                                    {weather.sales_impact.message}
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                    {weeklyForecast?.daily_forecasts?.some((d: any) => d.event_impact !== 'none') && (
                      <div 
                        className="relative"
                        onMouseEnter={() => setShowEventsTooltip(true)}
                        onMouseLeave={() => setShowEventsTooltip(false)}
                      >
                        <div className="cursor-pointer">
                          <Badge variant="info" size="md">
                            <Ticket className="w-3 h-3" /> Events nearby
                          </Badge>
                        </div>
                        <AnimatePresence>
                          {showEventsTooltip && events?.events?.length > 0 && (
                            <motion.div
                              initial={{ opacity: 0, y: 5, scale: 0.95 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: 5, scale: 0.95 }}
                              className="absolute bottom-full left-0 mb-2 w-80 p-4 bg-white rounded-xl shadow-strong border border-gray-100 z-50"
                            >
                              <div className="flex items-center gap-2 mb-3">
                                <Ticket className="w-5 h-5 text-purple-600" />
                                <p className="font-semibold text-text-primary">
                                  {events.event_count} Events This Week
                                </p>
                              </div>
                              {/* Scrollable events list */}
                              <ul className="space-y-2 max-h-64 overflow-y-auto pr-1">
                                {events.events.map((event: any, idx: number) => (
                                  <li key={idx} className="flex items-start gap-2 text-sm p-2 bg-surface-secondary rounded-lg">
                                    <span className="text-base flex-shrink-0">
                                      {event.type === 'sports' ? '🏟️' : 
                                       event.type === 'music' ? '🎵' : '📅'}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                      <p className="font-medium text-text-primary truncate">{event.name}</p>
                                      <p className="text-xs text-text-secondary">
                                        {event.date} {event.time && `• ${event.time}`}
                                      </p>
                                      <p className="text-xs text-text-tertiary truncate">{event.venue}</p>
                                    </div>
                                  </li>
                                ))}
                              </ul>
                              {events.traffic_impact !== 'none' && (
                                <div className={`mt-3 p-2 rounded-lg text-xs ${
                                  events.traffic_impact === 'high' ? 'bg-amber-50 text-amber-700' :
                                  'bg-blue-50 text-blue-700'
                                }`}>
                                  Traffic impact: {events.traffic_impact}
                                </div>
                              )}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                    {weeklyForecast?.factors?.seasonality && (
                      <div 
                        className="relative"
                        onMouseEnter={() => setShowSeasonalityTooltip(true)}
                        onMouseLeave={() => setShowSeasonalityTooltip(false)}
                      >
                        <div className="cursor-pointer">
                          <Badge variant="default" size="md">
                            <CloudRain className="w-3 h-3" /> Seasonality: {weeklyForecast.factors.seasonality}
                          </Badge>
                        </div>
                        <AnimatePresence>
                          {showSeasonalityTooltip && weather && (
                            <motion.div
                              initial={{ opacity: 0, y: 5, scale: 0.95 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: 5, scale: 0.95 }}
                              className="absolute bottom-full left-0 mb-2 w-64 p-4 bg-white rounded-xl shadow-strong border border-gray-100 z-50"
                            >
                              <div className="flex items-center gap-2 mb-3">
                                <span className="text-2xl">{weather.condition_icon}</span>
                                <div>
                                  <p className="font-semibold text-text-primary">Current Weather</p>
                                  <p className="text-xs text-text-secondary">{weeklyForecast.factors.seasonality} season</p>
                                </div>
                              </div>
                              <div className="grid grid-cols-2 gap-3">
                                <div className="bg-surface-secondary rounded-lg p-2 text-center">
                                  <Thermometer className="w-4 h-4 mx-auto text-text-secondary mb-1" />
                                  <p className="text-lg font-semibold text-text-primary">{weather.temperature}°F</p>
                                  <p className="text-xs text-text-secondary">Temperature</p>
                                </div>
                                <div className="bg-surface-secondary rounded-lg p-2 text-center">
                                  <Wind className="w-4 h-4 mx-auto text-text-secondary mb-1" />
                                  <p className="text-lg font-semibold text-text-primary">{weather.wind_speed}</p>
                                  <p className="text-xs text-text-secondary">Wind (mph)</p>
                                </div>
                              </div>
                              <div className="mt-3 flex items-center gap-2">
                                <MapPin className="w-4 h-4 text-text-tertiary" />
                                <span className="text-sm text-text-secondary">{weather.location}</span>
                              </div>
                              <div className="mt-2 p-2 bg-blue-50 rounded-lg">
                                <p className="text-xs text-blue-700">
                                  <span className="font-medium">{weather.condition_label}</span>
                                  {weather.sales_impact && ` — ${weather.sales_impact.message}`}
                                </p>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </Card>

        {/* Hourly Forecast */}
        <Card>
          <CardHeader 
            title="Today's Hourly Forecast" 
            subtitle="Transaction predictions by hour"
          />
          <AnimatePresence mode="wait">
            {loadingHourly ? (
              <div className="h-64">
                <LoadingState message="Querying Databricks Model Serving..." />
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={hourlyForecast || []}>
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
                      <Line 
                        type="monotone"
                        dataKey="predicted_transactions" 
                        name="Predicted"
                        stroke={palette.primary} 
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Daypart breakdown */}
                <div className="mt-4 grid grid-cols-5 gap-2 text-center">
                  {['Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Evening'].map((daypart, i) => {
                    const colors = ['bg-amber-100', 'bg-green-100', 'bg-blue-100', 'bg-orange-100', 'bg-purple-100']
                    return (
                      <div key={daypart} className={`${colors[i]} rounded-lg p-2`}>
                        <p className="text-xs text-text-secondary">{daypart}</p>
                        <p className="font-semibold text-sm">{[35, 120, 40, 75, 15][i]}</p>
                      </div>
                    )
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      {/* Prep Recommendations */}
      <Card>
        <CardHeader 
          title="Prep Recommendations" 
          subtitle="Based on lunch rush forecast"
          icon={<ChefHat className="w-5 h-5" />}
        />
        <AnimatePresence mode="wait">
          {loadingPrep ? (
            <LoadingState message="Generating prep recommendations from ML model..." />
          ) : prepRecs?.length ? (
            <motion.div 
              className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {prepRecs.map((rec, index) => (
                <motion.div
                  key={rec.item}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 bg-surface-secondary rounded-xl"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-text-primary">{rec.item}</span>
                    <Badge variant={rec.priority === 'high' ? 'warning' : 'default'} size="sm">
                      {rec.priority}
                    </Badge>
                  </div>
                  <p className="text-2xl font-semibold text-brand-primary">{rec.quantity}</p>
                  <p className="text-xs text-text-secondary mt-1">Prep time: {rec.prep_time}</p>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <div className="py-8 text-center text-text-tertiary">
              No prep recommendations available
            </div>
          )}
        </AnimatePresence>
      </Card>
    </div>
  )
}


