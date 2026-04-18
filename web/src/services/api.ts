import axios, { AxiosInstance, AxiosResponse } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

class ApiResponse<T = any> {
  success: boolean
  data: T
  error: string
  statusCode: number

  constructor(response: AxiosResponse) {
    this.success = response.status >= 200 && response.status < 300
    this.data = response.data?.data || response.data
    this.error = response.data?.error || ''
    this.statusCode = response.status
  }
}

class HermesApiService {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error)
        return Promise.reject(error)
      }
    )
  }

  private async request<T>(method: string, path: string, data?: any): Promise<ApiResponse<T>> {
    try {
      const response = await this.client.request<T>({
        method,
        url: path,
        data,
      })
      return new ApiResponse<T>(response)
    } catch (error: any) {
      const errorResponse = new ApiResponse(error.response || {})
      errorResponse.error = error.message
      return errorResponse
    }
  }

  // ==================== Chat ====================

  async chat(message: string, sessionId?: string): Promise<ApiResponse> {
    return this.request('POST', '/chat/completions', {
      message,
      session_id: sessionId || '',
    })
  }

  async getChatHistory(sessionId: string, limit: number = 50): Promise<ApiResponse> {
    return this.request('GET', `/chat/history/${sessionId}?limit=${limit}`)
  }

  // ==================== Memory ====================

  async searchMemory(query: string, limit: number = 10): Promise<ApiResponse> {
    return this.request('GET', `/memory/search?query=${encodeURIComponent(query)}&limit=${limit}`)
  }

  async storeMemory(
    content: string,
    memoryType: 'permanent' | 'session' | 'working' = 'permanent'
  ): Promise<ApiResponse> {
    return this.request('POST', '/memory/store', {
      content,
      memory_type: memoryType,
    })
  }

  async deleteMemory(memoryId: string): Promise<ApiResponse> {
    return this.request('DELETE', `/memory/${memoryId}`)
  }

  // ==================== Skills ====================

  async listSkills(category?: string): Promise<ApiResponse> {
    const url = category ? `/skills/list?category=${category}` : '/skills/list'
    return this.request('GET', url)
  }

  async getSkill(skillId: string): Promise<ApiResponse> {
    return this.request('GET', `/skills/${skillId}`)
  }

  async executeSkill(skillId: string, params: Record<string, any> = {}): Promise<ApiResponse> {
    return this.request('POST', '/skills/execute', {
      skill_id: skillId,
      params,
    })
  }

  // ==================== RAG ====================

  async queryRAG(query: string, topK: number = 5): Promise<ApiResponse> {
    return this.request('POST', '/rag/query', {
      query,
      top_k: topK,
    })
  }

  async indexDocument(document: Record<string, any>): Promise<ApiResponse> {
    return this.request('POST', '/rag/index', document)
  }

  // ==================== vLLM ====================

  async generate(
    prompt: string,
    model?: string,
    temperature: number = 0.6,
    maxTokens: number = 256
  ): Promise<ApiResponse> {
    return this.request('POST', '/vllm/generate', {
      prompt,
      model,
      temperature,
      max_tokens: maxTokens,
    })
  }

  async listModels(): Promise<ApiResponse> {
    return this.request('GET', '/vllm/models')
  }

  // ==================== System ====================

  async getStatus(): Promise<ApiResponse> {
    return this.request('GET', '/status')
  }

  async getHealth(): Promise<ApiResponse> {
    return this.request('GET', '/health')
  }

  // ==================== WebSocket ====================

  createWebSocket(path: string = '/ws/v1/chat'): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${path}`
    return new WebSocket(wsUrl)
  }
}

export const hermesApi = new HermesApiService()
