<template>
    <div class="card" style="flex: 1;">
        <h3><i class="mdi mdi-history"></i>会话</h3>
        <div style="margin-bottom: 12px;">
            <button class="btn btn-primary" @click="$emit('create')" style="width: 100%;">
                <i class="mdi mdi-plus"></i>新建会话
            </button>
        </div>
        <div style="height: calc(100% - 50px); overflow-y: auto;">
            <div 
                class="session-item" 
                v-for="session in sessions" 
                :key="session.id" 
                :class="{ active: currentSessionId === session.id }"
                @click="$emit('load', session.id)"
            >
                <div class="title">{{ session.title }}</div>
                <div class="time">{{ formatTime(session.updated_at) }}</div>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'SessionList',
    props: {
        sessions: {
            type: Array,
            required: true
        },
        currentSessionId: {
            type: String,
            default: ''
        }
    },
    emits: ['create', 'load'],
    methods: {
        formatTime(timestamp) {
            return new Date(timestamp).toLocaleString()
        }
    }
}
</script>
