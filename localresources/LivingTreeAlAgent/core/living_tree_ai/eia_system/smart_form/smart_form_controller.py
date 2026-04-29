"""
智能表单 - 主控制器
整合文档解析、表单生成、数据同步的完整工作流

核心理念：从"填表"到"核验"
业主上传文档 → AI解析 → 提取关键信息 → 生成预填表单 → 业主核对修改
"""

import asyncio
import json
import hashlib
import base64
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
from pathlib import Path

# 导入子模块
from .document_form_extractor import (
    DocumentFormExtractor,
    DocumentType,
    ExtractionResult,
    get_extractor,
    extract_form_data_async,
)
from .wysiwyg_form_generator import (
    WYSIWYGFormGenerator,
    generate_form_html,
    get_generator,
)
from .dynamic_form_generator import (
    DynamicFormGenerator,
    FormValidationEngine,
    get_dynamic_generator,
    generate_dynamic_form_async,
)
from .form_data_synchronizer import (
    FormDataSynchronizer,
    FormChangeTracker,
    DataSource,
    get_synchronizer,
    get_tracker,
    save_form_data_async,
    load_form_data_async,
)


# ==================== 数据模型 ====================

class SmartFormMode(Enum):
    """智能表单模式"""
    EXTRACT = "extract"           # 文档提取模式
    DYNAMIC = "dynamic"           # 动态生成模式
    HYBRID = "hybrid"             # 混合模式（提取+动态）


class FormStatus(Enum):
    """表单状态"""
    DRAFT = "draft"               # 草稿
    EXTRACTING = "extracting"    # 提取中
    REVIEWING = "reviewing"      # 审核中
    SUBMITTED = "submitted"       # 已提交
    APPROVED = "approved"         # 已批准
    REJECTED = "rejected"         # 已拒绝


@dataclass
class SmartFormSession:
    """智能表单会话"""
    session_id: str
    project_id: str
    form_id: str
    mode: SmartFormMode
    status: FormStatus
    template_name: str
    extraction_result: Optional[ExtractionResult] = None
    form_data: Dict = field(default_factory=dict)
    form_html: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class SmartFormConfig:
    """智能表单配置"""
    mode: SmartFormMode = SmartFormMode.EXTRACT
    auto_save: bool = True
    auto_save_interval: int = 30  # 秒
    enable_validation: bool = True
    enable_cross_reference: bool = True
    template_name: str = "eia_basic"
    websocket_url: str = "ws://localhost:8765/form/assist"
    api_base_url: str = "http://localhost:5000/api"


# ==================== 智能表单控制器 ====================

class SmartFormController:
    """
    智能表单主控制器

    整合所有智能表单组件，提供端到端的工作流
    """

    def __init__(self, config: SmartFormConfig = None):
        """
        Args:
            config: 配置
        """
        self.config = config or SmartFormConfig()

        # 初始化子模块
        self.extractor = get_extractor()
        self.generator = get_generator()
        self.dynamic_generator = get_dynamic_generator()
        self.synchronizer = get_synchronizer()
        self.tracker = get_tracker()

        # 会话管理
        self._sessions: Dict[str, SmartFormSession] = {}

    # ==================== 工作流方法 ====================

    async def create_session(
        self,
        project_id: str,
        mode: SmartFormMode = None,
        template_name: str = None
    ) -> SmartFormSession:
        """
        创建新的表单会话

        Args:
            project_id: 项目ID
            mode: 表单模式
            template_name: 模板名称

        Returns:
            SmartFormSession: 表单会话
        """
        mode = mode or self.config.mode
        template_name = template_name or self.config.template_name

        session_id = self._generate_session_id(project_id)
        form_id = f"form_{hashlib.md5(session_id.encode()).hexdigest()[:12]}"

        session = SmartFormSession(
            session_id=session_id,
            project_id=project_id,
            form_id=form_id,
            mode=mode,
            status=FormStatus.DRAFT,
            template_name=template_name
        )

        self._sessions[session_id] = session

        return session

    async def process_document(
        self,
        session_id: str,
        file_data: bytes,
        filename: str
    ) -> SmartFormSession:
        """
        处理上传的文档，提取数据并生成表单

        Args:
            session_id: 会话ID
            file_data: 文件数据
            filename: 文件名

        Returns:
            SmartFormSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        session.status = FormStatus.EXTRACTING

        try:
            # 1. 获取模板
            template = self.extractor.get_template(session.template_name)
            if not template:
                template = self.extractor.get_template("eia_basic")

            # 2. 提取数据
            extraction_result = await self.extractor.extract_form_data(
                file_data, filename, template
            )
            session.extraction_result = extraction_result

            # 3. 构建提取数据字典
            extracted_data = {
                name: field.value
                for name, field in extraction_result.extracted_fields.items()
            }
            session.form_data = extracted_data

            # 4. 生成表单HTML
            form_html = self.generator.generate_form(
                extraction_result,
                template,
                options={
                    "form_id": session.form_id,
                    "websocket_url": self.config.websocket_url,
                    "api_base_url": self.config.api_base_url
                }
            )
            session.form_html = form_html

            session.status = FormStatus.REVIEWING

        except Exception as e:
            session.status = FormStatus.DRAFT
            raise e

        session.updated_at = datetime.now()
        return session

    async def generate_dynamic_form(
        self,
        session_id: str,
        project_type: str,
        industry: str,
        region: str
    ) -> SmartFormSession:
        """
        动态生成表单

        Args:
            session_id: 会话ID
            project_type: 项目类型
            industry: 行业类别
            region: 地区

        Returns:
            SmartFormSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 1. 动态生成模板
        dynamic_template = await self.dynamic_generator.generate_form_for_project(
            project_type, industry, region
        )

        # 2. 生成空表单HTML
        template_dict = self.dynamic_generator._template_to_dict(dynamic_template)

        # 3. 创建空的ExtractionResult用于生成器
        from .document_form_extractor import ExtractedField
        empty_extracted = {
            f["name"]: ExtractedField(
                name=f["name"],
                value="",
                confidence=0.0
            )
            for f in template_dict["fields"]
        }

        from .document_form_extractor import ExtractionResult as ER
        fake_result = ER(
            doc_type=DocumentType.UNKNOWN,
            file_hash="",
            filename="dynamic_form",
            extracted_fields=empty_extracted,
            validation_results={},
            overall_confidence=0.0
        )

        # 4. 生成表单HTML
        template_for_generator = {
            "name": dynamic_template.name,
            "label": dynamic_template.label,
            "fields": [
                {
                    "name": f.name,
                    "label": f.label,
                    "type": f.field_type,
                    "required": f.required,
                    "category": f.category,
                    "options": f.options,
                    "min": f.min_value,
                    "max": f.max_value,
                    "placeholder": f.placeholder,
                    "help_text": f.help_text,
                    "unit": f.unit,
                }
                for f in dynamic_template.fields
            ],
            "sections": dynamic_template.sections
        }

        form_html = self.generator.generate_form(
            fake_result,
            template_for_generator,
            options={
                "form_id": session.form_id,
                "websocket_url": self.config.websocket_url,
                "api_base_url": self.config.api_base_url
            }
        )

        session.extraction_result = fake_result
        session.template_name = dynamic_template.name
        session.status = FormStatus.REVIEWING
        session.updated_at = datetime.now()

        return session

    async def update_field(
        self,
        session_id: str,
        field_name: str,
        new_value: Any
    ) -> SmartFormSession:
        """
        更新字段值

        Args:
            session_id: 会话ID
            field_name: 字段名
            new_value: 新值

        Returns:
            SmartFormSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 记录变更
        old_value = session.form_data.get(field_name)
        self.tracker.track_change(
            session.form_id,
            field_name,
            old_value,
            new_value
        )

        # 更新数据
        session.form_data[field_name] = new_value
        session.updated_at = datetime.now()

        return session

    async def validate_form(self, session_id: str) -> Dict:
        """
        验证表单

        Args:
            session_id: 会话ID

        Returns:
            Dict: 验证结果
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        template = self.extractor.get_template(session.template_name)
        if not template:
            return {"valid": False, "error": "模板不存在"}

        return FormValidationEngine.validate_form(
            session.form_data,
            template
        )

    async def submit_form(self, session_id: str) -> SmartFormSession:
        """
        提交表单

        Args:
            session_id: 会话ID

        Returns:
            SmartFormSession: 更新后的会话
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 验证
        validation = await self.validate_form(session_id)
        if not validation["valid"]:
            raise ValueError(
                f"表单验证失败: {validation.get('error_count', 0)} 个错误"
            )

        # 保存到P2P网络
        await self.synchronizer.save_form_data(
            session.project_id,
            session.form_id,
            session.form_data,
            DataSource.OWNER_INPUT
        )

        session.status = FormStatus.SUBMITTED
        session.updated_at = datetime.now()

        return session

    async def get_form_html(self, session_id: str) -> str:
        """
        获取表单HTML

        Args:
            session_id: 会话ID

        Returns:
            str: 表单HTML
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        return session.form_html

    async def get_session(self, session_id: str) -> Optional[SmartFormSession]:
        """获取会话"""
        return self._sessions.get(session_id)

    def get_all_sessions(self, project_id: str = None) -> List[SmartFormSession]:
        """获取所有会话"""
        sessions = list(self._sessions.values())
        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]
        return sessions

    def _generate_session_id(self, project_id: str) -> str:
        """生成会话ID"""
        timestamp = datetime.now().isoformat()
        raw = f"{project_id}_{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ==================== Flask API 集成 ====================

class SmartFormAPI:
    """Flask API 服务器（用于前端通信）"""

    def __init__(self, controller: SmartFormController):
        self.controller = controller

    def create_routes(self, app):
        """创建Flask路由"""

        from flask import Flask, request, jsonify, render_template_string

        @app.route('/api/form/create', methods=['POST'])
        async def create_form():
            """创建表单会话"""
            data = request.json
            session = await self.controller.create_session(
                project_id=data['project_id'],
                mode=SmartFormMode(data.get('mode', 'extract')),
                template_name=data.get('template_name')
            )
            return jsonify({
                'session_id': session.session_id,
                'form_id': session.form_id
            })

        @app.route('/api/form/<session_id>/upload', methods=['POST'])
        async def upload_document(session_id):
            """上传文档"""
            if 'file' not in request.files:
                return jsonify({'error': '没有文件'}), 400

            file = request.files['file']
            file_data = file.read()
            filename = file.filename

            session = await self.controller.process_document(
                session_id, file_data, filename
            )

            return jsonify({
                'session_id': session.session_id,
                'form_id': session.form_id,
                'confidence': session.extraction_result.overall_confidence,
                'doc_type': session.extraction_result.doc_type.value,
                'fields_extracted': len(session.extraction_result.extracted_fields)
            })

        @app.route('/api/form/<session_id>/dynamic', methods=['POST'])
        async def create_dynamic_form(session_id):
            """创建动态表单"""
            data = request.json

            session = await self.controller.generate_dynamic_form(
                session_id,
                project_type=data['project_type'],
                industry=data['industry'],
                region=data['region']
            )

            return jsonify({
                'session_id': session.session_id,
                'template': session.template_name,
                'fields_count': len(session.extraction_result.extracted_fields)
            })

        @app.route('/api/form/<session_id>/field', methods=['PUT'])
        async def update_field(session_id):
            """更新字段"""
            data = request.json

            session = await self.controller.update_field(
                session_id,
                field_name=data['field'],
                new_value=data['value']
            )

            return jsonify({'success': True})

        @app.route('/api/form/<session_id>/validate', methods=['POST'])
        async def validate_form(session_id):
            """验证表单"""
            validation = await self.controller.validate_form(session_id)
            return jsonify(validation)

        @app.route('/api/form/<session_id>/submit', methods=['POST'])
        async def submit_form(session_id):
            """提交表单"""
            try:
                session = await self.controller.submit_form(session_id)
                return jsonify({
                    'success': True,
                    'status': session.status.value
                })
            except ValueError as e:
                return jsonify({'error': str(e)}), 400

        @app.route('/api/form/<session_id>/html', methods=['GET'])
        async def get_form_html(session_id):
            """获取表单HTML"""
            html = await self.controller.get_form_html(session_id)
            return jsonify({'html': html})

        @app.route('/api/form/<session_id>/history', methods=['GET'])
        async def get_change_history(session_id):
            """获取变更历史"""
            session = await self.controller.get_session(session_id)
            if not session:
                return jsonify({'error': '会话不存在'}), 404

            tracker = get_tracker()
            history = tracker.get_changes(session.form_id)

            return jsonify({'changes': history})

        return app


# ==================== WebSocket 处理器 ====================

class SmartFormWebSocket:
    """WebSocket 处理器"""

    def __init__(self, controller: SmartFormController):
        self.controller = controller
        self.clients: Dict[str, Any] = {}

    async def handle_message(self, websocket, path):
        """处理WebSocket消息"""
        client_id = str(id(websocket))
        self.clients[client_id] = websocket

        try:
            async for message in websocket:
                data = json.loads(message)
                response = await self.process_message(data)
                await websocket.send(json.dumps(response))

        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            del self.clients[client_id]

    async def process_message(self, data: Dict) -> Dict:
        """处理消息"""
        msg_type = data.get('type')

        if msg_type == 'validate_field':
            # 验证字段
            session_id = data.get('session_id')
            field = data.get('field')
            value = data.get('value')

            # 简化验证
            is_valid = bool(value)
            return {
                'type': 'validation_result',
                'field': field,
                'result': {
                    'status': 'success' if is_valid else 'error',
                    'message': '验证通过' if is_valid else '字段不能为空'
                }
            }

        elif msg_type == 'autofill':
            # 自动填充
            session_id = data.get('session_id')
            fields = data.get('fields', [])

            return {
                'type': 'autofill',
                'fields': fields
            }

        return {'type': 'unknown', 'message': '未知消息类型'}


# ==================== 导出函数 ====================

_controller_instance: Optional[SmartFormController] = None


def get_smart_form_controller() -> SmartFormController:
    """获取智能表单控制器单例"""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = SmartFormController()
    return _controller_instance


async def create_form_session(
    project_id: str,
    mode: str = "extract",
    template_name: str = None
) -> SmartFormSession:
    """创建表单会话的便捷函数"""
    controller = get_smart_form_controller()
    return await controller.create_session(
        project_id,
        SmartFormMode(mode),
        template_name
    )


async def process_uploaded_document(
    session_id: str,
    file_data: bytes,
    filename: str
) -> SmartFormSession:
    """处理上传文档的便捷函数"""
    controller = get_smart_form_controller()
    return await controller.process_document(session_id, file_data, filename)


async def submit_form_data(session_id: str) -> SmartFormSession:
    """提交表单的便捷函数"""
    controller = get_smart_form_controller()
    return await controller.submit_form(session_id)
