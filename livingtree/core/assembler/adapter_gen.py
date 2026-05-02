"""
适配器生成器 (Adapter Generator)

目标：将外部模块统一封装为 ToolContract 接口

生成的适配器：
- 统一的调用格式
- 参数验证
- 错误处理
- 结果标准化
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Callable


@dataclass
class ToolContract:
    """工具合约定义"""
    name: str
    version: str = "1.0.0"
    description: str = ""

    # 输入输出定义
    input_schema: dict = None   # JSON Schema
    output_schema: dict = None  # JSON Schema

    # 调用入口
    entry_point: str = ""       # 模块路径::函数名
    command: str = ""           # CLI 命令

    # 元数据
    tags: list[str] = None
    examples: list[dict] = None

    def __post_init__(self):
        if self.input_schema is None:
            self.input_schema = {}
        if self.output_schema is None:
            self.output_schema = {}
        if self.tags is None:
            self.tags = []
        if self.examples is None:
            self.examples = []

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "entry_point": self.entry_point,
            "command": self.command,
            "tags": self.tags,
            "examples": self.examples,
        }


class AdapterGenerator:
    """适配器生成器"""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path.home() / ".hermes-desktop" / "modules" / "adapters"
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_python_adapter(
        self,
        module_name: str,
        repo_info: dict,
        installation_result: dict
    ) -> str:
        """
        生成 Python 模块适配器

        Args:
            module_name: 模块名称
            repo_info: 仓库信息
            installation_result: 安装结果

        Returns:
            str: 适配器代码
        """
        safe_name = self._to_safe_name(module_name)
        module_path = installation_result.get("module_path", "")

        adapter_code = f'''"""
{safe_name.title()} 适配器

自动生成 by 星港装配坞
来源: {repo_info.get("url", "unknown")}
版本: {repo_info.get("stars", 0)} ⭐
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# 模块路径
MODULE_PATH = Path("{module_path}")
MODULE_NAME = "{module_name}"
ENTRY_POINT = "{installation_result.get("entry_point", "")}"


class {safe_name.title()}Adapter:
    """{repo_info.get("description", module_name)} 适配器"""

    def __init__(self):
        self.name = MODULE_NAME
        self.version = "{installation_result.get("runtime_version", "unknown")}"

    def execute(self, action: str, **kwargs) -> dict:
        """
        执行操作

        Args:
            action: 操作名称
            **kwargs: 操作参数

        Returns:
            dict: 执行结果
        """
        try:
            if action == "call":
                return self._call(**kwargs)
            elif action == "info":
                return self._info()
            else:
                return {{"success": False, "error": f"未知操作: {{action}}"}}
        except Exception as e:
            return {{"success": False, "error": str(e)}}

    def _call(self, **kwargs) -> dict:
        """调用模块功能"""
        # TODO: 根据模块特性实现调用逻辑
        return {{
            "success": True,
            "result": "功能调用成功",
            "params": kwargs
        }}

    def _info(self) -> dict:
        """获取模块信息"""
        return {{
            "name": self.name,
            "version": self.version,
            "path": str(MODULE_PATH),
            "description": "{repo_info.get("description", "")}",
        }}


# 导出标准接口
def create_adapter() -> {safe_name.title()}Adapter:
    """创建适配器实例"""
    return {safe_name.title()}Adapter()


if __name__ == "__main__":
    adapter = create_adapter()
    print(json.dumps(adapter.execute("info"), ensure_ascii=False, indent=2))
'''

        return adapter_code

    def generate_cli_adapter(
        self,
        module_name: str,
        repo_info: dict,
        installation_result: dict
    ) -> str:
        """
        生成 CLI 适配器

        Args:
            module_name: 模块名称
            repo_info: 仓库信息
            installation_result: 安装结果

        Returns:
            str: 适配器代码 (shell 脚本)
        """
        safe_name = self._to_safe_name(module_name)
        entry_point = installation_result.get("entry_point", "")

        # 区分 Windows/Linux
        if sys.platform == 'win32':
            ext = '.bat'
            shebang = '@echo off'
        else:
            ext = '.sh'
            shebang = '#!/bin/bash'

        adapter_code = f'''{shebang}
"""
{safe_name} CLI 适配器

自动生成 by 星港装配坞
来源: {repo_info.get("url", "unknown")}
"""

set MODULE_NAME={module_name}
set ENTRY_POINT={entry_point}

:info
    echo {module_name} CLI Adapter
    echo Version: {installation_result.get("runtime_version", "unknown")}
    goto :end

:call
    {entry_point} %*
    goto :end

:end
'''

        return adapter_code

    def generate_tool_contract(
        self,
        module_name: str,
        repo_info: dict,
        installation_result: dict
    ) -> ToolContract:
        """
        生成工具合约

        Args:
            module_name: 模块名称
            repo_info: 仓库信息
            installation_result: 安装结果

        Returns:
            ToolContract: 工具合约
        """
        safe_name = self._to_safe_name(module_name)

        contract = ToolContract(
            name=f"ext:{safe_name}",
            version="1.0.0",
            description=repo_info.get("description", f"External module: {module_name}"),
            entry_point=installation_result.get("entry_point", ""),
            tags=self._extract_tags(repo_info),
            input_schema=self._generate_input_schema(repo_info),
            output_schema={"type": "object"},
        )

        return contract

    def save_adapter(
        self,
        module_name: str,
        code: str,
        adapter_type: str = "python"
    ) -> Path:
        """
        保存适配器代码

        Args:
            module_name: 模块名称
            code: 适配器代码
            adapter_type: 适配器类型 (python/cli)

        Returns:
            Path: 保存路径
        """
        safe_name = self._to_safe_name(module_name)
        ext = ".py" if adapter_type == "python" else ".sh"
        file_path = self.output_dir / f"{safe_name}_adapter{ext}"
        file_path.write_text(code, encoding='utf-8')
        return file_path

    def save_tool_contract(self, contract: ToolContract) -> Path:
        """
        保存工具合约

        Args:
            contract: 工具合约

        Returns:
            Path: 保存路径
        """
        file_path = self.output_dir / f"{contract.name}_contract.json"
        file_path.write_text(
            json.dumps(contract.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        return file_path

    def _to_safe_name(self, name: str) -> str:
        """转换为安全文件名"""
        # 移除特殊字符，只保留字母数字下划线
        return re.sub(r'[^a-zA-Z0-9_]', '_', name).lower()

    def _extract_tags(self, repo_info: dict) -> list[str]:
        """从仓库信息提取标签"""
        tags = []

        # 语言
        if repo_info.get("language"):
            tags.append(repo_info["language"].lower())

        # 描述关键词
        desc = repo_info.get("description", "").lower()
        keywords = ["pdf", "json", "api", "http", "crypto", "db", "sql", "web"]
        for kw in keywords:
            if kw in desc:
                tags.append(kw)

        return tags

    def _generate_input_schema(self, repo_info: dict) -> dict:
        """生成输入 Schema"""
        # TODO: 根据模块特性生成更精确的 Schema
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["call", "info"],
                    "description": "操作类型"
                }
            },
            "required": ["action"]
        }

    def load_contract(self, module_name: str) -> Optional[ToolContract]:
        """
        加载工具合约

        Args:
            module_name: 模块名称

        Returns:
            Optional[ToolContract]: 工具合约
        """
        safe_name = self._to_safe_name(module_name)
        contract_path = self.output_dir / f"ext:{safe_name}_contract.json"

        if not contract_path.exists():
            return None

        try:
            data = json.loads(contract_path.read_text(encoding='utf-8'))
            return ToolContract(**data)
        except Exception:
            return None

    def list_adapters(self) -> list[dict]:
        """列出所有适配器"""
        adapters = []

        for file_path in self.output_dir.iterdir():
            if file_path.suffix == '.py' and '_adapter' in file_path.name:
                adapters.append({
                    "name": file_path.stem.replace("_adapter", ""),
                    "type": "python",
                    "path": str(file_path)
                })
            elif file_path.suffix == '.sh' and '_adapter' in file_path.name:
                adapters.append({
                    "name": file_path.stem.replace("_adapter", ""),
                    "type": "cli",
                    "path": str(file_path)
                })
            elif file_path.suffix == '.json' and '_contract' in file_path.name:
                adapters.append({
                    "name": file_path.stem.replace("_contract", ""),
                    "type": "contract",
                    "path": str(file_path)
                })

        return adapters