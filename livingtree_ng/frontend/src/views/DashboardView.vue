<template>
    <div>
        <h1><i class="mdi mdi-view-dashboard"></i>系统概览</h1>
        <div class="grid">
            <div class="card">
                <h3><i class="mdi mdi-chart-box"></i>系统健康</h3>
                <div style="padding: 8px 0; display: flex; justify-content: space-between;">
                    <span>状态</span>
                    <span class="status-good">正常</span>
                </div>
                <div style="padding: 8px 0; display: flex; justify-content: space-between;">
                    <span>会话数</span>
                    <span class="status-good">{{ sessions.length }}</span>
                </div>
                <div style="padding: 8px 0; display: flex; justify-content: space-between;">
                    <span>当前提供商</span>
                    <span>{{ currentProviderName }}</span>
                </div>
            </div>
            <div class="card">
                <h3><i class="mdi mdi-lightbulb-on"></i>快捷操作</h3>
                <button class="btn btn-primary" @click="$emit('navigate', 'chat')">
                    <i class="mdi mdi-chat"></i>聊天
                </button>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'DashboardView',
    props: {
        sessions: {
            type: Array,
            required: true
        },
        currentProviderName: {
            type: String,
            default: ''
        }
    },
    emits: ['navigate']
}
</script>
