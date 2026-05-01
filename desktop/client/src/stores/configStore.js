import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const API_BASE = 'http://localhost:8766/api'

export const useConfigStore = defineStore('config', () => {
  const currentModel = ref('gpt4')
  const models = ref([])
  const temperature = ref(0.7)
  const maxTokens = ref(4000)
  const isDark = ref(true)
  const showSettings = ref(false)
  const apiKey = ref('')
  const apiEndpoint = ref('')
  const autoSave = ref(true)
  const fontSize = ref(14)
  const fontFamily = ref('system')

  async function loadModels() {
    try {
      const response = await fetch(`${API_BASE}/ai/models`)
      if (response.ok) {
        const data = await response.json()
        models.value = data.map(m => ({ label: `${m.name} (${m.provider})`, value: m.id }))
      } else {
        models.value = [
          { label: 'GPT-4 Turbo (OpenAI)', value: 'gpt4' },
          { label: 'GPT-3.5 Turbo (OpenAI)', value: 'gpt3.5' },
        ]
      }
    } catch (error) {
      console.error('Failed to load models:', error)
      models.value = [
        { label: 'GPT-4 Turbo (OpenAI)', value: 'gpt4' },
        { label: 'GPT-3.5 Turbo (OpenAI)', value: 'gpt3.5' },
      ]
    }
  }

  function changeModel(model) {
    currentModel.value = model
    saveSettings()
  }

  function toggleTheme() {
    isDark.value = !isDark.value
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    saveSettings()
  }

  function loadSettings() {
    try {
      const stored = localStorage.getItem('appConfig')
      if (stored) {
        const config = JSON.parse(stored)
        currentModel.value = config.currentModel || 'gpt4'
        temperature.value = config.temperature || 0.7
        maxTokens.value = config.maxTokens || 4000
        isDark.value = config.isDark !== undefined ? config.isDark : true
        apiKey.value = config.apiKey || ''
        apiEndpoint.value = config.apiEndpoint || ''
        autoSave.value = config.autoSave !== undefined ? config.autoSave : true
        fontSize.value = config.fontSize || 14
        fontFamily.value = config.fontFamily || 'system'
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  function saveSettings() {
    const config = {
      currentModel: currentModel.value,
      temperature: temperature.value,
      maxTokens: maxTokens.value,
      isDark: isDark.value,
      apiKey: apiKey.value,
      apiEndpoint: apiEndpoint.value,
      autoSave: autoSave.value,
      fontSize: fontSize.value,
      fontFamily: fontFamily.value
    }
    localStorage.setItem('appConfig', JSON.stringify(config))
  }

  function resetSettings() {
    currentModel.value = 'gpt4'
    temperature.value = 0.7
    maxTokens.value = 4000
    isDark.value = true
    apiKey.value = ''
    apiEndpoint.value = ''
    autoSave.value = true
    fontSize.value = 14
    fontFamily.value = 'system'
    saveSettings()
  }

  watch([currentModel, temperature, maxTokens], () => {
    if (autoSave.value) {
      saveSettings()
    }
  })

  return {
    currentModel,
    models,
    temperature,
    maxTokens,
    isDark,
    showSettings,
    apiKey,
    apiEndpoint,
    autoSave,
    fontSize,
    fontFamily,
    loadModels,
    changeModel,
    toggleTheme,
    loadSettings,
    saveSettings,
    resetSettings
  }
})