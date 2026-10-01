import { motion } from 'framer-motion'
import { useNavigate, Link } from 'react-router-dom'
import { Store, MapPin, ChevronRight } from 'lucide-react'
import { BRAND_CONFIG } from '../brand.config'

const personas = [
  {
    id: 'store',
    title: 'Store Manager',
    description: 'Real-time operations, forecasting, labor, inventory, and production prep for your store',
    icon: Store,
    path: '/store/operations',
    color: 'brand-primary',
    features: ['Live Sales Dashboard', 'Demand Forecasting', 'Labor Optimization', 'Inventory Tracking', 'Prep Schedule'],
  },
  {
    id: 'regional',
    title: 'Regional Manager',
    description: 'Multi-store overview, performance comparison, and AI-powered insights',
    icon: MapPin,
    path: '/regional/map',
    color: 'brand-secondary',
    features: ['Store Map View', 'Performance Rankings', 'AI Analytics Chat', 'Regional KPIs'],
  },
]

export default function Login() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-surface-secondary to-green-50 flex items-center justify-center p-8">
      {/* Background Pattern */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/2 -right-1/2 w-full h-full">
          <div className="w-[800px] h-[800px] rounded-full bg-gradient-to-br from-brand-primary/5 to-transparent blur-3xl" />
        </div>
        <div className="absolute -bottom-1/2 -left-1/2 w-full h-full">
          <div className="w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-brand-secondary/5 to-transparent blur-3xl" />
        </div>
      </div>

      <div className="relative z-10 max-w-5xl w-full">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          {/* Brand logo (replaced per-customer by generate.py) */}
          <div className="flex justify-center mb-8">
            <img src={BRAND_CONFIG.logoSrc} alt="StoreSight IQ" className="h-14" />
          </div>
          
          <div className="flex items-center justify-center gap-3 mb-6">
            <img
              src={BRAND_CONFIG.markSrc}
              alt="StoreSight IQ"
              className="w-14 h-14 rounded-2xl object-cover shadow-glow-brand"
            />
            <h1 className="text-4xl font-bold">
              <span className="gradient-text">StoreSight</span>
              <span className="text-text-primary"> IQ</span>
            </h1>
          </div>
          <p className="text-xl text-text-secondary max-w-xl mx-auto">
            {BRAND_CONFIG.customerName} — Real-time store operations intelligence powered by Databricks
          </p>
        </motion.div>

        {/* Persona Cards */}
        <div className="grid md:grid-cols-2 gap-6">
          {personas.map((persona, index) => (
            <motion.button
              key={persona.id}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 + index * 0.1 }}
              onClick={() => navigate(persona.path)}
              className="group relative bg-white rounded-3xl p-8 shadow-soft hover:shadow-strong transition-all duration-300 text-left border border-gray-100 hover:border-transparent overflow-hidden"
            >
              {/* Hover gradient overlay */}
              <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${
                persona.color === 'brand-primary' 
                  ? 'bg-gradient-to-br from-brand-primary/5 to-transparent' 
                  : 'bg-gradient-to-br from-brand-secondary/10 to-transparent'
              }`} />
              
              <div className="relative z-10">
                {/* Icon */}
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-6 ${
                  persona.color === 'brand-primary' 
                    ? 'bg-brand-primary/10 text-brand-primary' 
                    : 'bg-brand-secondary/20 text-brand-secondary-dark'
                }`}>
                  <persona.icon className="w-7 h-7" />
                </div>

                {/* Title & Description */}
                <h2 className="text-2xl font-semibold text-text-primary mb-2 group-hover:text-brand-primary transition-colors">
                  {persona.title}
                </h2>
                <p className="text-text-secondary mb-6">
                  {persona.description}
                </p>

                {/* Features */}
                <ul className="space-y-2 mb-6">
                  {persona.features.map((feature, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-text-secondary">
                      <div className="w-1.5 h-1.5 rounded-full bg-brand-primary" />
                      {feature}
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <div className="flex items-center gap-2 text-brand-primary font-medium group-hover:gap-3 transition-all">
                  <span>Continue as {persona.title}</span>
                  <ChevronRight className="w-5 h-5" />
                </div>
              </div>
            </motion.button>
          ))}
        </div>

        {/* Footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-center mt-12 text-sm text-text-tertiary"
        >
          <p>Powered by Databricks • Unity Catalog • Mosaic AI • AI/BI Genie • Lakebase</p>
          <Link to="/architecture" className="inline-block mt-3 text-brand-primary hover:underline font-medium">
            View live architecture →
          </Link>
        </motion.div>
      </div>
    </div>
  )
}


