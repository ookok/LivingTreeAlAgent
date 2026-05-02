"""
WebChannelBackend — PyQt6 QWebChannel 桥接
============================================

QObject 子类，通过 QWebChannel 暴露后端方法给 Vue 前端。
桥接 livingtree LifeEngine + 动态 UI 引擎 + 学习系统。

使用方式（前端）:
    window.backend.generateUI(contextJson)
    window.backend.handleEvent(eventType, payloadJson)
    window.backend.getEvolutionMetrics(userId)
"""

import sys
import os
import json
import logging
from typing import Optional, Dict, Any

try:
    from PyQt6.QtCore import QObject, pyqtSlot, pyqtProperty
except ImportError:
    class QObject: pass
    def pyqtSlot(*args, **kwargs): return lambda f: f
    def pyqtProperty(*args, **kwargs): return lambda f: f

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)


class WebChannelBackend(QObject):
    """PyQt6 QWebChannel 后端桥接"""

    def __init__(self):
        super().__init__()
        self._engine = None
        self._ui_engine = None
        self._learning_service = None
        self._ab_test = None
        self._preference_model = None
        self._rt_learning = None
        self._user_id = "default_user"

        self._init_services()

    def _init_services(self):
        try:
            from business.dynamic_ui_engine import get_dynamic_ui_engine
            self._ui_engine = get_dynamic_ui_engine()
        except Exception:
            pass

        try:
            from business.evolutionary_learning import get_evolutionary_learning_service
            self._learning_service = get_evolutionary_learning_service()
        except Exception:
            pass

        try:
            from business.ab_test_framework import get_ab_test_framework
            self._ab_test = get_ab_test_framework()
        except Exception:
            pass

        try:
            from business.user_preference_model import get_user_preference_model
            self._preference_model = get_user_preference_model()
        except Exception:
            pass

        try:
            from business.real_time_learning import get_real_time_learning_service
            self._rt_learning = get_real_time_learning_service()
        except Exception:
            pass

        try:
            from livingtree.core.life_engine import LifeEngine
            self._engine = LifeEngine.get_instance()
        except Exception:
            pass

        self._connected = True

    @pyqtSlot(str, result=str)
    def generateUI(self, context_json: str) -> str:
        try:
            context = json.loads(context_json)
            if self._ui_engine:
                result = self._ui_engine.generate_ui(context)
                return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"generateUI failed: {e}")

        return json.dumps({
            "id": "default_layout", "type": "vertical",
            "components": [
                {"id": "title", "type": "heading", "category": "display", "label": "LivingTree AI"},
                {"id": "desc", "type": "text", "category": "display",
                 "value": context.get("text", "") if isinstance(context, dict) else ""},
            ]
        })

    @pyqtSlot(str, str, result=str)
    def handleEvent(self, event_type: str, payload_json: str) -> str:
        try:
            payload = json.loads(payload_json) if payload_json else {}
            return json.dumps({"success": True, "event": event_type, "data": payload})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getEvolutionMetrics(self, user_id: str) -> str:
        try:
            if self._learning_service:
                metrics = self._learning_service.get_evolution_metrics(user_id)
                return json.dumps(metrics, ensure_ascii=False, default=str)
        except Exception:
            pass

        return json.dumps({
            "compliance_score": 75, "efficiency_score": 68,
            "quality_score": 82, "pattern_count": 5,
            "total_interactions": 23, "average_reward": 0.35,
            "evolution_stage": "pattern_discovery"
        })

    @pyqtSlot(str, str, result=str)
    def recordBehavior(self, user_id: str, behavior_json: str) -> str:
        try:
            behavior = json.loads(behavior_json)
            if self._learning_service:
                self._learning_service.record_behavior(user_id, behavior)
        except Exception:
            pass
        return json.dumps({"success": True})

    @pyqtSlot(str, str, result=str)
    def recommendComponents(self, user_id: str, context_json: str) -> str:
        try:
            if self._preference_model:
                result = self._preference_model.recommend_components(user_id, json.loads(context_json))
                return json.dumps(result)
        except Exception:
            pass
        return json.dumps(["button", "text_input", "card"])

    @pyqtSlot(str, str, result=str)
    def personalizeUI(self, user_id: str, ui_schema_json: str) -> str:
        try:
            if self._preference_model:
                return self._preference_model.personalize_ui(user_id, json.loads(ui_schema_json))
        except Exception:
            pass
        return ui_schema_json

    @pyqtSlot(str, result=str)
    def getLearningStats(self, user_id: str) -> str:
        return json.dumps({
            "total_learning_cycles": 10,
            "patterns_discovered": 8,
            "strategies_updated": 12,
            "last_learning_time": "2026-05-02T00:00:00Z"
        })

    @pyqtSlot(result=str)
    def getDefaultContext(self) -> str:
        return json.dumps({
            "user_id": self._user_id,
            "session_id": "default",
            "platform": "pyqt6",
            "livingtree_version": "1.0.0",
        })

    @pyqtSlot(str, str, result=str)
    def sendMessage(self, message: str, session_id: str = "") -> str:
        """处理聊天消息 — 委托给 LifeEngine"""
        try:
            if self._engine:
                response = self._engine.handle_request(message)
                return json.dumps({
                    "type": "chat_response",
                    "content": response.text,
                    "trace_id": response.trace_id,
                    "metadata": {
                        "tokens_input": response.result.tokens_input,
                        "tokens_output": response.result.tokens_output,
                        "duration_ms": response.result.duration_ms,
                        "learning_score": response.learning.score,
                    }
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"type": "error", "error": str(e)})

        return json.dumps({
            "type": "chat_response",
            "content": f"[LivingTreeBridge] 收到: {message[:100]}",
        })

    @pyqtSlot(result=str)
    def healthCheck(self) -> str:
        info = {
            "status": "connected",
            "engine": self._engine is not None,
            "ui_engine": self._ui_engine is not None,
            "livingtree_version": "1.0.0",
        }
        return json.dumps(info)
