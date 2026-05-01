<template>
    <div class="card chat-area">
        <h3><i class="mdi mdi-message"></i>聊天</h3>
        <div class="chat-messages" ref="messagesContainer">
            <div 
                v-for="msg in messages" 
                :key="msg.id" 
                :class="['chat-message', msg.role]"
            >
                <div class="role">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
                <div>{{ msg.content }}</div>
            </div>
            <div v-if="loading" class="chat-message assistant">
                <div class="role">AI</div>
                <div>
                    <span class="loading-inline"></span>正在思考...({{ modelName }})
                </div>
            </div>
        </div>
        <div class="chat-input-area">
            <input 
                class="input" 
                v-model="inputText" 
                placeholder="输入消息..." 
                @keyup.enter="sendMessage"
                :disabled="loading"
            >
            <button class="btn btn-primary" @click="sendMessage" :disabled="loading">
                <i class="mdi mdi-send"></i>
            </button>
        </div>
    </div>
</template>

<script>
export default {
    name: 'ChatArea',
    props: {
        messages: {
            type: Array,
            required: true
        },
        loading: {
            type: Boolean,
            default: false
        },
        modelName: {
            type: String,
            default: ''
        }
    },
    emits: ['send'],
    data() {
        return {
            inputText: ''
        }
    },
    methods: {
        sendMessage() {
            if (!this.inputText.trim() || this.loading) return
            this.$emit('send', this.inputText)
            this.inputText = ''
        }
    },
    watch: {
        messages() {
            this.$nextTick(() => {
                const container = this.$refs.messagesContainer
                if (container) {
                    container.scrollTop = container.scrollHeight
                }
            })
        }
    }
}
</script>
