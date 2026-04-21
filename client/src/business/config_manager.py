"""
配置导入导出管理器
Config Import/Export Manager

支持系统配置的一键导入导出，包括：
- 用户配置
- 专家人格库
- 技能包
- 用户画像
- 所有数据的 ZIP 压缩打包
"""

import os
import json
import zipfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
import base64

import requests


@dataclass
class ExportItem:
    """导出项"""
    name: str
    file_path: str
    description: str = ""
    category: str = "general"  # general, config, experts, skills, profiles
    size: int = 0


@dataclass
class ExportResult:
    """导出结果"""
    success: bool
    file_path: str = ""
    items_count: int = 0
    size: int = 0
    error: str = ""


@dataclass
class ImportResult:
    """导入结果"""
    success: bool
    items_imported: int = 0
    items_skipped: int = 0
    errors: List[str] = field(default_factory=list)


class ConfigManager:
    """
    配置管理器
    
    功能：
    1. 系统配置导出/导入
    2. 专家人格库导出/导入
    3. 技能包导出/导入
    4. 用户画像导出/导入
    5. ZIP 压缩打包
    6. 从 URL/文件导入
    """
    
    # 配置文件类型
    CONFIG_FILES = {
        "config": "config.json",
        "experts": "expert_system/experts.json",
        "skills": "expert_system/skills.json",
        "profiles": "expert_system/user_profiles.json",
        "sessions": "sessions.db",
    }
    
    def __init__(self, data_dir: str = None):
        """
        初始化配置管理器
        
        Args:
            data_dir: 数据目录路径
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = self._get_default_data_dir()
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 临时目录
        self._temp_dir = self.data_dir / ".temp"
    
    def _get_default_data_dir(self) -> Path:
        """获取默认数据目录"""
        user_dir = Path.home() / ".hermes-desktop"
        if os.access(str(Path.home()), os.W_OK):
            return user_dir
        
        return Path(__file__).parent.parent
    
    def _get_export_dir(self) -> Path:
        """获取导出目录"""
        export_dir = self.data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir
    
    def _get_backup_dir(self) -> Path:
        """获取备份目录"""
        backup_dir = self.data_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir
    
    # ── 导出功能 ─────────────────────────────────────────────────────
    
    def export_all(
        self,
        output_path: str = None,
        include_sessions: bool = True,
        progress_callback: Callable[[str, float], None] = None
    ) -> ExportResult:
        """
        导出所有配置为 ZIP
        
        Args:
            output_path: 输出路径（自动生成如果为None）
            include_sessions: 是否包含会话历史
            progress_callback: 进度回调
            
        Returns:
            ExportResult: 导出结果
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self._get_export_dir() / f"hermes_backup_{timestamp}.zip"
        
        output_path = Path(output_path)
        
        try:
            if progress_callback:
                progress_callback("准备导出...", 0.1)
            
            items_count = 0
            
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 导出配置文件
                for key, rel_path in self.CONFIG_FILES.items():
                    if key == "sessions" and not include_sessions:
                        continue
                    
                    file_path = self.data_dir / rel_path
                    if file_path.exists():
                        zf.write(file_path, rel_path)
                        items_count += 1
                        
                        if progress_callback:
                            progress_callback(f"已添加: {rel_path}", 0.3 + items_count * 0.1)
                
                # 添加元数据
                metadata = {
                    "exported_at": datetime.now().isoformat(),
                    "version": "1.0.0",
                    "items_count": items_count,
                    "includes_sessions": include_sessions
                }
                zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            
            return ExportResult(
                success=True,
                file_path=str(output_path),
                items_count=items_count,
                size=output_path.stat().st_size
            )
            
        except Exception as e:
            return ExportResult(success=False, error=str(e))
    
    def export_config(self, output_path: str = None) -> ExportResult:
        """导出系统配置"""
        return self.export_items(["config"], output_path)
    
    def export_experts(self, output_path: str = None) -> ExportResult:
        """导出专家人格库"""
        return self.export_items(["experts"], output_path)
    
    def export_skills(self, output_path: str = None) -> ExportResult:
        """导出技能包"""
        return self.export_items(["skills"], output_path)
    
    def export_profiles(self, output_path: str = None) -> ExportResult:
        """导出用户画像"""
        return self.export_items(["profiles"], output_path)
    
    def export_items(
        self,
        item_keys: List[str],
        output_path: str = None
    ) -> ExportResult:
        """
        导出指定项目
        
        Args:
            item_keys: 要导出的项目键列表
            output_path: 输出路径
            
        Returns:
            ExportResult: 导出结果
        """
        if output_path is None:
            key_str = "_".join(item_keys)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self._get_export_dir() / f"hermes_{key_str}_{timestamp}.zip"
        
        output_path = Path(output_path)
        
        try:
            items_count = 0
            
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for key in item_keys:
                    if key not in self.CONFIG_FILES:
                        continue
                    
                    rel_path = self.CONFIG_FILES[key]
                    file_path = self.data_dir / rel_path
                    
                    if file_path.exists():
                        zf.write(file_path, rel_path)
                        items_count += 1
                    
                    # 如果是目录，添加目录下所有文件
                    elif file_path.is_dir():
                        for root, dirs, files in os.walk(file_path):
                            for file in files:
                                full_path = Path(root) / file
                                arcname = str(full_path.relative_to(self.data_dir))
                                zf.write(full_path, arcname)
                                items_count += 1
            
            return ExportResult(
                success=True,
                file_path=str(output_path),
                items_count=items_count,
                size=output_path.stat().st_size
            )
            
        except Exception as e:
            return ExportResult(success=False, error=str(e))
    
    def export_to_json(self, item_key: str) -> Optional[str]:
        """
        导出为 JSON 字符串
        
        Args:
            item_key: 项目键
            
        Returns:
            JSON 字符串，失败返回 None
        """
        if item_key not in self.CONFIG_FILES:
            return None
        
        file_path = self.data_dir / self.CONFIG_FILES[item_key]
        
        if not file_path.exists():
            return None
        
        try:
            if file_path.suffix == ".json":
                return file_path.read_text(encoding="utf-8")
            elif file_path.suffix == ".db":
                # SQLite 数据库，转换为 JSON
                import sqlite3
                conn = sqlite3.connect(str(file_path))
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                data = {"tables": {}, "exported_at": datetime.now().isoformat()}
                
                for table in tables:
                    cursor = conn.execute(f"SELECT * FROM {table}")
                    rows = [dict(row) for row in cursor.fetchall()]
                    # 转换 bytes
                    for row in rows:
                        for k, v in row.items():
                            if isinstance(v, bytes):
                                row[k] = base64.b64encode(v).decode()
                    data["tables"][table] = rows
                
                conn.close()
                return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        return None
    
    # ── 导入功能 ─────────────────────────────────────────────────────
    
    def import_from_zip(
        self,
        zip_path: str,
        progress_callback: Callable[[str, float], None] = None,
        merge: bool = True
    ) -> ImportResult:
        """
        从 ZIP 文件导入
        
        Args:
            zip_path: ZIP 文件路径
            progress_callback: 进度回调
            merge: 是否合并（True）或覆盖（False）
            
        Returns:
            ImportResult: 导入结果
        """
        zip_path = Path(zip_path)
        
        if not zip_path.exists():
            return ImportResult(success=False, errors=["文件不存在"])
        
        result = ImportResult(success=False)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 创建临时目录
                self._temp_dir.mkdir(parents=True, exist_ok=True)
                
                # 解压
                zf.extractall(self._temp_dir)
                
                # 读取元数据
                metadata_path = self._temp_dir / "metadata.json"
                metadata = {}
                if metadata_path.exists():
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                
                # 导入各个文件
                for key, rel_path in self.CONFIG_FILES.items():
                    src_path = self._temp_dir / rel_path
                    
                    if not src_path.exists():
                        continue
                    
                    dst_path = self.data_dir / rel_path
                    
                    if merge:
                        # 合并模式
                        success, skipped = self._merge_file(src_path, dst_path, key)
                        if success:
                            result.items_imported += 1
                        if skipped:
                            result.items_skipped += skipped
                    else:
                        # 覆盖模式
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                        result.items_imported += 1
                    
                    if progress_callback:
                        progress_callback(f"已导入: {rel_path}", 0.5 + result.items_imported * 0.1)
            
            result.success = True
            
        except Exception as e:
            result.errors.append(str(e))
        
        finally:
            # 清理临时目录
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
        
        return result
    
    def import_from_url(
        self,
        url: str,
        item_type: str = "experts",
        progress_callback: Callable[[str, float], None] = None
    ) -> ImportResult:
        """
        从 URL 导入
        
        Args:
            url: 资源 URL
            item_type: 项目类型（experts/skills/profiles/config）
            progress_callback: 进度回调
            
        Returns:
            ImportResult: 导入结果
        """
        result = ImportResult()
        
        try:
            if progress_callback:
                progress_callback("正在下载...", 0.1)
            
            # 下载内容
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            
            content = resp.text
            
            if progress_callback:
                progress_callback("正在解析...", 0.5)
            
            # 解析内容
            if url.endswith('.zip'):
                # 保存为临时文件
                self._temp_dir.mkdir(parents=True, exist_ok=True)
                temp_zip = self._temp_dir / "import.zip"
                temp_zip.write_bytes(resp.content)
                
                result = self.import_from_zip(str(temp_zip), progress_callback)
                
            elif url.endswith('.json') or 'json' in resp.headers.get('content-type', ''):
                # JSON 格式，直接导入
                data = json.loads(content)
                
                # 确定目标路径
                if item_type in self.CONFIG_FILES:
                    dst_path = self.data_dir / self.CONFIG_FILES[item_type]
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 合并或覆盖
                    if dst_path.exists():
                        existing = json.loads(dst_path.read_text(encoding="utf-8"))
                        merged = self._deep_merge(existing, data)
                        dst_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
                    else:
                        dst_path.write_text(content, encoding="utf-8")
                    
                    result.items_imported = 1
                    result.success = True
            
            elif url.endswith('.md'):
                # Markdown 格式
                result = self._import_markdown(content, item_type)
            
            if progress_callback:
                progress_callback("导入完成", 1.0)
            
        except Exception as e:
            result.errors.append(f"下载/解析失败: {e}")
        
        finally:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
        
        return result
    
    def import_from_file(
        self,
        file_path: str,
        item_type: str = "experts",
        merge: bool = True
    ) -> ImportResult:
        """
        从本地文件导入
        
        Args:
            file_path: 文件路径
            item_type: 项目类型
            merge: 是否合并
            
        Returns:
            ImportResult: 导入结果
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return ImportResult(success=False, errors=["文件不存在"])
        
        if file_path.suffix == '.zip':
            return self.import_from_zip(str(file_path), merge=merge)
        
        # JSON 或 Markdown
        try:
            content = file_path.read_text(encoding="utf-8")
            
            if file_path.suffix == '.json':
                data = json.loads(content)
                
                if item_type in self.CONFIG_FILES:
                    dst_path = self.data_dir / self.CONFIG_FILES[item_type]
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    if merge and dst_path.exists():
                        existing = json.loads(dst_path.read_text(encoding="utf-8"))
                        merged = self._deep_merge(existing, data)
                        dst_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
                    else:
                        dst_path.write_text(content, encoding="utf-8")
                    
                    return ImportResult(success=True, items_imported=1)
            
            elif file_path.suffix == '.md':
                return self._import_markdown(content, item_type)
                
        except Exception as e:
            return ImportResult(success=False, errors=[str(e)])
        
        return ImportResult(success=False, errors=["不支持的文件格式"])
    
    def _import_markdown(self, content: str, item_type: str) -> ImportResult:
        """从 Markdown 导入"""
        # 简单的 Markdown 解析
        # 实际应用中应该使用更完善的解析器
        
        result = ImportResult()
        
        # 尝试提取 JSON 代码块
        import re
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        
        if json_blocks:
            for block in json_blocks:
                try:
                    data = json.loads(block)
                    
                    if item_type in self.CONFIG_FILES:
                        dst_path = self.data_dir / self.CONFIG_FILES[item_type]
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        if dst_path.exists():
                            existing = json.loads(dst_path.read_text(encoding="utf-8"))
                            merged = self._deep_merge(existing, data)
                            dst_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
                        else:
                            dst_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        
                        result.items_imported += 1
                except json.JSONDecodeError:
                    result.errors.append("JSON 解析失败")
        else:
            result.errors.append("未找到可导入的内容")
        
        result.success = result.items_imported > 0
        return result
    
    def _merge_file(self, src_path: Path, dst_path: Path, file_type: str) -> tuple:
        """
        合并文件
        
        Returns:
            (success, skipped_count)
        """
        if not dst_path.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            return True, 0
        
        # JSON 文件合并
        if dst_path.suffix == '.json':
            try:
                src_data = json.loads(src_path.read_text(encoding="utf-8"))
                dst_data = json.loads(dst_path.read_text(encoding="utf-8"))
                
                merged = self._deep_merge(dst_data, src_data)
                dst_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
                
                return True, 0
            except json.JSONDecodeError:
                pass
        
        # 其他文件直接覆盖
        shutil.copy2(src_path, dst_path)
        return True, 0
    
    def _deep_merge(self, base: dict, update: dict) -> dict:
        """深度合并字典"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            elif key in result and isinstance(result[key], list) and isinstance(value, list):
                # 列表合并去重
                result[key] = result[key] + [v for v in value if v not in result[key]]
            else:
                result[key] = value
        
        return result
    
    # ── 备份与恢复 ─────────────────────────────────────────────────
    
    def create_backup(self, name: str = None) -> ExportResult:
        """
        创建命名备份
        
        Args:
            name: 备份名称（自动生成如果为None）
            
        Returns:
            ExportResult: 备份结果
        """
        if name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"backup_{timestamp}"
        
        backup_path = self._get_backup_dir() / f"{name}.zip"
        
        result = self.export_all(str(backup_path))
        
        if not result.success:
            return result
        
        # 保存备份索引
        index_path = self._get_backup_dir() / "index.json"
        index = []
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding="utf-8"))
        
        index.append({
            "name": name,
            "path": str(backup_path),
            "created_at": datetime.now().isoformat(),
            "size": result.size
        })
        
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return result
    
    def restore_backup(self, name: str = None, zip_path: str = None) -> ImportResult:
        """
        恢复备份
        
        Args:
            name: 备份名称
            zip_path: 或者直接指定 ZIP 路径
            
        Returns:
            ImportResult: 恢复结果
        """
        if zip_path is None and name:
            index_path = self._get_backup_dir() / "index.json"
            if index_path.exists():
                index = json.loads(index_path.read_text(encoding="utf-8"))
                for item in index:
                    if item["name"] == name:
                        zip_path = item["path"]
                        break
        
        if zip_path is None:
            return ImportResult(success=False, errors=["备份不存在"])
        
        return self.import_from_zip(zip_path, merge=False)
    
    def list_backups(self) -> List[Dict]:
        """列出所有备份"""
        index_path = self._get_backup_dir() / "index.json"
        
        if index_path.exists():
            return json.loads(index_path.read_text(encoding="utf-8"))
        
        return []
    
    # ── 工具方法 ─────────────────────────────────────────────────────
    
    def get_exportable_items(self) -> List[ExportItem]:
        """获取可导出的项目列表"""
        items = []
        
        for key, rel_path in self.CONFIG_FILES.items():
            file_path = self.data_dir / rel_path
            
            if file_path.exists():
                size = file_path.stat().st_size if file_path.is_file() else 0
                
                items.append(ExportItem(
                    name=key,
                    file_path=str(file_path),
                    description=self._get_item_description(key),
                    category=self._get_item_category(key),
                    size=size
                ))
            elif file_path.is_dir() and any(file_path.iterdir()):
                items.append(ExportItem(
                    name=key,
                    file_path=str(file_path),
                    description=self._get_item_description(key),
                    category=self._get_item_category(key),
                    size=0
                ))
        
        return items
    
    def _get_item_description(self, key: str) -> str:
        """获取项目描述"""
        descriptions = {
            "config": "系统配置（窗口大小、主题、Ollama设置等）",
            "experts": "专家人格库（角色定义、触发条件等）",
            "skills": "技能包（专业能力定义）",
            "profiles": "用户画像（偏好、习惯、学习记录）",
            "sessions": "会话历史（聊天记录）"
        }
        return descriptions.get(key, "")
    
    def _get_item_category(self, key: str) -> str:
        """获取项目分类"""
        categories = {
            "config": "config",
            "experts": "experts",
            "skills": "skills",
            "profiles": "profiles",
            "sessions": "general"
        }
        return categories.get(key, "general")


# 单例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
