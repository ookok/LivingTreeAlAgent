<template>
  <div class="app-container">
    <Sidebar 
      :activeTab="store.state.activeTab" 
      :systemOnline="store.state.systemOnline"
      @navigate="handleNavigate"
    />
    
    <main class="main-content" :class="{ 'ide-layout': store.state.activeTab === 'ide' }">
      <Dashboard 
        v-if="store.state.activeTab === 'dashboard'"
        :systemStatus="store.state.systemStatus"
        :apiStats="store.state.apiStats"
        :cognitiveLoad="store.state.cognitiveLoad"
        :activeSystems="store.activeSystems"
        :totalSystems="store.totalSystems"
        :getStatusClass="store.getStatusClass"
        :formatSystemName="store.formatSystemName"
        :formatStatus="store.formatStatus"
      />
      
      <IDE 
        v-if="store.state.activeTab === 'ide'"
      />
      
      <Memory 
        v-if="store.state.activeTab === 'memory'"
        :memories="store.state.memories"
        @addMemory="handleAddMemory"
        @refreshMemory="handleRefreshMemory"
      />
      
      <Learning 
        v-if="store.state.activeTab === 'learning'"
        :learningTasks="store.state.learningTasks"
        :ewcStatus="store.state.ewcStatus"
      />
      
      <Reasoning 
        v-if="store.state.activeTab === 'reasoning'"
        :reasoningStatus="store.state.reasoningStatus"
        @executeReasoning="handleExecuteReasoning"
      />
      
      <SelfAwareness 
        v-if="store.state.activeTab === 'selfawareness'"
        :autonomyLevel="store.state.autonomyLevel"
        :goalStats="store.state.goalStats"
        :activeGoals="store.state.activeGoals"
        :reflectionHistory="store.state.reflectionHistory"
        :getPriorityClass="store.getPriorityClass"
        :getPriorityLabel="store.getPriorityLabel"
        @setAutonomyLevel="handleSetAutonomyLevel"
        @addGoal="handleAddGoal"
        @triggerReflection="handleTriggerReflection"
      />
      
      <MCP 
        ref="mcpRef"
        v-if="store.state.activeTab === 'mcp'"
        :mcpStatus="store.state.mcpStatus"
        :mcpStats="store.state.mcpStats"
        @toggleMCP="handleToggleMCP"
        @callMCPTool="handleCallMCPTool"
      />
      
      <Observability 
        v-if="store.state.activeTab === 'observability'"
      />
      
      <DocumentProcessor 
        v-if="store.state.activeTab === 'documents'"
      />
      
      <SkillPanel 
        v-if="store.state.activeTab === 'skills'"
      />
      
      <AutomationPanel 
        v-if="store.state.activeTab === 'automation'"
      />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import Sidebar from './components/Sidebar.vue';
import Dashboard from './components/Dashboard.vue';
import IDE from './components/IDE.vue';
import Memory from './components/Memory.vue';
import Learning from './components/Learning.vue';
import Reasoning from './components/Reasoning.vue';
import SelfAwareness from './components/SelfAwareness.vue';
import MCP from './components/MCP.vue';
import Observability from './components/Observability.vue';
import DocumentProcessor from './components/DocumentProcessor.vue';
import SkillPanel from './components/SkillPanel.vue';
import AutomationPanel from './components/AutomationPanel.vue';
import { useAppStore } from './stores/appStore';
import { backendService } from './utils/backend';

const store = useAppStore();
const mcpRef = ref(null);

let updateInterval = null;

const handleNavigate = (tab) => {
  store.setActiveTab(tab);
};

const handleAddMemory = () => {
  backendService.addMemory('测试记忆内容', 'short');
};

const handleRefreshMemory = () => {
  backendService.refreshMemory();
};

const handleExecuteReasoning = (query, type) => {
  backendService.executeReasoning(query, type);
};

const handleSetAutonomyLevel = (level) => {
  backendService.setAutonomyLevel(level);
};

const handleAddGoal = (description, priority) => {
  backendService.addGoal(description, priority);
};

const handleTriggerReflection = () => {
  backendService.triggerReflection();
};

const handleToggleMCP = () => {
  backendService.toggleMCP();
};

const handleCallMCPTool = (toolName, params) => {
  backendService.callMCPTool(toolName, params);
};

const updateData = () => {
  backendService.getSystemStatus();
  backendService.getAPIStats();
  backendService.getMCPStatus();
};

onMounted(async () => {
  await backendService.init();
  
  backendService.on('onStatusUpdate', (data) => {
    store.updateSystemStatus(data);
  });
  
  backendService.on('onAPIStats', (data) => {
    store.updateAPIStats(data);
  });
  
  backendService.on('onMemoryUpdate', (data) => {
    store.updateMemory(data);
  });
  
  backendService.on('onLearningUpdate', (data) => {
    store.updateLearning(data);
  });
  
  backendService.on('onReasoningResult', (data) => {
    console.log('推理结果:', data);
  });
  
  backendService.on('onSelfAwarenessUpdate', (data) => {
    store.updateSelfAwareness(data);
  });
  
  backendService.on('onMCPStatus', (data) => {
    store.updateMCPStatus(data);
  });
  
  backendService.on('onToolResult', (data) => {
    if (mcpRef.value) {
      mcpRef.value.setToolResult(JSON.parse(data));
    }
  });
  
  updateData();
  updateInterval = setInterval(updateData, 5000);
});

onUnmounted(() => {
  if (updateInterval) {
    clearInterval(updateInterval);
  }
});
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  overflow: hidden;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: #ffffff;
}

#app {
  height: 100%;
}

.app-container {
  display: flex;
  height: 100vh;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
}

.main-content.ide-layout {
  overflow: hidden;
  background: transparent;
}
</style>