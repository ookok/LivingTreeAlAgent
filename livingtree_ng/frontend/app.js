const { createApp, ref, reactive, computed, onMounted } = Vue
const { createRouter, createWebHashHistory } = VueRouter
const { createPinia, defineStore } = Pinia

// =========================================================================
// 状态管理
// =========================================================================
const useBackendStore = defineStore('backend', {
    state: () => ({
        connected: false,
        backend: null,
        status: {
            overall: 'healthy',
            metrics: {},
            repair_count: 0,
            last_repair: null
        },
        memories: [],
        allMemories: [],
        tasks: [],
        notifications: [],
        sessions: [],
        currentSessionId: null,
        currentSession: null,
        chatMessages: [],
        config: null,
        llmModels: [],
        llmConnected: false,
        currentModel: 'llama3',
        knowledgeItems: [],
        loading: false
    }),
    
    actions: {
        async init() {
            try {
                const channel = await new Promise((resolve) => {
                    new QWebChannel(qt.webChannelTransport, function (channel) {
                        resolve(channel)
                    })
                })
                
                this.backend = channel.objects.backend
                this.connected = true
                
                this.backend.eventReceived.connect(this.handleEvent)
                
                await this.refreshStatus()
                await this.refreshSessions()
                await this.refreshConfig()
                await this.refreshLLMModels()
                await this.checkLLMConnection()
                await this.refreshAllMemories()
                
                console.log('✅ 后端连接成功')
            } catch (e) {
                console.error('后端连接失败:', e)
            }
        },
        
        handleEvent(eventJson) {
            const event = JSON.parse(eventJson)
            console.log('收到事件:', event)
            
            this.notifications.unshift({
                id: Date.now(),
                type: event.type,
                data: event.data,
                time: new Date().toLocaleTimeString()
            })
            
            if (this.notifications.length > 20) {
                this.notifications.pop()
            }
            
            if (event.type === 'system.status') {
                this.status = event.data
            }
        },
        
        async refreshStatus() {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.getSystemStatus())
            if (result.status === 'ok') {
                this.status = result.system
            }
        },
        
        async refreshSessions() {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.listSessions())
            if (result.status === 'ok') {
                this.sessions = result.sessions
            }
        },
        
        async refreshConfig() {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.getConfig())
            if (result.status === 'ok') {
                this.config = result.config
            }
        },
        
        async refreshLLMModels() {
            if (!this.backend) return []
            
            const result = JSON.parse(await this.backend.llmListModels())
            if (result.status === 'ok') {
                this.llmModels = result.models
            }
        },
        
        async checkLLMConnection() {
            if (!this.backend) return false
            
            const result = JSON.parse(await this.backend.llmCheckConnection())
            if (result.status === 'ok') {
                this.llmConnected = result.result.alive
            }
            return this.llmConnected
        },
        
        async refreshAllMemories() {
            if (!this.backend) return []
            
            const result = JSON.parse(await this.backend.getAllMemories())
            if (result.status === 'ok') {
                this.allMemories = result.memories
            }
        },
        
        async ping(message) {
            if (!this.backend) return '未连接'
            
            const result = JSON.parse(await this.backend.ping(message))
            return result
        },
        
        async storeMemory(content, metadata = {}) {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.storeMemory(JSON.stringify({
                content, metadata
            })))
            return result
        },
        
        async retrieveMemory(query, limit = 10) {
            if (!this.backend) return []
            
            const result = JSON.parse(await this.backend.retrieveMemory(JSON.stringify({
                query, limit
            })))
            if (result.status === 'ok') {
                this.memories = result.results
            }
            return result
        },
        
        async reasoning(query, type = 'causal') {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.reasoning(JSON.stringify({
                query, type
            })))
            return result
        },
        
        async requestHealing(component, issue) {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.requestHealing(JSON.stringify({
                component, issue
            })))
            return result
        },
        
        async sendChatMessage(content) {
            if (!this.backend) return
            
            const result = JSON.parse(await this.backend.sendChatMessage(JSON.stringify({
                content
            })))
            return result
        },
        
        async createSession(name) {
            if (!this.backend) return null
            
            const result = JSON.parse(await this.backend.createSession(name))
            if (result.status === 'ok') {
                await this.refreshSessions()
                return result.session_id
            }
            return null
        },
        
        async loadSession(sessionId) {
            if (!this.backend) return null
            
            this.currentSessionId = sessionId
            const result = JSON.parse(await this.backend.getSession(sessionId))
            if (result.status === 'ok') {
                this.currentSession = result.session
                this.chatMessages = result.messages || []
            }
            return result
        },
        
        async sendChatMessageFull(sessionId, role, content) {
            if (!this.backend) return null
            
            const result = JSON.parse(await this.backend.sendChatMessageFull(sessionId, role, content))
            return result
        },
        
        // 记忆管理
        async encodeMemory(content, memoryType = 'episodic') {
            if (!this.backend) return null
            
            const result = JSON.parse(await this.backend.encodeMemory(content, memoryType))
            if (result.status === 'ok') {
                await this.refreshAllMemories()
            }
            return result
        },
        
        async deleteMemory(memoryId) {
            if (!this.backend) return null
            
            const result = JSON.parse(await this.backend.deleteMemory(memoryId))
            if (result.status === 'ok') {
                await this.refreshAllMemories()
            }
            return result
        },
        
        async searchMemories(query) {
            if (!this.backend) return []
            
            const result = JSON.parse(await this.backend.searchMemories(query))
            if (result.status === 'ok') {
                return result.results
            }
            return []
        },
        
        // 知识库管理
        async addKnowledgeItem(knowledgeType, content) {
            if (!this.backend) return null
            
            const result = JSON.parse(await this.backend.addKnowledge(knowledgeType, content))
            return result
        },
        
        async searchKnowledgeItems(query, knowledgeType = '') {
            if (!this.backend) return []
            
            const result = JSON.parse(await this.backend.searchKnowledge(query, knowledgeType, 10))
            if (result.status === 'ok') {
                this.knowledgeItems = result.results
            }
            return result
        },
        
        // 设置管理
        async updateConfig(key, value) {
            if (!this.backend) return null
            
            const result = JSON.parse(await this.backend.setConfig(key, String(value)))
            if (result.status === 'ok') {
                await this.refreshConfig()
            }
            return result
        },
        
        showToast(message) {
            const toast = document.createElement('div')
            toast.className = 'toast'
            toast.textContent = message
            document.body.appendChild(toast)
            setTimeout(() => {
                if (document.body.contains(toast)) {
                    document.body.removeChild(toast)
                }
            }, 3000)
        }
    }
})

// =========================================================================
// 页面组件
// =========================================================================

const Dashboard = {
    template: `
        <div class="dashboard">
            <h1><i class="mdi mdi-robot-happy"></i> LivingTreeAlAgent NG</h1>
            
            <div class="grid">
                <div class="card">
                    <h3><i class="mdi mdi-pulse"></i> 系统状态</h3>
                    <div :class="'status-' + status.overall">{{ status.overall }}</div>
                    
                    <div style="margin-top: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span>Ollama</span>
                            <span :class="llmConnected ? 'status-good' : 'status-error'">
                                {{ llmConnected ? '已连接' : '未连接' }}
                            </span>
                        </div>
                        <div class="btn btn-secondary" @click="checkLLM" style="margin-top: 8px;">
                            检查连接
                        </div>
                    </div>
                    
                    <div class="metrics" style="margin-top: 12px;">
                        <div v-for="(val, key) in status.metrics" :key="key">
                            <span>{{ key }}: {{ val.value }}/{{ val.threshold }}</span>
                            <span :class="'status-' + val.status">{{ val.status }}</span>
                        </div>
                    </div>
                    
                    <div class="btn btn-secondary" @click="refreshStatus">刷新状态</div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-forum"></i> 会话列表</h3>
                    <div class="btn btn-primary" @click="createNewSession">
                        <i class="mdi mdi-plus"></i> 新建会话
                    </div>
                    <div style="margin-top: 12px; max-height: 250px; overflow-y: auto;">
                        <div 
                            v-for="session in sessions" 
                            :key="session.id"
                            style="padding: 8px; background: rgba(255, 255, 255, 0.05); border-radius: 4px; margin-bottom: 8px; cursor: pointer;"
                            :style="{'background': currentSessionId === session.id ? 'rgba(102,126,234,0.2)' : 'rgba(255,255,255,0.05)'}"
                            @click="selectSession(session)">
                            <div style="font-weight: bold;">{{ session.name }}</div>
                            <div style="font-size: 12px; color: #888;">{{ formatTime(session.updated_at) }}</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-chat"></i> 聊天</h3>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="font-size: 14px; color: #888;">模型</label>
                        <select v-model="currentModel" class="input" style="margin-top: 4px;">
                            <option value="llama3">llama3</option>
                            <option v-for="model in modelList" :key="model.name" :value="model.name">
                                {{ model.name }}
                            </option>
                        </select>
                    </div>
                    
                    <div class="chat-messages" ref="chatContainer" style="min-height: 200px;">
                        <div v-if="!currentSession" style="color: #888; text-align: center; padding: 40px;">
                            请选择或创建一个会话
                        </div>
                        
                        <div v-for="(msg, i) in chatMessages" :key="i" style="margin-bottom: 12px;" class="chat-message">
                            <div style="font-weight: bold; margin-bottom: 4px;">{{ msg.role }}</div>
                            <div style="background: rgba(255,255,255,0.05); padding: 8px 12px; border-radius: 4px;">
                                {{ msg.content }}
                            </div>
                        </div>
                        
                        <div v-if="loading" style="text-align: center; padding: 12px;">
                            <div class="loading" style="display: inline-block;"></div>
                        </div>
                    </div>
                    
                    <div class="chat-input" style="margin-top: 12px;">
                        <input 
                            v-model="chatInput" 
                            @keyup.enter="sendChat" 
                            class="input" 
                            placeholder="输入消息..."
                            :disabled="!currentSession || loading">
                        <button class="btn btn-primary" @click="sendChat" :disabled="!currentSession || loading">
                            <i class="mdi mdi-send"></i>
                        </button>
                    </div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-lightbulb"></i> 推理</h3>
                    <input v-model="reasoningQuery" class="input" placeholder="输入推理查询...">
                    <div class="btn-group">
                        <button class="btn btn-secondary" v-for="type in reasoningTypes" :key="type" @click="doReasoning(type)">
                            {{ type }}
                        </button>
                    </div>
                    <div v-if="reasoningResult" class="reasoning-result">
                        <h4>结果</h4>
                        <pre>{{ JSON.stringify(reasoningResult, null, 2) }}</pre>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        
        const status = computed(() => store.status)
        const sessions = computed(() => store.sessions)
        const currentSessionId = computed(() => store.currentSessionId)
        const currentSession = computed(() => store.currentSession)
        const chatMessages = computed(() => store.chatMessages)
        const llmConnected = computed(() => store.llmConnected)
        const modelList = computed(() => store.llmModels)
        
        const newMemory = ref('')
        const chatInput = ref('')
        const reasoningQuery = ref('')
        const reasoningResult = ref(null)
        const currentModel = ref('llama3')
        const loading = ref(false)
        const reasoningTypes = ['causal', 'symbolic', 'analogical', 'counterfactual']
        
        const refreshStatus = () => store.refreshStatus()
        const checkLLM = async () => {
            await store.checkLLMConnection()
            await store.refreshLLMModels()
        }
        
        const createNewSession = async () => {
            const name = prompt('输入会话名称:', '新会话')
            if (name) {
                const sessionId = await store.createSession(name)
                if (sessionId) {
                    await selectSessionById(sessionId)
                }
            }
        }
        
        const selectSession = async (session) => {
            await selectSessionById(session.id)
        }
        
        const selectSessionById = async (sessionId) => {
            await store.loadSession(sessionId)
        }
        
        const sendChat = async () => {
            if (!chatInput.value || !currentSession.value || loading.value) return
            
            const content = chatInput.value
            chatInput.value = ''
            
            chatMessages.value.push({ role: 'user', content })
            loading.value = true
            
            try {
                const result = JSON.parse(await store.backend.llmChat(content, currentSessionId.value, currentModel.value))
                
                if (result && result.response) {
                    chatMessages.value.push({ role: 'assistant', content: result.response })
                    
                    await store.sendChatMessageFull(currentSessionId.value, 'user', content)
                    await store.sendChatMessageFull(currentSessionId.value, 'assistant', result.response)
                } else {
                    chatMessages.value.push({ 
                        role: 'assistant', 
                        content: result.error || '抱歉，发生了错误。' 
                    })
                }
            } catch (e) {
                console.error(e)
                chatMessages.value.push({ role: 'assistant', content: '抱歉，发生了错误。' })
            } finally {
                loading.value = false
            }
        }
        
        const doReasoning = async (type) => {
            if (reasoningQuery.value) {
                reasoningResult.value = await store.reasoning(reasoningQuery.value, type)
            }
        }
        
        const formatTime = (timestamp) => {
            if (!timestamp) return ''
            return new Date(timestamp * 1000).toLocaleString()
        }
        
        return {
            status, sessions, currentSessionId, currentSession, chatMessages,
            llmConnected, modelList, chatInput, reasoningQuery, reasoningResult, currentModel,
            reasoningTypes, refreshStatus, checkLLM, createNewSession, selectSession,
            sendChat, doReasoning, formatTime, loading
        }
    }
}

const MemoryPage = {
    template: `
        <div class="memory">
            <h1><i class="mdi mdi-brain"></i> 大脑启发记忆系统</h1>
            
            <div class="grid">
                <div class="card">
                    <h3><i class="mdi mdi-plus"></i> 编码记忆</h3>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="font-size: 14px; color: #888;">记忆类型</label>
                        <select v-model="memoryType" class="input" style="margin-top: 4px;">
                            <option value="episodic">情景记忆</option>
                            <option value="semantic">语义记忆</option>
                            <option value="procedural">程序记忆</option>
                            <option value="emotional">情绪记忆</option>
                        </select>
                    </div>
                    
                    <textarea v-model="memoryContent" class="input" placeholder="记忆内容..." rows="5"></textarea>
                    <button class="btn btn-primary" @click="encodeMemory">编码</button>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-book-open"></i> 记忆列表</h3>
                    
                    <div style="margin-bottom: 12px;">
                        <input v-model="memorySearch" class="input" placeholder="搜索记忆...">
                        <button class="btn btn-secondary" @click="searchMemories" style="margin-top: 8px;">
                            搜索
                        </button>
                    </div>
                    
                    <div style="max-height: 400px; overflow-y: auto;">
                        <div v-for="mem in displayedMemories" :key="mem.memory_id" 
                             style="padding: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; margin-bottom: 8px;"
                             class="fade-in">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div style="flex: 1;">
                                    <div style="font-weight: bold;">{{ mem.type }}</div>
                                    <div style="font-size: 13px; color: #aaa;">{{ mem.content }}</div>
                                    <div style="font-size: 12px; color: #777; margin-top: 4px;">
                                        {{ mem.created_at }} | 权重: {{ mem.weight }}
                                    </div>
                                </div>
                                <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 12px;" @click="deleteMemory(mem.memory_id)">
                                    <i class="mdi mdi-delete"></i>
                                </button>
                            </div>
                        </div>
                        
                        <div v-if="displayedMemories.length === 0" style="color: #888; text-align: center; padding: 20px;">
                            暂无记忆
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-information"></i> 说明</h3>
                    <ul style="margin-left: 20px;">
                        <li>海马体 - 快速记忆编码</li>
                        <li>新皮层 - 语义记忆存储</li>
                        <li>记忆巩固 - 类似睡眠过程</li>
                        <li>Hebbian学习 - 使用增强记忆权重</li>
                    </ul>
                    
                    <h4 style="margin-top: 16px;">记忆类型</h4>
                    <ul style="margin-left: 20px;">
                        <li><strong>情景记忆</strong> - 事件和经历</li>
                        <li><strong>语义记忆</strong> - 概念和知识</li>
                        <li><strong>程序记忆</strong> - 技能和过程</li>
                        <li><strong>情绪记忆</strong> - 情感相关</li>
                    </ul>
                </div>
            </div>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        
        const allMemories = computed(() => store.allMemories)
        const memoryType = ref('episodic')
        const memoryContent = ref('')
        const memorySearch = ref('')
        const searchResults = ref([])
        const isSearching = ref(false)
        
        const displayedMemories = computed(() => {
            if (isSearching.value) {
                return searchResults.value
            }
            return allMemories.value
        })
        
        const encodeMemory = async () => {
            if (memoryContent.value) {
                await store.encodeMemory(memoryContent.value, memoryType.value)
                store.showToast('记忆编码成功！')
                memoryContent.value = ''
            }
        }
        
        const deleteMemory = async (memoryId) => {
            if (confirm('确定删除此记忆吗?')) {
                await store.deleteMemory(memoryId)
                store.showToast('记忆删除成功！')
            }
        }
        
        const searchMemories = async () => {
            if (memorySearch.value) {
                isSearching.value = true
                searchResults.value = await store.searchMemories(memorySearch.value)
            } else {
                isSearching.value = false
                searchResults.value = []
            }
        }
        
        return {
            allMemories, memoryType, memoryContent, memorySearch, displayedMemories,
            encodeMemory, deleteMemory, searchMemories
        }
    }
}

const KnowledgePage = {
    template: `
        <div class="knowledge">
            <h1><i class="mdi mdi-bookshelf"></i> 知识库管理</h1>
            
            <div class="grid">
                <div class="card">
                    <h3><i class="mdi mdi-plus"></i> 添加知识</h3>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="font-size: 14px; color: #888;">知识类型</label>
                        <select v-model="knowledgeType" class="input" style="margin-top: 4px;">
                            <option value="text">文本</option>
                            <option value="fact">事实</option>
                            <option value="rule">规则</option>
                            <option value="concept">概念</option>
                            <option value="procedure">流程</option>
                        </select>
                    </div>
                    
                    <textarea v-model="knowledgeContent" class="input" placeholder="知识内容..." rows="5"></textarea>
                    <button class="btn btn-primary" @click="addKnowledge">添加</button>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-magnify"></i> 搜索知识</h3>
                    
                    <div style="margin-bottom: 12px;">
                        <input v-model="knowledgeSearch" class="input" placeholder="搜索知识库...">
                        
                        <div style="display: flex; gap: 8px; margin-top: 8px;">
                            <select v-model="searchKnowledgeType" class="input" style="flex: 1;">
                                <option value="">所有类型</option>
                                <option value="text">文本</option>
                                <option value="fact">事实</option>
                                <option value="rule">规则</option>
                                <option value="concept">概念</option>
                                <option value="procedure">流程</option>
                            </select>
                            
                            <button class="btn btn-secondary" @click="searchKnowledge">
                                搜索
                            </button>
                        </div>
                    </div>
                    
                    <div style="max-height: 400px; overflow-y: auto;">
                        <div v-for="item in knowledgeItems" :key="item.id" 
                             style="padding: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; margin-bottom: 8px;"
                             class="fade-in">
                            <div style="font-weight: bold;">{{ item.type }}</div>
                            <div style="font-size: 13px; color: #aaa;">{{ item.content }}</div>
                            <div style="font-size: 12px; color: #777; margin-top: 4px;">
                                {{ item.created_at }}
                            </div>
                        </div>
                        
                        <div v-if="knowledgeItems.length === 0" style="color: #888; text-align: center; padding: 20px;">
                            暂无知识条目
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-information"></i> 说明</h3>
                    <ul style="margin-left: 20px;">
                        <li><strong>文本</strong> - 一般文本内容</li>
                        <li><strong>事实</strong> - 真实事实</li>
                        <li><strong>规则</strong> - 规则和约束</li>
                        <li><strong>概念</strong> - 概念和定义</li>
                        <li><strong>流程</strong> - 操作流程</li>
                    </ul>
                    
                    <h4 style="margin-top: 16px;">使用</h4>
                    <p style="color: #aaa; margin-top: 8px;">
                        知识库可以为对话提供背景知识，增强AI的回答准确性。
                    </p>
                </div>
            </div>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        
        const knowledgeType = ref('text')
        const knowledgeContent = ref('')
        const knowledgeSearch = ref('')
        const searchKnowledgeType = ref('')
        const knowledgeItems = computed(() => store.knowledgeItems)
        
        const addKnowledge = async () => {
            if (knowledgeContent.value) {
                await store.addKnowledgeItem(knowledgeType.value, knowledgeContent.value)
                store.showToast('知识添加成功！')
                knowledgeContent.value = ''
            }
        }
        
        const searchKnowledge = async () => {
            if (knowledgeSearch.value) {
                await store.searchKnowledgeItems(knowledgeSearch.value, searchKnowledgeType.value)
            }
        }
        
        return {
            knowledgeType, knowledgeContent, knowledgeSearch,
            searchKnowledgeType, knowledgeItems,
            addKnowledge, searchKnowledge
        }
    }
}

const HealingPage = {
    template: `
        <div class="healing">
            <h1><i class="mdi mdi-heart-pulse"></i> 自修复系统</h1>
            
            <div class="grid">
                <div class="card">
                    <h3><i class="mdi mdi-wrench"></i> 触发修复</h3>
                    <input v-model="healComponent" class="input" placeholder="组件名称">
                    <input v-model="healIssue" class="input" placeholder="问题描述">
                    <button class="btn btn-primary" @click="triggerHealing">请求修复</button>
                    <div v-if="healResult" style="margin-top: 12px;">
                        <pre>{{ JSON.stringify(healResult, null, 2) }}</pre>
                    </div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-history"></i> 修复历史</h3>
                    <pre v-if="status.last_repair">{{ JSON.stringify(status.last_repair, null, 2) }}</pre>
                    <div v-else>暂无修复历史</div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-information"></i> 说明</h3>
                    <ul style="margin-left: 20px;">
                        <li>健康监控 - 实时监控系统状态</li>
                        <li>预测检测 - 预判潜在问题</li>
                        <li>修复策略 - 多种修复方案</li>
                        <li>数字孪生 - 验证修复结果</li>
                        <li>混沌工程 - 主动测试韧性</li>
                    </ul>
                </div>
            </div>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        
        const status = computed(() => store.status)
        const healComponent = ref('')
        const healIssue = ref('')
        const healResult = ref(null)
        
        const triggerHealing = async () => {
            if (healComponent.value && healIssue.value) {
                healResult.value = await store.requestHealing(healComponent.value, healIssue.value)
            }
        }
        
        return { status, healComponent, healIssue, healResult, triggerHealing }
    }
}

const SettingsPage = {
    template: `
        <div class="settings">
            <h1><i class="mdi mdi-cog"></i> 设置</h1>
            
            <div class="grid">
                <div class="card">
                    <h3><i class="mdi mdi-cog"></i> 系统设置</h3>
                    
                    <div style="margin-bottom: 16px;">
                        <h4 style="margin-bottom: 8px; color: #aaa;">Ollama配置</h4>
                        
                        <label style="font-size: 14px; color: #888;">Ollama地址</label>
                        <input v-model="configData.ollama.url" class="input" placeholder="http://localhost:11434">
                        
                        <label style="font-size: 14px; color: #888; margin-top: 12px; display: block;">默认模型</label>
                        <input v-model="configData.ollama.default_model" class="input" placeholder="llama3">
                    </div>
                    
                    <div style="margin-bottom: 16px;">
                        <h4 style="margin-bottom: 8px; color: #aaa;">系统配置</h4>
                        
                        <label style="font-size: 14px; color: #888;">健康检查间隔(秒)</label>
                        <input v-model="configData.system.health_check_interval" class="input" type="number" min="10">
                        
                        <label style="font-size: 14px; color: #888; margin-top: 12px; display: block;">最大并发任务</label>
                        <input v-model="configData.system.max_concurrent_tasks" class="input" type="number" min="1">
                    </div>
                    
                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-primary" @click="saveConfig">保存设置</button>
                        <button class="btn btn-secondary" @click="resetConfig">重置</button>
                    </div>
                </div>
                
                <div class="card">
                    <h3><i class="mdi mdi-information"></i> 版本信息</h3>
                    <p style="margin-bottom: 8px;"><strong>版本</strong>: {{ configData.version }}</p>
                    <p style="margin-bottom: 8px;"><strong>LivingTreeAlAgent NG</strong></p>
                    
                    <div style="margin-top: 16px;">
                        <h4 style="margin-bottom: 8px; color: #aaa;">架构</h4>
                        <ul style="margin-left: 20px;">
                            <li>PyQt6 WebEngine</li>
                            <li>Vue 3 + Pinia</li>
                            <li>QWebChannel通信</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        const config = computed(() => store.config)
        
        const configData = reactive({
            version: '2.0.0',
            ollama: {
                url: 'http://localhost:11434',
                default_model: 'llama3'
            },
            system: {
                health_check_interval: 60,
                max_concurrent_tasks: 10
            }
        })
        
        // 初始化配置数据
        if (config.value) {
            Object.assign(configData, config.value)
        }
        
        const saveConfig = async () => {
            try {
                await store.updateConfig('ollama.url', configData.ollama.url)
                await store.updateConfig('ollama.default_model', configData.ollama.default_model)
                await store.updateConfig('system.health_check_interval', configData.system.health_check_interval)
                await store.updateConfig('system.max_concurrent_tasks', configData.system.max_concurrent_tasks)
                store.showToast('设置保存成功！')
            } catch (e) {
                console.error('保存配置失败:', e)
                store.showToast('保存失败，请重试')
            }
        }
        
        const resetConfig = () => {
            if (confirm('确定要重置所有设置吗?')) {
                configData.version = '2.0.0'
                configData.ollama = {
                    url: 'http://localhost:11434',
                    default_model: 'llama3'
                }
                configData.system = {
                    health_check_interval: 60,
                    max_concurrent_tasks: 10
                }
                store.showToast('设置已重置！')
            }
        }
        
        return { configData, saveConfig, resetConfig }
    }
}

const AboutPage = {
    template: `
        <div class="about">
            <h1><i class="mdi mdi-information"></i> 关于</h1>
            
            <div class="card">
                <h3>LivingTreeAlAgent NG</h3>
                <p>创新的 AI 原生分布式系统架构</p>
                
                <h4>核心创新</h4>
                <ul>
                    <li>🧠 大脑启发记忆系统 - 不会遗忘</li>
                    <li>🛡️ 自修复容错系统 - 不会中断</li>
                    <li>📚 持续学习系统 - 会学习</li>
                    <li>🤔 认知推理系统 - 会思考</li>
                    <li>🔧 自我意识系统 - 会修复自己</li>
                </ul>
                
                <h4>技术栈</h4>
                <ul>
                    <li><strong>后端</strong>: Python 3, PyQt6</li>
                    <li><strong>前端</strong>: Vue 3, Pinia</li>
                    <li><strong>AI</strong>: Ollama, LLM集成</li>
                    <li><strong>数据</strong>: SQLite, JSON持久化</li>
                    <li><strong>通信</strong>: QWebChannel</li>
                </ul>
                
                <h4>架构</h4>
                <p>PyQt6 WebEngine + Vue 3</p>
                
                <h4>版本</h4>
                <p v-if="config">v{{ config.version }}</p>
            </div>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        const config = computed(() => store.config)
        return { config }
    }
}

// =========================================================================
// 主应用
// =========================================================================

const App = {
    template: `
        <div class="app-container">
            <nav class="sidebar">
                <div class="logo">
                    <i class="mdi mdi-tree"></i>
                    <span>LivingTree</span>
                </div>
                
                <div 
                    class="nav-item" 
                    v-for="route in routes" 
                    :class="{ 'active': $route.path === route.path }"
                    @click="$router.push(route.path)">
                    <i :class="route.icon"></i>
                    <span>{{ route.name }}</span>
                </div>
                
                <div class="connection-status" :class="connected ? 'connected' : 'disconnected'">
                    <i class="mdi mdi-circle"></i>
                    <span>{{ connected ? '已连接' : '未连接' }}</span>
                </div>
            </nav>
            
            <main class="main-content">
                <header class="header">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <h3 style="margin: 0;">{{ currentRouteName }}</h3>
                    </div>
                    <div class="notifications">
                        <div 
                            class="notification" 
                            v-for="n in notifications.slice(0, 3)" 
                            :key="n.id">
                            <span>{{ n.type }}</span>
                            <span>{{ n.time }}</span>
                        </div>
                    </div>
                </header>
                
                <div class="content">
                    <router-view></router-view>
                </div>
            </main>
        </div>
    `,
    setup() {
        const store = useBackendStore()
        
        const connected = computed(() => store.connected)
        const notifications = computed(() => store.notifications)
        
        const routes = [
            { path: '/', name: '仪表板', icon: 'mdi mdi-view-dashboard' },
            { path: '/memory', name: '记忆系统', icon: 'mdi mdi-brain' },
            { path: '/knowledge', name: '知识库', icon: 'mdi mdi-bookshelf' },
            { path: '/healing', name: '自修复', icon: 'mdi mdi-heart-pulse' },
            { path: '/settings', name: '设置', icon: 'mdi mdi-cog' },
            { path: '/about', name: '关于', icon: 'mdi mdi-information' }
        ]
        
        const currentRouteName = computed(() => {
            const route = routes.find(r => r.path === window.location.hash.slice(1) || '/')
            return route ? route.name : '未知'
        })
        
        onMounted(async () => {
            await store.init()
        })
        
        return {
            connected, notifications, routes, currentRouteName
        }
    }
}

// =========================================================================
// 路由
// =========================================================================
const router = createRouter({
    history: createWebHashHistory(),
    routes: [
        { path: '/', component: Dashboard },
        { path: '/memory', component: MemoryPage },
        { path: '/knowledge', component: KnowledgePage },
        { path: '/healing', name: 'healing', component: HealingPage },
        { path: '/settings', component: SettingsPage },
        { path: '/about', component: AboutPage }
    ]
})

// =========================================================================
// 创建应用
// =========================================================================
const pinia = createPinia()
const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')
