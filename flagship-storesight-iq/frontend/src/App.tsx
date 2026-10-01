import { Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Login from './pages/Login'
import StoreLayout from './layouts/StoreLayout'
import RegionalLayout from './layouts/RegionalLayout'
import StoreOperations from './pages/store/Operations'
import StoreForecast from './pages/store/Forecast'
import StoreLabor from './pages/store/Labor'
import StoreInventory from './pages/store/Inventory'
import StorePrep from './pages/store/PrepScheduler'
import RegionalMap from './pages/regional/MapView'
import RegionalCompare from './pages/regional/Compare'
import Architecture from './pages/Architecture'
import { BRAND_CONFIG } from './brand.config'

function App() {
  return (
    <AnimatePresence mode="wait">
      <Routes>
        {/* Login / Persona Selection */}
        <Route path="/" element={<Login />} />

        {/* Live architecture diagram */}
        <Route path="/architecture" element={<Architecture />} />
        
        {/* Store Manager Views */}
        <Route path="/store" element={<StoreLayout />}>
          <Route index element={<Navigate to="operations" replace />} />
          <Route path="operations" element={<StoreOperations />} />
          <Route path="forecast" element={<StoreForecast />} />
          <Route path="labor" element={<StoreLabor />} />
          <Route path="inventory" element={<StoreInventory />} />
          {/* Configurable 5th surface — only mounted when enabled in brand.config. */}
          {BRAND_CONFIG.prepSchedulerEnabled && <Route path="prep" element={<StorePrep />} />}
        </Route>
        
        {/* Regional Manager Views */}
        <Route path="/regional" element={<RegionalLayout />}>
          <Route index element={<Navigate to="map" replace />} />
          <Route path="map" element={<RegionalMap />} />
          <Route path="compare" element={<RegionalCompare />} />
        </Route>
        
        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  )
}

export default App





