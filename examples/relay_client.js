/**
 * WebSocket 中继客户端 JavaScript SDK
 * WebSocket Relay Client JavaScript SDK
 * 
 * 用于网页端和移动端(Hybrid App)连接中继服务器
 * 
 * 使用示例:
 * 
 * // 创建客户端
 * const client = new RelayClient('ws://localhost:8765', {
 *     clientName: 'Web User',
 *     clientType: 'web'
 * });
 * 
 * // 连接
 * await client.connect();
 * 
 * // 创建会话
 * await client.createSession({ name: 'My Session' });
 * 
 * // 发送消息
 * client.broadcast({ text: 'Hello everyone!' });
 */

// 消息类型常量
const MessageType = {
    PING: 'ping',
    PONG: 'pong',
    REGISTER: 'register',
    REGISTERED: 'registered',
    CREATE_SESSION: 'create_session',
    SESSION_CREATED: 'session_created',
    JOIN_SESSION: 'join_session',
    SESSION_JOINED: 'session_joined',
    LEAVE_SESSION: 'leave_session',
    SESSION_LEFT: 'session_left',
    RELAY_MESSAGE: 'relay_message',
    ERROR: 'error',
    NOTIFICATION: 'notification'
};

// 连接状态
const ConnectionState = {
    DISCONNECTED: 'disconnected',
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    AUTHENTICATED: 'authenticated',
    ERROR: 'error'
};

/**
 * 中继客户端类
 */
class RelayClient {
    /**
     * 构造函数
     * @param {string} serverUrl - 服务器地址
     * @param {Object} options - 配置选项
     */
    constructor(serverUrl, options = {}) {
        this.serverUrl = serverUrl;
        this.clientName = options.clientName || 'Web User';
        this.clientType = options.clientType || 'web';
        this.autoReconnect = options.autoReconnect !== false;
        this.reconnectInterval = options.reconnectInterval || 5000;
        this.pingInterval = options.pingInterval || 30000;
        
        // 内部状态
        this.ws = null;
        this.state = ConnectionState.DISCONNECTED;
        this.clientId = null;
        this.currentSession = null;
        this.sessionMembers = [];
        
        // 定时器
        this.reconnectTimer = null;
        this.pingTimer = null;
        
        // 回调函数
        this.onConnected = null;
        this.onDisconnected = null;
        this.onMessage = null;
        this.onSessionCreated = null;
        this.onSessionJoined = null;
        this.onSessionLeft = null;
        this.onError = null;
        this.onNotification = null;
    }

    /**
     * 创建JSON消息
     */
    createMessage(type, data, extra = {}) {
        const msg = {
            type,
            id: extra.id || this._generateId(),
            timestamp: Date.now(),
            data
        };
        
        if (extra.to) msg.to = extra.to;
        if (extra.session) msg.session = extra.session;
        
        return JSON.stringify(msg);
    }

    /**
     * 解析JSON消息
     */
    parseMessage(raw) {
        try {
            return JSON.parse(raw);
        } catch (e) {
            console.error('Failed to parse message:', e);
            return null;
        }
    }

    /**
     * 生成唯一ID
     */
    _generateId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    /**
     * 连接到服务器
     */
    async connect() {
        return new Promise((resolve, reject) => {
            if (this.ws) {
                this.disconnect();
            }
            
            this.state = ConnectionState.CONNECTING;
            
            try {
                this.ws = new WebSocket(this.serverUrl);
                
                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.state = ConnectionState.CONNECTED;
                    
                    // 发送注册消息
                    this._send(MessageType.REGISTER, {
                        name: this.clientName,
                        client_type: this.clientType
                    });
                };
                
                this.ws.onmessage = (event) => {
                    this._handleMessage(event.data);
                };
                
                this.ws.onclose = () => {
                    console.log('WebSocket closed');
                    this._setState(ConnectionState.DISCONNECTED);
                    this._stopPing();
                    
                    if (this.onDisconnected) {
                        this.onDisconnected();
                    }
                    
                    // 自动重连
                    if (this.autoReconnect && this.state !== ConnectionState.DISCONNECTED) {
                        this._scheduleReconnect();
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this._setState(ConnectionState.ERROR);
                    reject(error);
                };
                
                // 等待连接超时
                setTimeout(() => {
                    if (this.state !== ConnectionState.AUTHENTICATED) {
                        reject(new Error('Connection timeout'));
                    }
                }, 10000);
                
            } catch (error) {
                this._setState(ConnectionState.ERROR);
                reject(error);
            }
        });
    }

    /**
     * 断开连接
     */
    disconnect() {
        this._stopReconnect();
        this._stopPing();
        
        if (this.ws) {
            this._send(MessageType.UNREGISTER, {});
            this.ws.close();
            this.ws = null;
        }
        
        this._setState(ConnectionState.DISCONNECTED);
        this.currentSession = null;
        this.sessionMembers = [];
    }

    /**
     * 发送消息
     */
    _send(type, data, extra = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket not connected');
            return false;
        }
        
        const msg = this.createMessage(type, data, extra);
        this.ws.send(msg);
        return true;
    }

    /**
     * 处理接收到的消息
     */
    _handleMessage(raw) {
        const msg = this.parseMessage(raw);
        if (!msg) return;
        
        const { type, data } = msg;
        
        switch (type) {
            case MessageType.PONG:
                // 心跳响应
                break;
                
            case MessageType.REGISTERED:
                this.clientId = data.client_id;
                this._setState(ConnectionState.AUTHENTICATED);
                this._startPing();
                
                if (this.onConnected) {
                    this.onConnected(data);
                }
                break;
                
            case MessageType.SESSION_CREATED:
                this.currentSession = data.session_id;
                
                if (this.onSessionCreated) {
                    this.onSessionCreated(data);
                }
                break;
                
            case MessageType.SESSION_JOINED:
                this.currentSession = data.session_id;
                this.sessionMembers = data.members || [];
                
                if (this.onSessionJoined) {
                    this.onSessionJoined(data);
                }
                break;
                
            case MessageType.SESSION_LEFT:
                this.currentSession = null;
                this.sessionMembers = [];
                
                if (this.onSessionLeft) {
                    this.onSessionLeft(data);
                }
                break;
                
            case MessageType.RELAY_MESSAGE:
                if (this.onMessage) {
                    this.onMessage(data);
                }
                break;
                
            case MessageType.ERROR:
                console.error('Server error:', data);
                
                if (this.onError) {
                    this.onError(data);
                }
                break;
                
            case MessageType.NOTIFICATION:
                if (this.onNotification) {
                    this.onNotification(data);
                }
                break;
        }
    }

    /**
     * 创建会话
     */
    createSession(options = {}) {
        return this._send(MessageType.CREATE_SESSION, {
            name: options.name || '',
            password: options.password || '',
            max_clients: options.maxClients || 10
        });
    }

    /**
     * 加入会话
     */
    joinSession(sessionId, password = '') {
        return this._send(MessageType.JOIN_SESSION, {
            session_id: sessionId,
            password: password
        });
    }

    /**
     * 离开会话
     */
    leaveSession(sessionId = null) {
        return this._send(MessageType.LEAVE_SESSION, {
            session_id: sessionId || this.currentSession
        });
    }

    /**
     * 发送消息到会话
     */
    broadcast(data) {
        if (!this.currentSession) {
            console.warn('Not in a session');
            return false;
        }
        
        return this._send(MessageType.RELAY_MESSAGE, { data }, {
            session: this.currentSession
        });
    }

    /**
     * 发送点对点消息
     */
    sendTo(toId, data) {
        return this._send(MessageType.RELAY_MESSAGE, { data, to: toId });
    }

    /**
     * 设置连接状态
     */
    _setState(state) {
        this.state = state;
    }

    /**
     * 启动心跳
     */
    _startPing() {
        this._stopPing();
        this.pingTimer = setInterval(() => {
            this._send(MessageType.PING, {});
        }, this.pingInterval);
    }

    /**
     * 停止心跳
     */
    _stopPing() {
        if (this.pingTimer) {
            clearInterval(this.pingTimer);
            this.pingTimer = null;
        }
    }

    /**
     * 安排重连
     */
    _scheduleReconnect() {
        this._stopReconnect();
        console.log(`Reconnecting in ${this.reconnectInterval / 1000}s...`);
        
        this.reconnectTimer = setTimeout(async () => {
            try {
                await this.connect();
            } catch (e) {
                console.error('Reconnect failed:', e);
            }
        }, this.reconnectInterval);
    }

    /**
     * 停止重连
     */
    _stopReconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RelayClient, MessageType, ConnectionState };
}
