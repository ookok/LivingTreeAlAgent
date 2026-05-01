import { createApp, ref, computed, onMounted } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'
import ChatView from './views/ChatView.vue'
import DashboardView from './views/DashboardView.vue'
import SettingsView from './views/SettingsView.vue'

const app = createApp({
    components: {
        Sidebar,
        Header,
        ChatView,
        DashboardView,
        SettingsView
    },
    setup() {
        const currentPage = ref('chat')
        const llmConnected = ref(false)
        const providers = ref([])
        const currentProvider = ref('deepseek')
        const currentProviderName = ref('DeepSeek')
        const currentProviderThinkingMode = ref(false)
        const apiKey = ref('')
        const baseUrl = ref('')
        const selectedModel = ref('DeepSeek-V4-Flash')
        const currentProviderModels = ref([])
        const chatMessages = ref([])
        const chatLoading = ref(false)
        const sessions = ref([])
        const currentSessionId = ref(null)
        const showToast = ref(false)
        const toastMessage = ref('')
        
        let backend = null
        
        const showToastMsg = (msg) => {
            toastMessage.value = msg
            showToast.value = true
            setTimeout(() => showToast.value = false, 3000)
        }
        
        const initBackend = () => {
            if (typeof window !== 'undefined' && window.qt && window.qt.webChannelTransport) {
                new QWebChannel(window.qt.webChannelTransport, function(channel) {
                    backend = channel.objects.backend
                    console.log('Backend connected')
                    initData()
                })
            } else {
                console.log('QWebChannel not available')
            }
        }
        
        const initData = async () => {
            if (backend) {
                await loadProviders()
                await loadSessions()
                await loadProviderSettings()
                await checkConnection()
            }
        }
        
        const navigate = (pageId) => {
            currentPage.value = pageId
        }
        
        const loadProviders = async () => {
            if (backend) {
                const resp = await backend.listProviders()
                const data = JSON.parse(resp)
                if (data.status === 'ok') {
                    providers.value = data.providers
                    currentProvider.value = data.current_provider
                    selectedModel.value = data.current_model
                    const provider = providers.value.find(p => p.name === currentProvider.value)
                    if (provider) {
                        currentProviderName.value = provider.display_name
                        currentProviderModels.value = provider.models
                        currentProviderThinkingMode.value = provider.thinking_mode
                        baseUrl.value = provider.base_url
                    }
                }
            }
        }
        
        const selectProvider = async (providerName) => {
            if (backend) {
                const resp = await backend.setCurrentProvider(providerName)
                const data = JSON.parse(resp)
                if (data.status === 'ok') {
                    currentProvider.value = providerName
                    selectedModel.value = data.model
                    const provider = providers.value.find(p => p.name === providerName)
                    if (provider) {
                        currentProviderName.value = provider.display_name
                        currentProviderModels.value = provider.models
                        currentProviderThinkingMode.value = provider.thinking_mode
                        baseUrl.value = provider.base_url
                        apiKey.value = ''
                    }
                    showToastMsg(`已切换到 ${currentProviderName.value}`)
                }
            }
        }
        
        const loadProviderSettings = async () => {
            if (backend) {
                const resp = await backend.listProviders()
                const data = JSON.parse(resp)
                if (data.status === 'ok') {
                    const provider = data.providers.find(p => p.name === data.current_provider)
                    if (provider) {
                        baseUrl.value = provider.base_url
                    }
                }
            }
        }
        
        const saveSettings = async (settings) => {
            if (backend) {
                if (settings.apiKey) {
                    await backend.setProviderApiKey(currentProvider.value, settings.apiKey)
                    apiKey.value = settings.apiKey
                    showToastMsg('API密钥已保存（加密存储）')
                }
                if (settings.baseUrl) {
                    await backend.setProviderBaseUrl(currentProvider.value, settings.baseUrl)
                    baseUrl.value = settings.baseUrl
                    showToastMsg('API地址已保存')
                }
                await loadProviders()
            }
        }
        
        const selectModel = async (modelName) => {
            selectedModel.value = modelName
            if (backend) {
                await backend.setCurrentModel(modelName)
                showToastMsg(`已切换到模型: ${modelName}`)
            }
        }
        
        const loadSessions = async () => {
            if (backend) {
                const resp = await backend.listSessions()
                const data = JSON.parse(resp)
                if (data.status === 'ok') sessions.value = data.sessions
            }
        }
        
        const createSession = async () => {
            if (backend) {
                const title = '新会话 ' + new Date().toLocaleTimeString()
                const resp = await backend.createSession(title)
                const data = JSON.parse(resp)
                if (data.status === 'ok') {
                    currentSessionId.value = data.session_id
                    chatMessages.value = []
                    await loadSessions()
                    showToastMsg('会话已创建')
                }
            }
        }
        
        const loadSession = async (sessionId) => {
            if (backend) {
                currentSessionId.value = sessionId
                const resp = await backend.getSession(sessionId)
                const data = JSON.parse(resp)
                if (data.status === 'ok') {
                    chatMessages.value = data.messages.map(m => ({
                        id: m.timestamp, 
                        role: m.role, 
                        content: m.content
                    }))
                }
            }
        }
        
        const sendMessage = async (message) => {
            if (!message.trim() || chatLoading.value) return
            if (!currentSessionId.value) await createSession()
            chatLoading.value = true
            try {
                if (backend) {
                    const resp = await backend.llmChatSync(currentSessionId.value, message)
                    const data = JSON.parse(resp)
                    if (data.status === 'ok') {
                        await loadSession(currentSessionId.value)
                    } else {
                        showToastMsg(data.error || '发送失败')
                    }
                } else {
                    showToastMsg('后端未连接')
                }
            } catch (e) {
                console.error(e)
                showToastMsg('发送失败')
            } finally {
                chatLoading.value = false
            }
        }
        
        const checkConnection = async () => {
            if (backend) {
                const resp = await backend.llmCheckConnection()
                const data = JSON.parse(resp)
                llmConnected.value = data.result.alive
                showToastMsg(data.result.alive ? '连接成功' : '连接失败')
            }
        }
        
        onMounted(() => {
            console.log('Vue app mounted')
            initBackend()
        })
        
        return {
            currentPage,
            llmConnected,
            providers,
            currentProvider,
            currentProviderName,
            currentProviderThinkingMode,
            apiKey,
            baseUrl,
            selectedModel,
            currentProviderModels,
            chatMessages,
            chatLoading,
            sessions,
            currentSessionId,
            showToast,
            toastMessage,
            navigate,
            selectProvider,
            saveSettings,
            selectModel,
            createSession,
            loadSession,
            sendMessage,
            checkConnection
        }
    }
})

app.mount('#app')
