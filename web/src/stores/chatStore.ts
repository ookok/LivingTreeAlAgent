import { create } from 'zustand'

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: number
}

interface ChatState {
  messages: Message[]
  sessionId: string | null
  addMessage: (message: Message) => void
  clearMessages: () => void
  setSessionId: (id: string) => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  sessionId: null,

  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          timestamp: Date.now(),
        },
      ],
    })),

  clearMessages: () =>
    set({
      messages: [],
      sessionId: null,
    }),

  setSessionId: (id) =>
    set({
      sessionId: id,
    }),
}))
