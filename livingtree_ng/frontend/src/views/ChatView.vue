<template>
    <div class="chat-page">
        <div class="chat-grid">
            <ChatArea 
                :messages="chatMessages" 
                :loading="chatLoading" 
                :modelName="currentModelName"
                @send="handleSendMessage"
            />
            <div style="display: flex; flex-direction: column; gap: 20px;">
                <ProviderSelector 
                    :providers="providers" 
                    :currentProvider="currentProvider"
                    @select="handleSelectProvider"
                />
                <ProviderSettings 
                    :apiKey="apiKey" 
                    :baseUrl="baseUrl"
                    @save="handleSaveSettings"
                    @check="handleCheckConnection"
                />
                <ModelSelector 
                    :models="currentProviderModels" 
                    :selectedModel="selectedModel"
                    :thinkingMode="currentProviderThinkingMode"
                    @select="handleSelectModel"
                />
                <SessionList 
                    :sessions="sessions" 
                    :currentSessionId="currentSessionId"
                    @create="handleCreateSession"
                    @load="handleLoadSession"
                />
            </div>
        </div>
    </div>
</template>

<script>
import ChatArea from '../components/ChatArea.vue'
import ProviderSelector from '../components/ProviderSelector.vue'
import ProviderSettings from '../components/ProviderSettings.vue'
import ModelSelector from '../components/ModelSelector.vue'
import SessionList from '../components/SessionList.vue'

export default {
    name: 'ChatView',
    components: {
        ChatArea,
        ProviderSelector,
        ProviderSettings,
        ModelSelector,
        SessionList
    },
    props: {
        providers: {
            type: Array,
            required: true
        },
        currentProvider: {
            type: String,
            required: true
        },
        currentProviderName: {
            type: String,
            default: ''
        },
        currentProviderThinkingMode: {
            type: Boolean,
            default: false
        },
        apiKey: {
            type: String,
            default: ''
        },
        baseUrl: {
            type: String,
            default: ''
        },
        selectedModel: {
            type: String,
            required: true
        },
        currentProviderModels: {
            type: Array,
            required: true
        },
        chatMessages: {
            type: Array,
            required: true
        },
        chatLoading: {
            type: Boolean,
            default: false
        },
        sessions: {
            type: Array,
            required: true
        },
        currentSessionId: {
            type: String,
            default: ''
        }
    },
    emits: [
        'sendMessage', 
        'selectProvider', 
        'saveSettings', 
        'checkConnection',
        'selectModel',
        'createSession',
        'loadSession'
    ],
    computed: {
        currentModelName() {
            return this.selectedModel
        }
    },
    methods: {
        handleSendMessage(message) {
            this.$emit('sendMessage', message)
        },
        handleSelectProvider(providerName) {
            this.$emit('selectProvider', providerName)
        },
        handleSaveSettings(settings) {
            this.$emit('saveSettings', settings)
        },
        handleCheckConnection() {
            this.$emit('checkConnection')
        },
        handleSelectModel(modelName) {
            this.$emit('selectModel', modelName)
        },
        handleCreateSession() {
            this.$emit('createSession')
        },
        handleLoadSession(sessionId) {
            this.$emit('loadSession', sessionId)
        }
    }
}
</script>
