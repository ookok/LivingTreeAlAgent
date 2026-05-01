<template>
    <div>
        <h1><i class="mdi mdi-cog"></i>设置</h1>
        <div class="grid">
            <div class="card">
                <h3><i class="mdi mdi-robot"></i>LLM提供商管理</h3>
                <div 
                    v-for="provider in providers" 
                    :key="provider.name" 
                    :class="['provider-item', { active: currentProvider === provider.name }]"
                    @click="$emit('selectProvider', provider.name)"
                >
                    <div style="font-weight: bold;">{{ provider.display_name }}</div>
                    <div style="font-size: 12px; opacity: 0.7;">{{ provider.base_url }}</div>
                </div>
            </div>
            <div class="card">
                <h3><i class="mdi mdi-key"></i>API配置</h3>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; margin-bottom: 6px; font-size: 13px;">当前提供商</label>
                    <input class="input" :value="currentProviderName" disabled>
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; margin-bottom: 6px; font-size: 13px;">API密钥</label>
                    <input class="input" v-model="apiKey" type="password" placeholder="输入API密钥">
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; margin-bottom: 6px; font-size: 13px;">API地址</label>
                    <input class="input" v-model="baseUrl" placeholder="https://api.example.com/v1">
                </div>
                <button class="btn btn-primary" @click="saveSettings">保存设置</button>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'SettingsView',
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
        apiKey: {
            type: String,
            default: ''
        },
        baseUrl: {
            type: String,
            default: ''
        }
    },
    emits: ['selectProvider', 'saveSettings'],
    data() {
        return {
            localApiKey: this.apiKey,
            localBaseUrl: this.baseUrl
        }
    },
    watch: {
        apiKey(newVal) {
            this.localApiKey = newVal
        },
        baseUrl(newVal) {
            this.localBaseUrl = newVal
        }
    },
    methods: {
        saveSettings() {
            this.$emit('saveSettings', {
                apiKey: this.localApiKey,
                baseUrl: this.localBaseUrl
            })
        }
    }
}
</script>
