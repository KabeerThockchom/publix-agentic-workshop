import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, TooltipProps 
} from 'recharts'
import { motion } from 'framer-motion'
import { brand } from '../../brand'

interface SalesChartProps {
  data: Array<{
    hour: number
    sales: number
    transactions?: number
    vs_forecast?: number
  }>
  height?: number
  showForecast?: boolean
}

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null

  const formatHour = (hour: number) => {
    if (hour === 0) return '12 AM'
    if (hour < 12) return `${hour} AM`
    if (hour === 12) return '12 PM'
    return `${hour - 12} PM`
  }

  return (
    <div className="custom-tooltip">
      <p className="font-medium text-text-primary mb-1">{formatHour(label as number)}</p>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <span 
            className="w-2 h-2 rounded-full" 
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-text-secondary">{entry.name}:</span>
          <span className="font-medium text-text-primary">
            {entry.name === 'Sales' ? `$${entry.value?.toLocaleString()}` : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function SalesChart({ data, height = 300 }: SalesChartProps) {
  const palette = brand()
  const formatHour = (hour: number) => {
    if (hour === 0) return '12A'
    if (hour < 12) return `${hour}A`
    if (hour === 12) return '12P'
    return `${hour - 12}P`
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{ height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="salesGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={palette.primary} stopOpacity={0.2} />
              <stop offset="95%" stopColor={palette.primary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
          <XAxis 
            dataKey="hour" 
            tickFormatter={formatHour}
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis 
            tick={{ fontSize: 12, fill: '#9CA3AF' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `$${value}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="sales"
            name="Sales"
            stroke={palette.primary}
            strokeWidth={2}
            fill="url(#salesGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  )
}



