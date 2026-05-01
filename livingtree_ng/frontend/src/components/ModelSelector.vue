<template>
    <div class="card">
        <h3><i class="mdi mdi-box"></i>可用模型</h3>
        <div v-if="models.length === 0" style="opacity: 0.5;">请先选择提供商</div>
        <div 
            v-for="model in models" 
            :key="model" 
            :class="['model-item', { active: selectedModel === model }]"
            @click="$emit('select', model)"
        >
            {{ model }}
        </div>
        <div v-if="thinkingMode" class="info-box" style="font-size: 12px; margin-top: 8px;">
            <i class="mdi mdi-brain"></i> 支持Thinking模式
        </div>
    </div>
</template>

<script>
export default {
    name: 'ModelSelector',
    props: {
        models: {
            type: Array,
            required: true
        },
        selectedModel: {
            type: String,
            required: true
        },
        thinkingMode: {
            type: Boolean,
            default: false
        }
    },
    emits: ['select']
}
</script>
