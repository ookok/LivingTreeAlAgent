"""
状态管理器 - State Manager

功能：
1. Redux风格状态管理
2. 单向数据流
3. 状态订阅
4. 中间件支持
"""

import logging
from typing import Dict, Any, Callable, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Action:
    """动作封装"""
    type: str
    payload: Any = None


class Reducer:
    """Reducer基类"""
    def reduce(self, state: Any, action: Action) -> Any:
        """处理动作并返回新状态"""
        return state


class Middleware:
    """中间件基类"""
    def process(self, store: 'Store', action: Action, next_fn: Callable):
        """处理动作"""
        next_fn(action)


class Store:
    """
    状态管理器 - Redux风格
    
    核心特性：
    1. 单一状态源
    2. 只读状态
    3. 纯函数修改
    4. 中间件支持
    """
    
    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._reducers: Dict[str, Reducer] = {}
        self._middlewares: List[Middleware] = []
        self._subscribers: List[Callable] = []
    
    def register_reducer(self, key: str, reducer: Reducer):
        """注册Reducer"""
        self._reducers[key] = reducer
        if key not in self._state:
            self._state[key] = {}
    
    def register_middleware(self, middleware: Middleware):
        """注册中间件"""
        self._middlewares.append(middleware)
    
    def dispatch(self, action: Action):
        """分发动作"""
        # 通过中间件处理
        chain = self._build_middleware_chain()
        chain(action)
    
    def _build_middleware_chain(self) -> Callable:
        """构建中间件链"""
        def apply_middleware(middleware: Middleware, next_fn: Callable) -> Callable:
            def wrapped(action: Action):
                middleware.process(self, action, next_fn)
            return wrapped
        
        # 从后往前构建链
        chain = self._reduce
        for middleware in reversed(self._middlewares):
            chain = apply_middleware(middleware, chain)
        
        return chain
    
    def _reduce(self, action: Action):
        """执行状态更新"""
        new_state = {}
        
        for key, reducer in self._reducers.items():
            new_state[key] = reducer.reduce(self._state.get(key), action)
        
        self._state = new_state
        self._notify()
    
    def _notify(self):
        """通知订阅者"""
        for subscriber in self._subscribers:
            try:
                subscriber(self._state.copy())
            except Exception as e:
                logger.error(f"订阅者回调失败: {e}")
    
    def subscribe(self, subscriber: Callable[[Dict], None]):
        """订阅状态变化"""
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)
    
    def unsubscribe(self, subscriber: Callable[[Dict], None]):
        """取消订阅"""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态（只读副本）"""
        return self._state.copy()
    
    def get_state_by_key(self, key: str) -> Any:
        """获取指定key的状态"""
        return self._state.get(key)
    
    def reset(self):
        """重置状态"""
        self._state = {key: {} for key in self._reducers.keys()}
        self._notify()


class LoggerMiddleware(Middleware):
    """日志中间件"""
    def process(self, store: Store, action: Action, next_fn: Callable):
        logger.debug(f"Action: {action.type}")
        next_fn(action)


class ThunkMiddleware(Middleware):
    """Thunk中间件 - 支持异步动作"""
    def process(self, store: Store, action: Action, next_fn: Callable):
        if callable(action.payload):
            # 如果payload是函数，执行它
            action.payload(store.dispatch)
        else:
            next_fn(action)


class AppReducer(Reducer):
    """应用状态Reducer"""
    def reduce(self, state: Dict, action: Action) -> Dict:
        new_state = state.copy()
        
        if action.type == 'SET_ACTIVE_TAB':
            new_state['active_tab'] = action.payload
        elif action.type == 'SET_SYSTEM_STATUS':
            new_state['system_status'] = action.payload
        elif action.type == 'SET_METRICS':
            new_state['metrics'] = action.payload
        
        return new_state


class WindowReducer(Reducer):
    """窗口状态Reducer"""
    def reduce(self, state: Dict, action: Action) -> Dict:
        new_state = state.copy()
        
        if action.type == 'SET_WINDOW_SIZE':
            new_state['size'] = action.payload
        elif action.type == 'SET_WINDOW_POSITION':
            new_state['position'] = action.payload
        elif action.type == 'SET_WINDOW_STATE':
            new_state['state'] = action.payload
        
        return new_state


# 全局Store实例
_store_instance = None

def get_store() -> Store:
    """获取全局状态管理器"""
    global _store_instance
    
    if _store_instance is None:
        _store_instance = Store()
        
        # 注册默认Reducers
        _store_instance.register_reducer('app', AppReducer())
        _store_instance.register_reducer('window', WindowReducer())
        
        # 注册默认中间件
        _store_instance.register_middleware(LoggerMiddleware())
        _store_instance.register_middleware(ThunkMiddleware())
    
    return _store_instance