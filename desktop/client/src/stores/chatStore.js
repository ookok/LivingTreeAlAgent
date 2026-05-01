import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = 'http://localhost:8766/api'
const WS_BASE = 'ws://localhost:8766/ws/chat'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSession = ref(null)
  const messages = ref([])
  const isLoading = ref(false)
  const searchQuery = ref('')
  const stopSignal = ref(false)
  
  // WebSocket 相关状态
  const websocket = ref(null)
  const isWsConnected = ref(false)
  const currentProtocol = ref('http') // 'websocket' | 'http'

  const filteredSessions = computed(() => {
    if (!searchQuery.value) return sessions.value
    const query = searchQuery.value.toLowerCase()
    return sessions.value.filter(s => s.name.toLowerCase().includes(query))
  })

  async function initConnection() {
    """初始化连接，优先使用 WebSocket，失败则降级到 HTTP"""
    try {
      await connectWebSocket()
      currentProtocol.value = 'websocket'
      console.log('Connected via WebSocket')
    } catch (error) {
      console.warn('WebSocket connection failed, falling back to HTTP:', error)
      currentProtocol.value = 'http'
    }
    await loadSessions()
  }

  function connectWebSocket() {
    """建立 WebSocket 连接"""
    return new Promise((resolve, reject) => {
      if (websocket.value) {
        websocket.value.close()
      }

      const ws = new WebSocket(WS_BASE)
      websocket.value = ws

      ws.onopen = () => {
        isWsConnected.value = true
        resolve()
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      }

      ws.onerror = () => {
        isWsConnected.value = false
        reject(new Error('WebSocket connection error'))
      }

      ws.onclose = () => {
        isWsConnected.value = false
        // 尝试重连
        setTimeout(() => {
          if (currentProtocol.value === 'websocket') {
            connectWebSocket()
          }
        }, 5000)
      }
    })
  }

  function handleWebSocketMessage(data) {
    """处理 WebSocket 消息"""
    switch (data.type) {
      case 'message':
        messages.value.push({
          id: data.id,
          session_id: data.session_id,
          content: data.content,
          role: data.role,
          timestamp: data.timestamp
        })
        break
      case 'sessions':
        sessions.value = data.data
        break
      case 'messages':
        if (data.session_id === currentSession.value?.id) {
          messages.value = data.data
        }
        break
      case 'session_created':
        sessions.value.unshift({
          id: data.id,
          name: data.name,
          timestamp: data.timestamp,
          starred: false
        })
        break
      case 'session_deleted':
        sessions.value = sessions.value.filter(s => s.id !== data.session_id)
        if (currentSession.value?.id === data.session_id) {
          currentSession.value = sessions.value[0] || null
          messages.value = []
        }
        break
      case 'session_updated':
        const index = sessions.value.findIndex(s => s.id === data.session_id)
        if (index !== -1) {
          sessions.value[index] = { ...sessions.value[index], ...data.updates }
        }
        break
      case 'pong':
        break
      case 'error':
        console.error('WebSocket error:', data.message)
        break
    }
  }

  function sendWebSocketMessage(type, payload) {
    """发送 WebSocket 消息"""
    if (isWsConnected.value && websocket.value) {
      websocket.value.send(JSON.stringify({ type, ...payload }))
    }
  }

  async function loadSessions() {
    if (isWsConnected.value) {
      sendWebSocketMessage('get_sessions')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/sessions`)
      if (response.ok) {
        sessions.value = await response.json()
      } else {
        sessions.value = []
      }
      if (sessions.value.length > 0 && !currentSession.value) {
        await selectSession(sessions.value[0])
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
      sessions.value = []
    }
  }

  async function createSession(name = '新会话') {
    if (isWsConnected.value) {
      sendWebSocketMessage('create_session', { name })
      // WebSocket 会异步返回结果，更新 sessions
      return
    }

    try {
      const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      if (response.ok) {
        const session = await response.json()
        sessions.value.unshift(session)
        await selectSession(session)
        return session
      }
    } catch (error) {
      console.error('Failed to create session:', error)
    }
  }

  async function selectSession(session) {
    currentSession.value = session
    messages.value = []
    await loadMessages(session.id)
  }

  async function loadMessages(sessionId) {
    if (isWsConnected.value) {
      sendWebSocketMessage('get_messages', { session_id: sessionId })
      return
    }

    try {
      const response = await fetch(`${API_BASE}/messages/${sessionId}`)
      if (response.ok) {
        messages.value = await response.json()
      } else {
        messages.value = []
      }
    } catch (error) {
      console.error('Failed to load messages:', error)
      messages.value = []
    }
  }

  async function sendMessage(content) {
    if (!content.trim() || !currentSession.value || isLoading.value) return

    const userMessage = {
      id: `msg_${Date.now()}`,
      session_id: currentSession.value.id,
      content,
      role: 'user',
      timestamp: Date.now() / 1000
    }
    messages.value.push(userMessage)

    isLoading.value = true
    stopSignal.value = false

    if (isWsConnected.value) {
      sendWebSocketMessage('message', {
        message: content,
        session_id: currentSession.value.id
      })
      isLoading.value = false
      return
    }

    try {
      const response = await fetch(`${API_BASE}/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: currentSession.value.id
        })
      })

      if (response.ok) {
        const data = await response.json()
        const aiMessage = {
          id: `msg_${Date.now()}`,
          session_id: currentSession.value.id,
          content: data.content,
          role: 'assistant',
          timestamp: Date.now() / 1000
        }
        messages.value.push(aiMessage)
        
        await loadSessions()
      }
    } catch (error) {
      console.error('Failed to send message:', error)
    } finally {
      isLoading.value = false
      stopSignal.value = false
    }
  }

  function stopGeneration() {
    stopSignal.value = true
  }

  async function deleteSession(sessionId) {
    if (isWsConnected.value) {
      sendWebSocketMessage('delete_session', { session_id: sessionId })
      return
    }

    try {
      await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' })
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      
      if (currentSession.value?.id === sessionId) {
        currentSession.value = sessions.value[0] || null
        messages.value = []
        if (currentSession.value) {
          await loadMessages(currentSession.value.id)
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
    }
  }

  async function updateSession(sessionId, data) {
    if (isWsConnected.value) {
      sendWebSocketMessage('update_session', { session_id: sessionId, updates: data })
      return
    }

    try {
      await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      const index = sessions.value.findIndex(s => s.id === sessionId)
      if (index !== -1) {
        sessions.value[index] = { ...sessions.value[index], ...data }
        if (currentSession.value?.id === sessionId) {
          currentSession.value = sessions.value[index]
        }
      }
      await loadSessions()
    } catch (error) {
      console.error('Failed to update session:', error)
    }
  }

  function disconnect() {
    if (websocket.value) {
      websocket.value.close()
      websocket.value = null
      isWsConnected.value = false
    }
  }

  return {
    sessions,
    currentSession,
    messages,
    isLoading,
    searchQuery,
    filteredSessions,
    isWsConnected,
    currentProtocol,
    initConnection,
    loadSessions,
    createSession,
    selectSession,
    loadMessages,
    sendMessage,
    stopGeneration,
    deleteSession,
    updateSession,
    disconnect
  }
})