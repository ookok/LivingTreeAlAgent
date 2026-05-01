/**
 * 后端通信工具类
 * 通过 QWebChannel 与 Python 后端通信
 */
class BackendClient {
    constructor() {
        this.backend = window.backend;
        this.isConnected = false;
        
        // 等待WebChannel连接
        this._waitForConnection();
    }
    
    async _waitForConnection() {
        return new Promise((resolve) => {
            const checkConnection = () => {
                if (window.backend && typeof window.backend.generateUI === 'function') {
                    this.isConnected = true;
                    resolve();
                } else {
                    setTimeout(checkConnection, 100);
                }
            };
            checkConnection();
        });
    }
    
    /**
     * 根据上下文生成动态UI
     * @param {Object} context - 上下文数据
     * @returns {Object} UI Schema
     */
    async generateUI(context) {
        await this._ensureConnected();
        
        const contextJson = JSON.stringify(context);
        const result = await this._callMethod('generateUI', contextJson);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 处理前端事件
     * @param {string} eventType - 事件类型
     * @param {Object} payload - 事件数据
     * @returns {Object} 处理结果
     */
    async handleEvent(eventType, payload) {
        await this._ensureConnected();
        
        const payloadJson = JSON.stringify(payload);
        const result = await this._callMethod('handleEvent', eventType, payloadJson);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 获取进化指标
     * @param {string} userId - 用户ID
     * @returns {Object} 指标数据
     */
    async getEvolutionMetrics(userId) {
        await this._ensureConnected();
        
        const result = await this._callMethod('getEvolutionMetrics', userId);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 记录用户行为
     * @param {string} userId - 用户ID
     * @param {Object} behavior - 行为数据
     * @returns {Object} 结果
     */
    async recordBehavior(userId, behavior) {
        await this._ensureConnected();
        
        const behaviorJson = JSON.stringify(behavior);
        const result = await this._callMethod('recordBehavior', userId, behaviorJson);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 推荐组件
     * @param {string} userId - 用户ID
     * @param {Object} context - 上下文数据
     * @returns {Array} 组件ID列表
     */
    async recommendComponents(userId, context) {
        await this._ensureConnected();
        
        const contextJson = JSON.stringify(context);
        const result = await this._callMethod('recommendComponents', userId, contextJson);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 个性化UI
     * @param {string} userId - 用户ID
     * @param {Object} uiSchema - UI Schema
     * @returns {Object} 个性化后的Schema
     */
    async personalizeUI(userId, uiSchema) {
        await this._ensureConnected();
        
        const uiSchemaJson = JSON.stringify(uiSchema);
        const result = await this._callMethod('personalizeUI', userId, uiSchemaJson);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 获取学习统计
     * @param {string} userId - 用户ID
     * @returns {Object} 统计数据
     */
    async getLearningStats(userId) {
        await this._ensureConnected();
        
        const result = await this._callMethod('getLearningStats', userId);
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 获取默认上下文
     * @returns {Object} 默认上下文
     */
    async getDefaultContext() {
        await this._ensureConnected();
        
        const result = await this._callMethod('getDefaultContext');
        
        try {
            return JSON.parse(result);
        } catch {
            return result;
        }
    }
    
    /**
     * 调用后端方法
     * @param {string} methodName - 方法名
     * @param  {...any} args - 参数
     * @returns {any} 返回值
     */
    async _callMethod(methodName, ...args) {
        return new Promise((resolve, reject) => {
            try {
                const method = this.backend[methodName];
                
                if (typeof method === 'function') {
                    // Qt WebChannel 方法支持回调
                    const callback = (result) => {
                        resolve(result);
                    };
                    
                    // 尝试调用方法
                    const result = method(...args, callback);
                    
                    // 如果方法同步返回值，直接使用
                    if (result !== undefined) {
                        resolve(result);
                    }
                } else {
                    reject(new Error(`方法不存在: ${methodName}`));
                }
            } catch (error) {
                reject(error);
            }
        });
    }
    
    /**
     * 确保已连接
     */
    async _ensureConnected() {
        if (!this.isConnected) {
            await this._waitForConnection();
        }
    }
}

// 创建单例
export const backendClient = new BackendClient();

// 备用实现：当Qt WebChannel不可用时使用模拟数据
export const mockBackendClient = {
    async generateUI(context) {
        console.log('模拟生成UI:', context);
        
        const text = context.text || '';
        
        if (text.includes('上传') || text.includes('文件')) {
            return {
                id: 'upload_layout',
                type: 'vertical',
                components: [
                    { id: 'title', type: 'heading', category: 'display', label: '上传文件' },
                    { id: 'desc', type: 'text', category: 'display', value: '请上传环评相关文件' },
                    { id: 'upload', type: 'file_upload', category: 'input', label: '选择文件' }
                ]
            };
        }
        
        return {
            id: 'default_layout',
            type: 'vertical',
            components: [
                { id: 'title', type: 'heading', category: 'display', label: '环评智能工作台' },
                { id: 'desc', type: 'text', category: 'display', value: '请描述您的需求...' },
                { id: 'input', type: 'text_input', category: 'input', label: '输入需求', placeholder: '例如：开发用户登录功能' }
            ]
        };
    },
    
    async handleEvent(eventType, payload) {
        console.log('模拟处理事件:', eventType, payload);
        return { success: true };
    },
    
    async getEvolutionMetrics(userId) {
        return {
            compliance_score: 75,
            efficiency_score: 68,
            quality_score: 82,
            pattern_count: 5,
            total_interactions: 23,
            average_reward: 0.35,
            evolution_stage: 'pattern_discovery'
        };
    },
    
    async recordBehavior(userId, behavior) {
        console.log('模拟记录行为:', userId, behavior);
        return { success: true };
    },
    
    async recommendComponents(userId, context) {
        return ['button', 'text_input', 'card'];
    },
    
    async personalizeUI(userId, uiSchema) {
        return uiSchema;
    },
    
    async getLearningStats(userId) {
        return {
            total_learning_cycles: 10,
            patterns_discovered: 8,
            strategies_updated: 12,
            last_learning_time: new Date().toISOString()
        };
    },
    
    async getDefaultContext() {
        return {
            user_id: 'default_user',
            session_id: 'test_session',
            timestamp: Date.now()
        };
    }
};

// 根据环境选择使用真实后端还是模拟后端
export const useBackend = window.backend ? backendClient : mockBackendClient;