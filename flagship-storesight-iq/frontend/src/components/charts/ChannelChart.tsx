import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import { motion } from 'framer-motion'
import { brand } from '../../brand'

interface ChannelData {
  channel: string
  sales: number
  transactions: number
  percentage: number
}

interface ChannelChartProps {
  data: ChannelData[]
  height?: number
}

const formatChannel = (channel: string) => {
  // NOTE: channel display labels are customer-specific copy — generate.py
  // overwrites these from domain.yaml (sales_channels). Neutral defaults below.
  const labels: Record<string, string> = {
    in_store: 'In-Store',
    delivery: 'Delivery',
    app: 'Mobile App',
    third_party: '3rd Party',
  }
  return labels[channel] || channel
}

export function ChannelChart({ data, height = 200 }: ChannelChartProps) {
  const COLORS = brand().series
  const formattedData = data.map(d => ({
    ...d,
    name: formatChannel(d.channel),
  }))

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      style={{ height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={formattedData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={70}
            paddingAngle={3}
            dataKey="sales"
          >
            {formattedData.map((_, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={COLORS[index % COLORS.length]}
                className="drop-shadow-sm"
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number) => [`$${value.toLocaleString()}`, 'Sales']}
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: 'none',
              borderRadius: '12px',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
            }}
          />
          <Legend
            verticalAlign="middle"
            align="right"
            layout="vertical"
            formatter={(value) => <span className="text-sm text-text-primary">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </motion.div>
  )
}

export function ChannelBreakdown({ data }: { data: ChannelData[] }) {
  const COLORS = brand().series
  return (
    <div className="space-y-3">
      {data.map((channel, index) => (
        <motion.div
          key={channel.channel}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: index * 0.1 }}
          className="flex items-center gap-3"
        >
          <div 
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: COLORS[index % COLORS.length] }}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-text-primary truncate">
                {formatChannel(channel.channel)}
              </span>
              <span className="text-sm text-text-secondary tabular-nums">
                ${channel.sales.toLocaleString()}
              </span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
                initial={{ width: 0 }}
                animate={{ width: `${channel.percentage}%` }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
              />
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  )
}





