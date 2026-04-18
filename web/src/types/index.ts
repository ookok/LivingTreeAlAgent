export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: number
}

export interface ChatResponse {
  success: boolean
  message: string
  session_id: string
  timestamp: number
}

export interface MemoryItem {
  id: string
  content: string
  type: 'permanent' | 'session' | 'working'
  score?: number
  metadata?: Record<string, any>
  created_at?: number
}

export interface Skill {
  id: string
  name: string
  description: string
  icon?: string
  category?: string
  parameters?: Record<string, any>
}

export interface SystemStatus {
  online: boolean
  connected_nodes: number
  active_routes: number
  cpu_usage: number
  memory_usage: number
  network_quality: 'excellent' | 'good' | 'poor'
  last_update: number
}
