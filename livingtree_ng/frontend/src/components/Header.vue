<template>
    <div class="header">
        <div style="display: flex; align-items: center; gap: 12px;">
            <h3>
                <i :class="currentNavItem?.icon"></i>
                {{ currentNavItem?.name }}
            </h3>
            <span v-if="providerName" class="info-box" style="font-size: 12px; padding: 4px 10px;">
                {{ providerName }}
            </span>
        </div>
        <div v-if="showToast" class="toast">{{ toastMessage }}</div>
    </div>
</template>

<script>
export default {
    name: 'Header',
    props: {
        currentPage: {
            type: String,
            required: true
        },
        providerName: {
            type: String,
            default: ''
        },
        showToast: {
            type: Boolean,
            default: false
        },
        toastMessage: {
            type: String,
            default: ''
        }
    },
    computed: {
        currentNavItem() {
            const navItems = [
                { id: 'chat', name: 'AI 聊天', icon: 'mdi mdi-chat' },
                { id: 'dashboard', name: '系统概览', icon: 'mdi mdi-view-dashboard' },
                { id: 'settings', name: '设置', icon: 'mdi mdi-cog' }
            ]
            return navItems.find(n => n.id === this.currentPage)
        }
    }
}
</script>
