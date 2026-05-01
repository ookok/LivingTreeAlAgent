<template>
    <div class="card">
        <h3><i class="mdi mdi-robot"></i>LLM提供商</h3>
        <div 
            v-for="provider in providers" 
            :key="provider.name" 
            :class="['provider-item', { active: currentProvider === provider.name, disabled: !provider.enabled }]"
            @click="$emit('select', provider.name)"
        >
            <div style="font-weight: bold;">{{ provider.display_name }}</div>
            <div style="font-size: 12px; opacity: 0.7;">{{ provider.name }}</div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'ProviderSelector',
    props: {
        providers: {
            type: Array,
            required: true
        },
        currentProvider: {
            type: String,
            required: true
        }
    },
    emits: ['select']
}
</script>
