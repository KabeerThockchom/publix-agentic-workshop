/**
 * API client for StoreSight IQ backend
 */

const API_BASE = '/api'

class ApiClient {
  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    // Always send client's local time info via headers (more reliable than query params)
    const now = new Date()
    const localHour = now.getHours()
    const timezoneOffset = now.getTimezoneOffset() // minutes from UTC
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        'X-Client-Local-Hour': localHour.toString(),
        'X-Client-Timezone-Offset': timezoneOffset.toString(),
        ...options?.headers,
      },
      ...options,
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`)
    }

    return response.json()
  }

  // Stores
  async getStores() {
    return this.fetch<{ stores: any[]; total: number }>('/stores/')
  }

  async getStoreLocations() {
    return this.fetch<any[]>('/stores/locations')
  }

  async getStoreDetail(storeId: number) {
    return this.fetch<any>(`/stores/${storeId}`)
  }

  // Operations
  // Note: Local hour is automatically sent via X-Client-Local-Hour header in fetch()
  async getOperationsSummary(storeId: number) {
    return this.fetch<any>(`/operations/summary/${storeId}`)
  }

  async getHourlySales(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any[]>(`/operations/hourly/${storeId}${query}`)
  }

  async getTransactions(storeId: number, limit = 10, initial = false, startIndex = 0) {
    return this.fetch<any[]>(`/operations/transactions/${storeId}?limit=${limit}&initial=${initial}&start_index=${startIndex}`)
  }

  async getAlerts(storeId: number) {
    return this.fetch<any[]>(`/operations/alerts/${storeId}`)
  }

  async getCurrentWeather(storeId: number) {
    return this.fetch<any>(`/operations/weather/${storeId}`)
  }

  async getLocalEvents(storeId: number) {
    return this.fetch<any>(`/operations/events/${storeId}`)
  }

  // Forecast
  async getWeeklyForecast(storeId: number) {
    return this.fetch<any>(`/forecast/weekly/${storeId}`)
  }

  async getHourlyForecast(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any[]>(`/forecast/hourly/${storeId}${query}`)
  }

  async getDaypartForecast(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any>(`/forecast/daypart/${storeId}${query}`)
  }

  async getPrepRecommendations(storeId: number, daypart = 'lunch') {
    return this.fetch<any[]>(`/forecast/prep/${storeId}?daypart=${daypart}`)
  }

  // Labor
  async getLaborSummary(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any>(`/labor/summary/${storeId}${query}`)
  }

  async getSchedule(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any[]>(`/labor/schedule/${storeId}${query}`)
  }

  async getHourlyLabor(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any[]>(`/labor/hourly/${storeId}${query}`)
  }

  async getStaffingRecommendations(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any[]>(`/labor/recommendations/${storeId}${query}`)
  }

  // Inventory
  async getInventorySummary(storeId: number) {
    return this.fetch<any>(`/inventory/summary/${storeId}`)
  }

  async getInventoryLevels(storeId: number, category?: string) {
    const query = category ? `?category=${category}` : ''
    return this.fetch<any[]>(`/inventory/levels/${storeId}${query}`)
  }

  async getDeliveries(storeId: number) {
    return this.fetch<any[]>(`/inventory/deliveries/${storeId}`)
  }

  async getOrderSuggestions(storeId: number) {
    return this.fetch<any[]>(`/inventory/suggestions/${storeId}`)
  }

  async getWasteTracking(storeId: number, days = 7) {
    return this.fetch<any>(`/inventory/waste/${storeId}?days=${days}`)
  }

  // Prep Scheduler (production prep)
  async getDoughInventory(storeId: number) {
    return this.fetch<any[]>(`/prep/inventory/${storeId}`)
  }

  async getPrepSchedule(storeId: number, date?: string) {
    const query = date ? `?date=${date}` : ''
    return this.fetch<any>(`/prep/schedule/${storeId}${query}`)
  }

  async getPrepBatchRecommendations(storeId: number) {
    return this.fetch<any[]>(`/prep/recommendations/${storeId}`)
  }

  async getPrepAlerts(storeId: number) {
    return this.fetch<any[]>(`/prep/alerts/${storeId}`)
  }

  // Genie (AI Chat)
  async queryGenie(question: string, conversationId?: string) {
    return this.fetch<any>('/genie/query', {
      method: 'POST',
      body: JSON.stringify({ question, conversation_id: conversationId }),
    })
  }

  async getGenieSuggestions() {
    return this.fetch<any[]>('/genie/suggestions')
  }

  async getGenieStatus() {
    return this.fetch<any>('/genie/status')
  }

  // State Persistence
  async getInventoryOrders(storeId: number) {
    return this.fetch<any[]>(`/state/inventory-orders/${storeId}`)
  }

  async submitInventoryOrders(storeId: number, items: {
    ingredient_id: number
    ingredient_name: string
    suggested_quantity?: number
    estimated_cost?: number
    urgency?: string
  }[]) {
    return this.fetch<any>(`/state/inventory-orders/${storeId}`, {
      method: 'POST',
      body: JSON.stringify(items),
    })
  }

  async clearInventoryOrders(storeId: number) {
    return this.fetch<any>(`/state/inventory-orders/${storeId}`, {
      method: 'DELETE',
    })
  }

  async getPrepState(storeId: number) {
    return this.fetch<any[]>(`/state/prep-items/${storeId}`)
  }

  async submitPrepItems(storeId: number, items: {
    crust_type: string
    recommended_quantity?: number
    suggested_prep_time?: string
    confidence?: number
  }[]) {
    return this.fetch<any>(`/state/prep-items/${storeId}`, {
      method: 'POST',
      body: JSON.stringify(items),
    })
  }

  async clearPrepState(storeId: number) {
    return this.fetch<any>(`/state/prep-items/${storeId}`, {
      method: 'DELETE',
    })
  }

  // Health
  async getHealth() {
    return this.fetch<any>('/health')
  }
}

export const api = new ApiClient()


