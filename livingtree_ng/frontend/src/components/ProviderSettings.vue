<template>
    <div class="card">
        <h3><i class="mdi mdi-cog"></i>当前提供商设置</h3>
        <div style="margin-bottom: 12px;">
            <label style="display: block; margin-bottom: 6px; font-size: 13px;">API密钥</label>
            <input class="input" v-model="localApiKey" type="password" placeholder="输入API密钥">
        </div>
        <div style="margin-bottom: 12px;">
            <label style="display: block; margin-bottom: 6px; font-size: 13px;">API地址</label>
            <input class="input" v-model="localBaseUrl" placeholder="https://api.example.com/v1">
        </div>
        <button class="btn btn-primary" @click="saveSettings" style="width: 100%; margin-bottom: 8px;">
            保存设置
        </button>
        <button class="btn btn-secondary" @click="$emit('check')" style="width: 100%;">
            检查连接
        </button>
    </div>
</template>

<script>
export default {
    name: 'ProviderSettings',
    props: {
        apiKey: {
            type: String,
            default: ''
        },
        baseUrl: {
            type: String,
            default: ''
        }
    },
    emits: ['save', 'check'],
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
            this.$emit('save', {
                apiKey: this.localApiKey,
                baseUrl: this.localBaseUrl
            })
        }
    }
}
</script>
