/**
 * Qt WebChannel 后端通信工具
 * 封装与Python后端的通信逻辑
 */

class BackendService {
  constructor() {
    this.backend = null;
    this.callbacks = {};
  }

  async init() {
    return new Promise((resolve) => {
      new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
        this.backend = channel.objects.backend;
        this._setupListeners();
        resolve();
      });
    });
  }

  _setupListeners() {
    if (!this.backend) return;

    const events = [
      'onStatusUpdate',
      'onAPIStats',
      'onMemoryUpdate',
      'onLearningUpdate',
      'onReasoningResult',
      'onSelfAwarenessUpdate',
      'onMCPStatus',
      'onToolResult'
    ];

    events.forEach(eventName => {
      if (this.backend[eventName]) {
        this.backend[eventName].connect((data) => {
          if (this.callbacks[eventName]) {
            this.callbacks[eventName].forEach(cb => cb(data));
          }
        });
      }
    });
  }

  on(eventName, callback) {
    if (!this.callbacks[eventName]) {
      this.callbacks[eventName] = [];
    }
    this.callbacks[eventName].push(callback);
  }

  off(eventName, callback) {
    if (this.callbacks[eventName]) {
      this.callbacks[eventName] = this.callbacks[eventName].filter(cb => cb !== callback);
    }
  }

  async callMethod(methodName, ...args) {
    if (!this.backend || !this.backend[methodName]) {
      throw new Error(`Method ${methodName} not found`);
    }
    return new Promise((resolve) => {
      this.backend[methodName](...args, (result) => {
        resolve(result);
      });
    });
  }

  getSystemStatus() {
    return this.callMethod('getSystemStatus');
  }

  getAPIStats() {
    return this.callMethod('getAPIStats');
  }

  getMCPStatus() {
    return this.callMethod('getMCPStatus');
  }

  refreshMemory() {
    return this.callMethod('refreshMemory');
  }

  addMemory(content, type) {
    return this.callMethod('addMemory', content, type);
  }

  executeReasoning(query, type) {
    return this.callMethod('executeReasoning', query, type);
  }

  setAutonomyLevel(level) {
    return this.callMethod('setAutonomyLevel', level);
  }

  addGoal(description, priority) {
    return this.callMethod('addGoal', description, priority);
  }

  triggerReflection() {
    return this.callMethod('triggerReflection');
  }

  toggleMCP() {
    return this.callMethod('toggleMCP');
  }

  callMCPTool(toolName, params) {
    return this.callMethod('callMCPTool', toolName, JSON.stringify(params));
  }
}

export const backendService = new BackendService();
export default backendService;