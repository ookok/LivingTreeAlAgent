<template>
  <div class="software-manager-page">
    <!-- 顶部搜索栏 -->
    <div class="sm-header">
      <h2>软件工具箱</h2>
      <div class="sm-search-box">
        <input type="text" v-model="searchQuery" placeholder="搜索软件..." @keyup.enter="searchSoftware">
        <i class="fa-solid fa-search"></i>
      </div>
      <div :class="['backend-status', backendStatus === 'none' ? 'warning' : '']">
        <i class="fa-solid fa-check-circle"></i>
        {{ backendStatusText }}
      </div>
    </div>

    <!-- 导航选项卡 -->
    <div class="sm-tabs">
      <button :class="{ active: currentView === 'store' }" @click="currentView = 'store'">
        <i class="fa-solid fa-store"></i>
        软件商店
      </button>
      <button :class="{ active: currentView === 'installed' }" @click="loadInstalled">
        <i class="fa-solid fa-download"></i>
        已安装
      </button>
      <button :class="{ active: currentView === 'system' }" @click="loadSystemOverview">
        <i class="fa-solid fa-desktop"></i>
        系统扫描
      </button>
    </div>

    <!-- 分类标签 -->
    <div v-if="currentView === 'store'" class="sm-categories">
      <button :class="{ active: selectedCategory === 'all' }" @click="selectedCategory = 'all'">
        <i class="fa-solid fa-layer-group"></i>
        全部
      </button>
      <button v-for="(info, key) in categories" :key="key" 
              :class="{ active: selectedCategory === key }" 
              @click="selectedCategory = key">
        <i :class="getCategoryIcon(key)"></i>
        {{ info.name }}
      </button>
    </div>

    <!-- 软件网格 -->
    <div v-if="currentView === 'store'" class="sm-grid">
      <div v-for="software in filteredSoftware" :key="software.id" 
           class="sm-card" @click="showDetail(software)">
        <div class="card-icon">
          <i :class="getSoftwareIcon(software.icon)"></i>
        </div>
        <div v-if="installedIds.includes(software.id)" class="installed-badge">
          <i class="fa-solid fa-check"></i>
          已安装
        </div>
        <h3>{{ software.name }}</h3>
        <p>{{ software.description }}</p>
        <div class="tags">
          <span v-for="tag in software.tags.slice(0, 3)" :key="tag" class="tag">{{ tag }}</span>
        </div>
        <div class="card-actions">
          <button v-if="installedIds.includes(software.id)" class="btn btn-launch" @click.stop="launchSoftware(software)">
            <i class="fa-solid fa-play"></i>
            启动
          </button>
          <button v-if="installedIds.includes(software.id)" class="btn btn-uninstall" @click.stop="confirmUninstall(software)">
            <i class="fa-solid fa-trash"></i>
            卸载
          </button>
          <button v-else class="btn btn-install" @click.stop="installSoftware(software)">
            <i class="fa-solid fa-download"></i>
            安装
          </button>
        </div>
      </div>
    </div>

    <!-- 已安装列表 -->
    <div v-else-if="currentView === 'installed'" class="sm-grid">
      <div v-for="software in installedSoftware" :key="software.id" class="sm-card">
        <div class="card-icon">
          <i :class="getSoftwareIcon(getSoftwareInfo(software.id)?.icon || 'box')"></i>
        </div>
        <h3>{{ software.name }}</h3>
        <p>版本: {{ software.version }}</p>
        <span class="tag">{{ software.source }}</span>
        <div class="card-actions">
          <button class="btn btn-launch" @click="launchSoftware(software)">
            <i class="fa-solid fa-play"></i>
            启动
          </button>
          <button class="btn btn-uninstall" @click="confirmUninstall(software)">
            <i class="fa-solid fa-trash"></i>
            卸载
          </button>
        </div>
      </div>
    </div>

    <!-- 系统扫描视图 -->
    <div v-else-if="currentView === 'system'" class="sm-system">
      <div class="system-stats">
        <div class="stat-card">
          <div class="stat-icon"><i class="fa-solid fa-archive"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ systemOverview.total_scanned || 0 }}</div>
            <div class="stat-label">已扫描软件</div>
          </div>
        </div>
        <div class="stat-card matched">
          <div class="stat-icon"><i class="fa-solid fa-check-circle"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ systemOverview.matched_count || 0 }}</div>
            <div class="stat-label">已匹配</div>
          </div>
        </div>
        <div class="stat-card unmatched">
          <div class="stat-icon"><i class="fa-solid fa-question-circle"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ systemOverview.unmatched_count || 0 }}</div>
            <div class="stat-label">未匹配</div>
          </div>
        </div>
        <div class="stat-card python">
          <div class="stat-icon"><i class="fa-brands fa-python"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ systemOverview.python_packages_count || 0 }}</div>
            <div class="stat-label">Python包</div>
          </div>
        </div>
      </div>

      <div class="system-section">
        <h3>已匹配软件</h3>
        <div class="matched-list">
          <div v-for="item in systemOverview.matched" :key="item.name" class="matched-item">
            <div class="item-icon">
              <i :class="getSoftwareIcon(item.metadata_match?.icon || 'box')"></i>
            </div>
            <div class="item-info">
              <span class="item-name">{{ item.name }}</span>
              <span class="item-version">{{ item.version }}</span>
            </div>
            <div class="match-badge">匹配度: {{ (item.match_score * 100).toFixed(0) }}%</div>
          </div>
        </div>
      </div>

      <div class="system-section">
        <h3>未匹配软件（部分）</h3>
        <div class="unmatched-list">
          <div v-for="item in systemOverview.unmatched" :key="item.name" class="unmatched-item">
            <div class="item-icon">
              <i class="fa-solid fa-unknown"></i>
            </div>
            <div class="item-info">
              <span class="item-name">{{ item.name }}</span>
              <span class="item-version">{{ item.version }}</span>
            </div>
            <span class="item-publisher">{{ item.publisher }}</span>
          </div>
        </div>
      </div>

      <button class="btn btn-primary" @click="loadSystemOverview">
        <i class="fa-solid fa-refresh"></i>
        重新扫描
      </button>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ selectedSoftware?.name }} - 详情</h2>
          <button class="modal-close" @click="closeModal">
            <i class="fa-solid fa-x"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="modal-icon">
            <i :class="getSoftwareIcon(selectedSoftware?.icon || 'box')"></i>
          </div>
          <h3>{{ selectedSoftware?.name }}</h3>
          <p>{{ selectedSoftware?.description }}</p>
          
          <div class="info-grid">
            <div class="info-item">
              <label>来源</label>
              <span>{{ getBackendName(selectedSoftware?.backend) }}</span>
            </div>
            <div class="info-item">
              <label>包ID</label>
              <span>{{ selectedSoftware?.package_id }}</span>
            </div>
            <div class="info-item">
              <label>分类</label>
              <span>{{ getCategoryName(selectedSoftware?.category) }}</span>
            </div>
            <div class="info-item">
              <label>状态</label>
              <span>{{ installedIds.includes(selectedSoftware?.id) ? '已安装' : '未安装' }}</span>
            </div>
          </div>

          <div v-if="installingId === selectedSoftware?.id" class="install-status">
            <div class="status-bar">
              <div :class="['status-indicator', installState]"></div>
              <span>{{ getStatusText(installState) }}</span>
            </div>
            <div class="progress-bar">
              <div class="progress" :style="{ width: installProgress + '%' }"></div>
            </div>
            <div class="logs" v-if="showLogs">
              <div v-for="(log, index) in installLogs" :key="index">{{ log }}</div>
            </div>
            <button class="toggle-logs" @click="showLogs = !showLogs">
              {{ showLogs ? '隐藏日志' : '显示日志' }}
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeModal">关闭</button>
          <button v-if="!installedIds.includes(selectedSoftware?.id)" 
                  class="btn btn-primary" 
                  :disabled="installingId !== null"
                  @click="installSoftware(selectedSoftware)">
            <i class="fa-solid fa-download"></i>
            {{ installingId === selectedSoftware?.id ? '安装中...' : '安装' }}
          </button>
          <button v-else class="btn btn-uninstall" @click="confirmUninstall(selectedSoftware)">
            <i class="fa-solid fa-trash"></i>
            卸载
          </button>
        </div>
      </div>
    </div>

    <!-- Toast提示 -->
    <div v-if="toast.show" :class="['toast', toast.type]">
      <i :class="toast.icon"></i>
      <span>{{ toast.message }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';

// 响应式数据
const searchQuery = ref('');
const selectedCategory = ref('all');
const currentView = ref('store');
const showModal = ref(false);
const selectedSoftware = ref(null);
const softwareList = ref([]);
const installedSoftware = ref([]);
const installedIds = ref([]);
const categories = ref({});
const backendStatus = ref('none');

// 安装状态
const installingId = ref(null);
const installState = ref('pending');
const installProgress = ref(0);
const installLogs = ref([]);
const showLogs = ref(false);

// 系统扫描数据
const systemOverview = ref({
  total_scanned: 0,
  matched_count: 0,
  unmatched_count: 0,
  python_packages_count: 0,
  path_executables_count: 0,
  matched: [],
  unmatched: []
});

// Toast提示
const toast = ref({
  show: false,
  message: '',
  type: 'success',
  icon: 'fa-solid fa-check-circle'
});

// 计算属性
const backendStatusText = computed(() => {
  if (backendStatus.value === 'none') {
    return '检测包管理器中...';
  }
  return `已连接: ${backendStatus.value}`;
});

const filteredSoftware = computed(() => {
  let list = softwareList.value;
  
  if (selectedCategory.value !== 'all') {
    list = list.filter(s => s.category === selectedCategory.value);
  }
  
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase();
    list = list.filter(s => 
      s.name.toLowerCase().includes(query) ||
      s.description.toLowerCase().includes(query) ||
      s.tags.some(t => t.toLowerCase().includes(query))
    );
  }
  
  return list;
});

// 方法
const initWebChannel = () => {
  if (window.QWebChannel) {
    new window.QWebChannel(channel => {
      window.softwareManager = channel.objects.softwareManager;
      setupChannelCallbacks();
    });
  }
};

const setupChannelCallbacks = () => {
  if (window.softwareManager && window.softwareManager.messageReceived) {
    window.softwareManager.messageReceived.connect((message) => {
      handleChannelMessage(message);
    });
  }
};

const callBridge = async (action, params = {}) => {
  if (!window.softwareManager) {
    return await simulateCall(action, params);
  }
  
  const message = JSON.stringify({ action, ...params });
  const result = window.softwareManager.call(message);
  return JSON.parse(result);
};

const simulateCall = async (action, params) => {
  const mockData = {
    'get_software_list': {
      success: true,
      software: [
        { id: 'vscode', name: 'Visual Studio Code', category: 'development', description: '轻量级代码编辑器', icon: 'vscode', backend: 'winget', package_id: 'Microsoft.VisualStudioCode', tags: ['code', 'editor'] },
        { id: 'python', name: 'Python', category: 'development', description: 'Python编程语言', icon: 'python', backend: 'winget', package_id: 'Python.Python.3.11', tags: ['python', 'programming'] },
        { id: 'git', name: 'Git', category: 'development', description: '版本控制系统', icon: 'git', backend: 'winget', package_id: 'Git.Git', tags: ['version', 'control'] },
        { id: 'qgis', name: 'QGIS', category: 'industrial', description: '开源GIS系统', icon: 'qgis', backend: 'chocolatey', package_id: 'qgis', tags: ['gis', 'mapping'] }
      ],
      categories: {
        development: { name: '开发工具', icon: 'code' },
        computation: { name: '计算工具', icon: 'calculator' },
        industrial: { name: '工业软件', icon: 'factory' },
        emergency: { name: '应急工具', icon: 'alert' },
        productivity: { name: '办公工具', icon: 'office' }
      }
    },
    'get_backend_status': {
      success: true,
      backend: 'winget',
      available: ['winget']
    },
    'get_system_overview': {
      success: true,
      data: {
        total_scanned: 45,
        matched_count: 8,
        unmatched_count: 37,
        python_packages_count: 23,
        path_executables_count: 156,
        matched: [
          { name: 'Python 3.11', version: '3.11.0', match_score: 0.9, metadata_match: { icon: 'python' } },
          { name: 'Git', version: '2.42.0', match_score: 0.85, metadata_match: { icon: 'git' } }
        ],
        unmatched: [
          { name: 'Microsoft Office', version: '2021', publisher: 'Microsoft' },
          { name: 'Google Chrome', version: '118.0', publisher: 'Google' }
        ]
      }
    },
    'get_installed': {
      success: true,
      installed: [
        { id: 'python', name: 'Python', version: '3.11.0', source: 'winget' },
        { id: 'git', name: 'Git', version: '2.42.0', source: 'winget' }
      ]
    }
  };
  
  return mockData[action] || { success: false, error: 'Not implemented' };
};

const handleChannelMessage = (message) => {
  try {
    const data = JSON.parse(message);
    
    if (data.type === 'status' && data.pkg === installingId.value) {
      installState.value = data.state;
      if (data.message) {
        installLogs.value.push(data.message);
      }
    } else if (data.type === 'progress' && data.pkg === installingId.value) {
      installProgress.value = data.progress;
    } else if (data.type === 'result' && data.pkg === installingId.value) {
      installingId.value = null;
      if (data.success) {
        showToast('安装成功', 'success');
        installedIds.value.push(data.pkg);
      } else {
        showToast('安装失败', 'error');
      }
    }
  } catch (e) {
    console.error('Failed to parse channel message:', e);
  }
};

const loadData = async () => {
  const result = await callBridge('get_software_list');
  if (result.success) {
    softwareList.value = result.software;
    categories.value = result.categories;
  }
};

const loadBackendStatus = async () => {
  const result = await callBridge('get_backend_status');
  if (result.success) {
    backendStatus.value = result.backend || 'none';
  }
};

const loadInstalled = async () => {
  currentView.value = 'installed';
  const result = await callBridge('get_installed');
  if (result.success) {
    installedSoftware.value = result.installed;
    installedIds.value = installedSoftware.value.map(s => s.id);
  }
};

const loadSystemOverview = async () => {
  currentView.value = 'system';
  const result = await callBridge('get_system_overview');
  if (result.success) {
    systemOverview.value = result.data;
  }
};

const searchSoftware = () => {
  selectedCategory.value = 'all';
};

const showDetail = (software) => {
  selectedSoftware.value = software;
  showModal.value = true;
};

const closeModal = () => {
  showModal.value = false;
  selectedSoftware.value = null;
  installingId.value = null;
  installState.value = 'pending';
  installProgress.value = 0;
  installLogs.value = [];
  showLogs.value = false;
};

const installSoftware = async (software) => {
  if (!software) return;
  
  installingId.value = software.id;
  installState.value = 'detecting';
  installProgress.value = 0;
  installLogs.value = [];
  showLogs.value = false;
  showModal.value = true;
  selectedSoftware.value = software;
  
  await callBridge('install_software', { software_id: software.id });
};

const confirmUninstall = async (software) => {
  if (!software) return;
  
  if (confirm(`确定要卸载 ${software.name} 吗？`)) {
    const result = await callBridge('uninstall_software', { software_id: software.id });
    if (result.success) {
      showToast('卸载成功', 'success');
      installedIds.value = installedIds.value.filter(id => id !== software.id);
      installedSoftware.value = installedSoftware.value.filter(s => s.id !== software.id);
    } else {
      showToast('卸载失败', 'error');
    }
  }
};

const launchSoftware = (software) => {
  showToast(`正在启动 ${software.name}`, 'success');
};

const getCategoryIcon = (category) => {
  const icons = {
    development: 'fa-solid fa-code',
    computation: 'fa-solid fa-calculator',
    industrial: 'fa-solid fa-factory',
    emergency: 'fa-solid fa-alert-triangle',
    productivity: 'fa-solid fa-briefcase'
  };
  return icons[category] || 'fa-solid fa-layer-group';
};

const getSoftwareIcon = (icon) => {
  const icons = {
    vscode: 'fa-solid fa-code',
    python: 'fa-brands fa-python',
    git: 'fa-brands fa-git-alt',
    nodejs: 'fa-brands fa-node-js',
    docker: 'fa-brands fa-docker',
    anaconda: 'fa-solid fa-flask-vial',
    julia: 'fa-solid fa-circle',
    r: 'fa-solid fa-chart-line',
    qgis: 'fa-solid fa-map',
    grass: 'fa-solid fa-tree',
    paraview: 'fa-solid fa-box',
    gnuplot: 'fa-solid fa-chart-bar',
    octave: 'fa-solid fa-wrench',
    notepad: 'fa-solid fa-file-text',
    '7zip': 'fa-solid fa-compress',
    pdf: 'fa-solid fa-file-pdf',
    box: 'fa-solid fa-box',
    unknown: 'fa-solid fa-question-circle'
  };
  return icons[icon] || 'fa-solid fa-box';
};

const getBackendName = (backend) => {
  const names = {
    winget: 'Winget',
    chocolatey: 'Chocolatey',
    scoop: 'Scoop',
    direct_download: '直接下载'
  };
  return names[backend] || backend;
};

const getCategoryName = (category) => {
  return categories.value[category]?.name || category;
};

const getStatusText = (state) => {
  const texts = {
    pending: '等待中',
    detecting: '检测环境',
    downloading: '下载中',
    installing: '安装中',
    completed: '安装完成',
    failed: '安装失败'
  };
  return texts[state] || state;
};

const getSoftwareInfo = (id) => {
  return softwareList.value.find(s => s.id === id);
};

const showToast = (message, type) => {
  toast.value = {
    show: true,
    message,
    type,
    icon: type === 'success' ? 'fa-solid fa-check-circle' : 'fa-solid fa-exclamation-circle'
  };
  setTimeout(() => {
    toast.value.show = false;
  }, 3000);
};

onMounted(() => {
  initWebChannel();
  loadData();
  loadBackendStatus();
});
</script>

<style scoped>
.software-manager-page {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.sm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.sm-header h2 {
  font-size: 24px;
}

.sm-search-box {
  flex: 0 0 400px;
  position: relative;
}

.sm-search-box input {
  width: 100%;
  padding: 12px 40px 12px 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  color: #fff;
  font-size: 14px;
}

.sm-search-box input:focus {
  outline: none;
  border-color: #00d4ff;
}

.sm-search-box i {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #888;
}

.backend-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(0, 255, 136, 0.1);
  border-radius: 20px;
  font-size: 13px;
  color: #00ff88;
}

.backend-status.warning {
  background: rgba(255, 170, 0, 0.1);
  color: #ffaa00;
}

.sm-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.sm-tabs button {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.sm-tabs button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.sm-tabs button.active {
  background: rgba(0, 212, 255, 0.2);
  border-color: rgba(0, 212, 255, 0.5);
}

.sm-categories {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.sm-categories button {
  padding: 10px 24px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 25px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.sm-categories button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.sm-categories button.active {
  background: linear-gradient(135deg, #00d4ff, #0099cc);
  border-color: transparent;
}

.sm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.sm-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
}

.sm-card:hover {
  transform: translateY(-5px);
  border-color: rgba(0, 212, 255, 0.5);
  box-shadow: 0 10px 40px rgba(0, 212, 255, 0.2);
}

.card-icon {
  width: 64px;
  height: 64px;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2), rgba(0, 153, 204, 0.2));
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin-bottom: 16px;
}

.installed-badge {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(0, 255, 136, 0.2);
  border-radius: 20px;
  font-size: 12px;
  color: #00ff88;
  margin-bottom: 10px;
}

.sm-card h3 {
  font-size: 18px;
  margin-bottom: 8px;
}

.sm-card p {
  font-size: 13px;
  color: #aaa;
  margin-bottom: 16px;
  line-height: 1.5;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.tag {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  font-size: 11px;
  color: #ccc;
}

.card-actions {
  display: flex;
  gap: 10px;
}

.btn {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.3s;
}

.btn-primary {
  background: linear-gradient(135deg, #00d4ff, #0099cc);
  color: #fff;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-install {
  background: linear-gradient(135deg, #00d4ff, #0099cc);
  color: #fff;
}

.btn-install:hover {
  transform: scale(1.05);
  box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
}

.btn-install:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-launch {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-launch:hover {
  background: rgba(255, 255, 255, 0.2);
}

.btn-uninstall {
  background: rgba(255, 100, 100, 0.2);
  color: #ff6464;
  border: 1px solid rgba(255, 100, 100, 0.3);
}

.btn-uninstall:hover {
  background: rgba(255, 100, 100, 0.3);
}

.sm-system {
  max-width: 1200px;
}

.system-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-card.matched {
  border: 1px solid rgba(0, 255, 136, 0.3);
}

.stat-card.unmatched {
  border: 1px solid rgba(255, 170, 0, 0.3);
}

.stat-card.python {
  border: 1px solid rgba(0, 212, 255, 0.3);
}

.stat-icon {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #fff;
}

.stat-label {
  font-size: 13px;
  color: #888;
}

.system-section {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
}

.system-section h3 {
  margin-bottom: 15px;
}

.matched-list, .unmatched-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.matched-item, .unmatched-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}

.item-icon {
  width: 36px;
  height: 36px;
  background: rgba(0, 212, 255, 0.2);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.item-info {
  flex: 1;
}

.item-name {
  display: block;
  font-size: 14px;
  color: #fff;
}

.item-version {
  font-size: 12px;
  color: #888;
}

.item-publisher {
  font-size: 12px;
  color: #666;
}

.match-badge {
  padding: 4px 10px;
  background: rgba(0, 255, 136, 0.2);
  border-radius: 12px;
  font-size: 12px;
  color: #00ff88;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(5px);
}

.modal {
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  width: 90%;
  max-width: 500px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-close {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-body {
  padding: 20px;
}

.modal-icon {
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2), rgba(0, 153, 204, 0.2));
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  margin: 0 auto 20px;
}

.modal-body h3 {
  font-size: 24px;
  text-align: center;
  margin-bottom: 10px;
}

.modal-body p {
  color: #aaa;
  text-align: center;
  margin-bottom: 20px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin-bottom: 20px;
}

.info-item {
  background: rgba(255, 255, 255, 0.05);
  padding: 12px;
  border-radius: 12px;
}

.info-item label {
  font-size: 12px;
  color: #888;
  display: block;
  margin-bottom: 5px;
}

.info-item span {
  font-size: 14px;
  color: #fff;
}

.install-status {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 15px;
  margin-bottom: 20px;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

.status-indicator.detecting { background: #ffaa00; }
.status-indicator.downloading { background: #00d4ff; }
.status-indicator.installing { background: #00ff88; }
.status-indicator.completed { background: #00ff88; animation: none; }
.status-indicator.failed { background: #ff6464; animation: none; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress {
  height: 100%;
  background: linear-gradient(90deg, #00d4ff, #00ff88);
  border-radius: 3px;
  transition: width 0.3s;
}

.logs {
  max-height: 150px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 12px;
  color: #888;
  background: rgba(0, 0, 0, 0.3);
  padding: 10px;
  border-radius: 8px;
}

.toggle-logs {
  margin-top: 10px;
  background: none;
  border: none;
  color: #00d4ff;
  cursor: pointer;
  font-size: 13px;
}

.modal-footer {
  display: flex;
  gap: 12px;
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-footer .btn {
  flex: 1;
}

.toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: rgba(0, 0, 0, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 15px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 2000;
  animation: slideIn 0.3s;
}

.toast.success {
  border-color: #00ff88;
}

.toast.error {
  border-color: #ff6464;
}

@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
</style>