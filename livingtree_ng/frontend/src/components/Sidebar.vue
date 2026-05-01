<template>
    <div class="sidebar">
        <div class="logo">
            <i class="mdi mdi-pine-tree"></i>
            <span>LivingTree</span>
        </div>
        <div 
            v-for="nav in navItems" 
            :key="nav.id" 
            :class="['nav-item', { active: currentPage === nav.id }]"
            @click="$emit('navigate', nav.id)"
        >
            <i :class="nav.icon"></i>
            <span>{{ nav.name }}</span>
        </div>
        <div :class="['connection-status', connected ? 'connected' : 'disconnected']">
            <i class="mdi mdi-circle"></i>
            <span>{{ connected ? '已连接' : '未连接' }}</span>
        </div>
    </div>
</template>

<script>
export default {
    name: 'Sidebar',
    props: {
        currentPage: {
            type: String,
            required: true
        },
        connected: {
            type: Boolean,
            default: false
        }
    },
    emits: ['navigate'],
    data() {
        return {
            navItems: [
                { id: 'chat', name: 'AI 聊天', icon: 'mdi mdi-chat' },
                { id: 'dashboard', name: '系统概览', icon: 'mdi mdi-view-dashboard' },
                { id: 'settings', name: '设置', icon: 'mdi mdi-cog' }
            ]
        }
    }
}
</script>
