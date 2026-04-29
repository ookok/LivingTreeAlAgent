# adapter_wrapper.py — 择优替换适配器封装系统

import os
import re
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json


logger = logging.getLogger(__name__)


# ============ 适配器模板库 ============

ADAPTER_TEMPLATES = {
    "pdf_parser": '''
class {{class_name}}Adapter:
    """
    PDF解析器适配器
    封装 {{library_name}} ({{version}})
    保持与原接口兼容
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._instance = None
        self._init_library()

    def _init_library(self):
        """初始化库实例"""
        try:
            import {{import_name}}
            self._instance = {{import_name}}.{{init_method}}(**self._config)
        except ImportError:
            raise ImportError(
                "请安装: pip install {{install_name}}\\n"
                "或运行: hermes --install {{library_name}}"
            )

    # === 原有接口 (保持不变) ===
    def extract_text(self, path: str, **kwargs) -> str:
        """提取PDF文本"""
        return self._instance.extract_text(path, **kwargs)

    def extract_metadata(self, path: str) -> dict:
        """提取元数据"""
        return self._instance.get_metadata(path)

    def extract_images(self, path: str) -> List[bytes]:
        """提取图片"""
        return self._instance.extract_images(path)

    # === 扩展接口 (可选) ===
    def extract_pages(self, path: str) -> List[str]:
        """按页提取"""
        return self._instance.extract_pages(path)

    def is_encrypted(self, path: str) -> bool:
        """检查是否加密"""
        return self._instance.is_encrypted(path)
''',

    "markdown_parser": '''
class {{class_name}}Adapter:
    """
    Markdown解析器适配器
    封装 {{library_name}} ({{version}})
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._md = None
        self._init_library()

    def _init_library(self):
        """初始化库实例"""
        try:
            import {{import_name}}
            self._md = {{import_name}}.{{init_method}}(**self._config)
        except ImportError:
            raise ImportError("请安装: pip install {{install_name}}")

    def parse(self, text: str) -> Any:
        """解析Markdown"""
        return self._md.parse(text)

    def render(self, text: str) -> str:
        """渲染为HTML"""
        return self._md.render(text)

    def render_ast(self, text: str) -> Any:
        """渲染为AST"""
        return self._md.parse(text).to_ast()

    # === 原有接口兼容 ===
    def to_html(self, md_text: str) -> str:
        """Markdown转HTML"""
        return self.render(md_text)
''',

    "http_client": '''
class {{class_name}}Adapter:
    """
    HTTP客户端适配器
    封装 {{library_name}} ({{version}})
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._session = None
        self._init_library()

    def _init_library(self):
        """初始化库实例"""
        try:
            import {{import_name}}
            self._session = {{import_name}}.{{init_method}}(**self._config)
        except ImportError:
            raise ImportError("请安装: pip install {{install_name}}")

    async def get(self, url: str, **kwargs) -> Any:
        """GET请求"""
        return await self._session.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> Any:
        """POST请求"""
        return await self._session.post(url, **kwargs)

    async def close(self):
        """关闭会话"""
        await self._session.close()

    # === 原有接口兼容 ===
    async def request(self, method: str, url: str, **kwargs) -> Any:
        """通用请求"""
        return await getattr(self._session, method.lower())(url, **kwargs)
''',

    "json_schema": '''
class {{class_name}}Adapter:
    """
    JSON Schema验证器适配器
    封装 {{library_name}} ({{version}})
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._validator = None
        self._init_library()

    def _init_library(self):
        """初始化库实例"""
        try:
            import {{import_name}}
            self._validator = {{import_name}}.{{init_method}}(**self._config)
        except ImportError:
            raise ImportError("请安装: pip install {{install_name}}")

    def validate(self, data: Any, schema: dict) -> bool:
        """验证数据"""
        return self._validator.validate(data, schema)

    def is_valid(self, data: Any, schema: dict) -> bool:
        """检查是否有效"""
        try:
            self.validate(data, schema)
            return True
        except Exception:
            return False

    def iter_errors(self, data: Any, schema: dict):
        """迭代验证错误"""
        return self._validator.iter_errors(data, schema)
''',

    "yaml_parser": '''
class {{class_name}}Adapter:
    """
    YAML解析器适配器
    封装 {{library_name}} ({{version}})
    """

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._loader = None
        self._dumper = None
        self._init_library()

    def _init_library(self):
        """初始化库实例"""
        try:
            import {{import_name}}
            self._loader = {{import_name}}.Loader
            self._dumper = {{import_name}}.Dumper
        except ImportError:
            raise ImportError("请安装: pip install {{install_name}}")

    def load(self, stream) -> Any:
        """加载YAML"""
        return {{import_name}}.load(stream, Loader=self._loader)

    def dump(self, data: Any, stream=None) -> str:
        """导出YAML"""
        return {{import_name}}.dump(data, Dumper=self._dumper, stream=stream)

    # === 原有接口兼容 ===
    def parse(self, text: str) -> Any:
        """解析YAML文本"""
        return self.load(text)

    def stringify(self, data: Any) -> str:
        """将数据转为YAML字符串"""
        return self.dump(data)
''',
}


# ============ 适配器元数据 ============

@dataclass
class AdapterMetadata:
    """适配器元数据"""
    adapter_id: str
    class_name: str
    module_name: str
    library_name: str
    library_version: str
    import_name: str
    install_name: str
    init_method: str
    template_type: str
    original_module: str
    created_at: int
    file_path: Optional[str] = None
    status: str = "draft"  # draft/generated/installed/active
    test_status: str = "pending"  # pending/passing/failed


# ============ 适配器封装器 ============

class AdapterWrapper:
    """
    适配器封装器

    功能:
    1. 根据模板生成适配器代码
    2. 管理适配器生命周期
    3. 支持回滚和切换
    """

    def __init__(
        self,
        adapters_dir: Path = None,
        registry_file: Path = None,
    ):
        if adapters_dir is None:
            adapters_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "adapters"
        adapters_dir.mkdir(parents=True, exist_ok=True)
        self._adapters_dir = adapters_dir

        if registry_file is None:
            registry_file = adapters_dir / "registry.json"
        self._registry_file = registry_file

        self._registry: Dict[str, AdapterMetadata] = {}
        self._load_registry()

    def _load_registry(self):
        """加载注册表"""
        if self._registry_file.exists():
            try:
                data = json.loads(self._registry_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._registry[k] = AdapterMetadata(**v)
            except Exception:
                pass

    def _save_registry(self):
        """保存注册表"""
        try:
            data = {
                k: {
                    "adapter_id": v.adapter_id,
                    "class_name": v.class_name,
                    "module_name": v.module_name,
                    "library_name": v.library_name,
                    "library_version": v.library_version,
                    "import_name": v.import_name,
                    "install_name": v.install_name,
                    "init_method": v.init_method,
                    "template_type": v.template_type,
                    "original_module": v.original_module,
                    "created_at": v.created_at,
                    "file_path": v.file_path,
                    "status": v.status,
                    "test_status": v.test_status,
                }
                for k, v in self._registry.items()
            }
            self._registry_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _generate_id(self, module_name: str, library_name: str) -> str:
        """生成适配器ID"""
        raw = f"{module_name}:{library_name}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def _to_class_name(self, name: str) -> str:
        """将名称转换为类名"""
        words = re.split(r"[-_]", name)
        return "".join(w.capitalize() for w in words)

    def _to_import_name(self, library_name: str) -> str:
        """将库名转换为导入名"""
        return library_name.lower().replace("-", "_")

    def _detect_template_type(self, module_name: str) -> str:
        """检测模板类型"""
        module_lower = module_name.lower()

        if "pdf" in module_lower:
            return "pdf_parser"
        elif "markdown" in module_lower:
            return "markdown_parser"
        elif "http" in module_lower:
            return "http_client"
        elif "json" in module_lower and "schema" in module_lower:
            return "json_schema"
        elif "yaml" in module_lower:
            return "yaml_parser"
        else:
            return "generic"

    def _generate_generic_template(self, library_name: str, class_name: str) -> str:
        """生成通用模板"""
        return f'''
class {class_name}Adapter:
    """
    {library_name} 适配器
    自动生成的适配器类
    """

    def __init__(self, config: dict = None):
        self._config = config or {{}}
        self._instance = None
        self._init_library()

    def _init_library(self):
        """初始化库实例"""
        import {self._to_import_name(library_name)} as lib
        self._instance = lib

    def __getattr__(self, name: str):
        """代理所有未定义的方法到库实例"""
        if self._instance is None:
            self._init_library()
        return getattr(self._instance, name)
'''

    def create_adapter(
        self,
        module_name: str,
        library_name: str,
        library_version: str,
        template_type: str = None,
    ) -> AdapterMetadata:
        """
        创建适配器

        Args:
            module_name: 原始模块名
            library_name: 开源库名
            library_version: 开源库版本
            template_type: 模板类型

        Returns:
            AdapterMetadata: 适配器元数据
        """
        adapter_id = self._generate_id(module_name, library_name)
        class_name = self._to_class_name(library_name)
        import_name = self._to_import_name(library_name)
        install_name = import_name.replace("_", "-")
        init_method = ".__init__"

        if template_type is None:
            template_type = self._detect_template_type(module_name)

        template = ADAPTER_TEMPLATES.get(
            template_type,
            self._generate_generic_template(library_name, class_name)
        )

        # 填充模板
        adapter_code = template
        for placeholder, value in [
            ("{{class_name}}", class_name),
            ("{{library_name}}", library_name),
            ("{{version}}", library_version),
            ("{{import_name}}", import_name),
            ("{{install_name}}", install_name),
            ("{{init_method}}", init_method),
        ]:
            adapter_code = adapter_code.replace(placeholder, value)

        # 创建适配器目录
        adapter_dir = self._adapters_dir / adapter_id
        adapter_dir.mkdir(parents=True, exist_ok=True)

        # 写入适配器文件
        adapter_file = adapter_dir / f"{class_name.lower()}_adapter.py"
        adapter_file.write_text(adapter_code, encoding="utf-8")

        # 创建 __init__.py
        (adapter_dir / "__init__.py").write_text(
            f"from .{class_name.lower()}_adapter import {class_name}Adapter\n"
            f"__all__ = ['{class_name}Adapter']\n",
            encoding="utf-8"
        )

        # 创建测试文件
        test_file = adapter_dir / f"test_{class_name.lower()}_adapter.py"
        test_file.write_text(
            self._generate_test_template(class_name, import_name),
            encoding="utf-8"
        )

        # 创建安装脚本
        install_script = adapter_dir / "install.sh"
        install_script.write_text(
            f"#!/bin/bash\npip install {install_name}\n",
            encoding="utf-8"
        )

        # 构建元数据
        metadata = AdapterMetadata(
            adapter_id=adapter_id,
            class_name=class_name,
            module_name=module_name,
            library_name=library_name,
            library_version=library_version,
            import_name=import_name,
            install_name=install_name,
            init_method=init_method,
            template_type=template_type,
            original_module=module_name,
            created_at=int(time.time()),
            file_path=str(adapter_file),
            status="generated",
        )

        self._registry[adapter_id] = metadata
        self._save_registry()

        logger.info(f"Created adapter {class_name}Adapter for {library_name}")
        return metadata

    def _generate_test_template(self, class_name: str, import_name: str) -> str:
        """生成测试模板"""
        return f'''
"""
{class_name}Adapter 测试
"""
import pytest

class Test{class_name}Adapter:
    """测试用例"""

    @pytest.fixture
    def adapter(self):
        from {import_name}_adapter import {class_name}Adapter
        return {class_name}Adapter()

    def test_init(self, adapter):
        """测试初始化"""
        assert adapter is not None

    def test_basic_functionality(self, adapter):
        """测试基本功能"""
        # TODO: 根据实际库实现
        pass
'''

    def install_adapter(self, adapter_id: str) -> bool:
        """
        安装适配器 (安装依赖库)

        Args:
            adapter_id: 适配器ID

        Returns:
            bool: 是否成功
        """
        metadata = self._registry.get(adapter_id)
        if not metadata:
            return False

        try:
            import subprocess
            result = subprocess.run(
                ["pip", "install", metadata.install_name],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                metadata.status = "installed"
                self._save_registry()
                return True
            else:
                logger.error(f"Install failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Install error: {e}")
            return False

    def activate_adapter(self, adapter_id: str) -> bool:
        """
        激活适配器 (替换原始模块)

        Args:
            adapter_id: 适配器ID

        Returns:
            bool: 是否成功
        """
        metadata = self._registry.get(adapter_id)
        if not metadata:
            return False

        if metadata.status != "installed":
            if not self.install_adapter(adapter_id):
                return False

        # 创建符号链接或修改导入路径
        original_module_path = self._find_original_module(metadata.original_module)
        if original_module_path:
            backup_path = original_module_path.with_suffix(".bak")
            if not backup_path.exists():
                shutil.move(original_module_path, backup_path)
                logger.info(f"Backed up original to {backup_path}")

        metadata.status = "active"
        self._save_registry()
        return True

    def deactivate_adapter(self, adapter_id: str) -> bool:
        """
        停用适配器 (恢复原始模块)

        Args:
            adapter_id: 适配器ID

        Returns:
            bool: 是否成功
        """
        metadata = self._registry.get(adapter_id)
        if not metadata:
            return False

        original_module_path = self._find_original_module(metadata.original_module)
        if original_module_path:
            backup_path = original_module_path.with_suffix(".bak")
            if backup_path.exists():
                shutil.move(backup_path, original_module_path)
                logger.info(f"Restored original from {backup_path}")

        metadata.status = "installed"
        self._save_registry()
        return True

    def _find_original_module(self, module_name: str) -> Optional[Path]:
        """查找原始模块路径"""
        import sys
        for path in sys.path:
            module_path = Path(path) / f"{module_name}.py"
            if module_path.exists():
                return module_path

            module_dir = Path(path) / module_name
            if module_dir.exists() and module_dir.is_dir():
                init_file = module_dir / "__init__.py"
                if init_file.exists():
                    return init_file

        return None

    def get_adapter(self, adapter_id: str) -> Optional[AdapterMetadata]:
        """获取适配器元数据"""
        return self._registry.get(adapter_id)

    def get_all_adapters(self) -> List[AdapterMetadata]:
        """获取所有适配器"""
        return list(self._registry.values())

    def get_active_adapter(self, module_name: str) -> Optional[AdapterMetadata]:
        """获取活跃的适配器"""
        for metadata in self._registry.values():
            if metadata.original_module == module_name and metadata.status == "active":
                return metadata
        return None

    def delete_adapter(self, adapter_id: str) -> bool:
        """
        删除适配器

        Args:
            adapter_id: 适配器ID

        Returns:
            bool: 是否成功
        """
        metadata = self._registry.get(adapter_id)
        if not metadata:
            return False

        # 如果是活跃状态，先停用
        if metadata.status == "active":
            self.deactivate_adapter(adapter_id)

        # 删除适配器目录
        adapter_dir = self._adapters_dir / adapter_id
        if adapter_dir.exists():
            shutil.rmtree(adapter_dir)

        del self._registry[adapter_id]
        self._save_registry()
        return True

    def run_tests(self, adapter_id: str) -> Dict[str, Any]:
        """
        运行适配器测试

        Args:
            adapter_id: 适配器ID

        Returns:
            Dict: 测试结果
        """
        metadata = self._registry.get(adapter_id)
        if not metadata:
            return {"status": "error", "message": "Adapter not found"}

        test_file = self._adapters_dir / adapter_id / f"test_{metadata.class_name.lower()}_adapter.py"
        if not test_file.exists():
            return {"status": "skipped", "message": "No test file"}

        try:
            import subprocess
            result = subprocess.run(
                ["pytest", str(test_file), "-v"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            passed = "passed" in result.stdout.lower()
            metadata.test_status = "passing" if passed else "failed"
            self._save_registry()

            return {
                "status": "completed",
                "passed": passed,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }

    def generate_replacement_script(
        self,
        module_name: str,
        library_name: str,
        output_path: Path = None,
    ) -> str:
        """
        生成替换脚本 (供用户手动执行)

        Args:
            module_name: 原始模块名
            library_name: 开源库名
            output_path: 输出路径

        Returns:
            str: 脚本内容
        """
        script = f'''#!/bin/bash
# 替换 {module_name} 为 {library_name}

echo "Step 1: 安装开源库"
pip install {library_name.lower().replace("-", "_")}

echo "Step 2: 备份原始模块"
cp -r $(python -c "import {module_name}; print({module_name}.__file__)") {{module_name}}.bak

echo "Step 3: 应用适配器"
# TODO: 执行适配器替换逻辑

echo "Step 4: 运行测试"
pytest tests/ -v

echo "Done! 如需回滚: cp -r {{module_name}}.bak {{module_name}}"
'''
        if output_path:
            output_path.write_text(script, encoding="utf-8")

        return script


# ============ 全局实例 ============

_adapter_wrapper: Optional[AdapterWrapper] = None


def get_adapter_wrapper() -> AdapterWrapper:
    """获取适配器封装器全局实例"""
    global _adapter_wrapper
    if _adapter_wrapper is None:
        _adapter_wrapper = AdapterWrapper()
    return _adapter_wrapper
