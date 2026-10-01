import { motion, HTMLMotionProps } from 'framer-motion'
import { ReactNode } from 'react'

interface CardProps extends HTMLMotionProps<"div"> {
  children: ReactNode
  className?: string
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export function Card({ 
  children, 
  className = '', 
  hover = false,
  padding = 'md',
  ...props 
}: CardProps) {
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }

  return (
    <motion.div
      className={`
        bg-white rounded-2xl border border-gray-100 shadow-soft
        ${hover ? 'card-hover' : ''}
        ${paddingClasses[padding]}
        ${className}
      `}
      {...props}
    >
      {children}
    </motion.div>
  )
}

interface CardHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
  icon?: ReactNode
}

export function CardHeader({ title, subtitle, action, icon }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div className="flex items-center gap-3">
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center text-brand-primary">
            {icon}
          </div>
        )}
        <div>
          <h3 className="font-semibold text-text-primary">{title}</h3>
          {subtitle && <p className="text-sm text-text-secondary">{subtitle}</p>}
        </div>
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: string | number
  change?: number
  changeLabel?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'flat'
}

export function StatCard({ label, value, change, changeLabel, icon, trend }: StatCardProps) {
  const trendColors = {
    up: 'text-green-600 bg-green-50',
    down: 'text-red-600 bg-red-50',
    flat: 'text-gray-600 bg-gray-100',
  }

  return (
    <Card hover className="relative overflow-hidden">
      {/* Background accent */}
      <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
        <div className="w-full h-full rounded-full bg-brand-primary transform translate-x-8 -translate-y-8" />
      </div>
      
      <div className="relative">
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center text-brand-primary mb-3">
            {icon}
          </div>
        )}
        
        <p className="text-sm text-text-secondary mb-1">{label}</p>
        <p className="text-2xl font-semibold text-text-primary tabular-nums">{value}</p>
        
        {(change !== undefined || changeLabel) && (
          <div className="flex items-center gap-2 mt-2">
            {change !== undefined && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${trendColors[trend || (change >= 0 ? 'up' : 'down')]}`}>
                {change >= 0 ? '+' : ''}{change}%
              </span>
            )}
            {changeLabel && (
              <span className="text-xs text-text-tertiary">{changeLabel}</span>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}





