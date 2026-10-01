import { ReactNode } from 'react'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info'

interface BadgeProps {
  children: ReactNode
  variant?: BadgeVariant
  size?: 'sm' | 'md'
  dot?: boolean
}

const variants: Record<BadgeVariant, string> = {
  default: 'bg-gray-100 text-gray-700',
  success: 'bg-green-50 text-green-700',
  warning: 'bg-amber-50 text-amber-700',
  error: 'bg-red-50 text-red-700',
  info: 'bg-blue-50 text-blue-700',
}

const dotColors: Record<BadgeVariant, string> = {
  default: 'bg-gray-500',
  success: 'bg-green-500',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
  info: 'bg-blue-500',
}

export function Badge({ 
  children, 
  variant = 'default', 
  size = 'sm',
  dot = false 
}: BadgeProps) {
  const sizeClasses = size === 'sm' 
    ? 'text-xs px-2 py-0.5' 
    : 'text-sm px-3 py-1'

  return (
    <span className={`
      inline-flex items-center gap-1.5 rounded-full font-medium
      ${variants[variant]}
      ${sizeClasses}
    `}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]}`} />}
      {children}
    </span>
  )
}

interface StatusBadgeProps {
  status: 'good' | 'low' | 'critical' | 'overstocked'
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = {
    good: { label: 'Good', variant: 'success' as BadgeVariant },
    low: { label: 'Low', variant: 'warning' as BadgeVariant },
    critical: { label: 'Critical', variant: 'error' as BadgeVariant },
    overstocked: { label: 'Overstocked', variant: 'info' as BadgeVariant },
  }

  const { label, variant } = config[status]

  return <Badge variant={variant} dot>{label}</Badge>
}





