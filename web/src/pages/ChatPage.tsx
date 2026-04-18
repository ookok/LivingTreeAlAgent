import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, MessageCircle } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { hermesApi } from '@/services/api'
import toast from 'react-hot-toast'

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { messages, addMessage, clearMessages } = useChatStore()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    addMessage({ role: 'user', content: userMessage })
    setLoading(true)

    try {
      const response = await hermesApi.chat(userMessage)
      if (response.success && response.data) {
        addMessage({ role: 'assistant', content: response.data.message || response.data })
      } else {
        addMessage({ role: 'assistant', content: '抱歉，发生了错误。' })
        toast.error(response.error || '发送失败')
      }
    } catch (error) {
      addMessage({ role: 'assistant', content: '网络错误，请稍后重试。' })
      toast.error('网络错误')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="h-14 px-4 flex items-center border-b border-border bg-surface">
        <h1 className="text-lg font-semibold">聊天</h1>
        <div className="ml-auto">
          <button
            onClick={clearMessages}
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            清空会话
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-text-secondary">
            <div className="text-center">
              <MessageCircle size={48} className="mx-auto mb-4 opacity-50" />
              <p>开始一段新的对话</p>
            </div>
          </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] md:max-w-[60%] rounded-2xl px-4 py-2 ${
                msg.role === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-surface-light text-text-primary'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface-light rounded-2xl px-4 py-3 flex items-center space-x-2">
              <Loader2 size={16} className="animate-spin text-primary" />
              <span className="text-text-secondary text-sm">思考中...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border bg-surface">
        <div className="flex items-end space-x-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息..."
            rows={1}
            className="flex-1 bg-surface-light rounded-xl px-4 py-3 text-sm resize-none focus:ring-2 focus:ring-primary/50"
            style={{ maxHeight: '120px' }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="p-3 bg-primary rounded-xl hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  )
}
