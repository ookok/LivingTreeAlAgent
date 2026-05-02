from typing import Dict, List, Optional, Any
from .manifest import ToolManifest, ToolStatus
import json
import os
from datetime import datetime
import threading
from pathlib import Path


class ToolRegistry:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self.manifests: Dict[str, ToolManifest] = {}
        self.status_cache: Dict[str, ToolStatus] = {}
        self.manifest_dir = Path(__file__).parent / "manifests"
        self.manifest_dir.mkdir(exist_ok=True)
        self._load_manifests()

    def register_manifest(self, manifest: ToolManifest):
        """注册工具清单"""
        self.manifests[manifest.tool_id] = manifest
        self._save_manifest(manifest)
        self.status_cache.pop(manifest.tool_id, None)

    def unregister_manifest(self, tool_id: str):
        """注销工具清单"""
        if tool_id in self.manifests:
            del self.manifests[tool_id]
            self.status_cache.pop(tool_id, None)
            manifest_file = self.manifest_dir / f"{tool_id}.json"
            if manifest_file.exists():
                manifest_file.unlink()

    def get_manifest(self, tool_id: str) -> Optional[ToolManifest]:
        """获取工具清单"""
        return self.manifests.get(tool_id)

    def list_manifests(self) -> List[ToolManifest]:
        """获取所有工具清单"""
        return list(self.manifests.values())

    def search_by_intent(self, intent: str) -> List[ToolManifest]:
        """根据意图搜索工具 - 使用LLM进行语义理解"""
        try:
            return self._search_with_llm(intent)
        except Exception as e:
            print(f"LLM搜索失败，回退到关键词匹配: {e}")
            return self._search_with_keywords(intent)
    
    def _search_with_llm(self, intent: str) -> List[ToolManifest]:
        """使用LLM进行语义匹配"""
        from business.global_model_router import call_model_sync, ModelCapability
        
        tools_info = "\n".join([
            f"{m.tool_id}: {m.name} - {m.description}"
            for m in self.manifests.values()
        ])
        
        prompt = f"""
请分析以下用户意图，并从提供的工具列表中选择最合适的工具。

用户意图: {intent}

可用工具列表:
{tools_info}

请返回匹配的工具ID列表，每个ID一行，按匹配度从高到低排序。
如果没有合适的工具，请返回空列表。

输出格式:
<tool_id>
<tool_id>
...
"""
        
        response = call_model_sync(ModelCapability.CHAT, prompt)
        
        results = []
        for line in response.strip().split('\n'):
            tool_id = line.strip()
            if tool_id in self.manifests:
                results.append(self.manifests[tool_id])
        
        return results
    
    def _search_with_keywords(self, intent: str) -> List[ToolManifest]:
        """基于关键词匹配的回退搜索"""
        results = []
        intent_lower = intent.lower()
        intent_words = intent_lower.split()
        
        for manifest in self.manifests.values():
            description = manifest.description.lower()
            name = manifest.name.lower()
            
            full_match = intent_lower in description or intent_lower in name
            keyword_match = any(word in description or word in name for word in intent_words)
            
            tag_match = False
            for tag in manifest.tags:
                tag_lower = tag.lower()
                if intent_lower in tag_lower:
                    tag_match = True
                    break
                for word in intent_words:
                    if word in tag_lower:
                        tag_match = True
                        break
            
            if full_match or keyword_match or tag_match:
                results.append(manifest)
        
        results.sort(key=lambda m: self._calculate_match_score(m, intent_lower), reverse=True)
        return results

    def _calculate_match_score(self, manifest: ToolManifest, intent: str) -> int:
        """计算匹配分数"""
        score = 0
        intent_words = intent.split()
        
        if intent in manifest.description.lower():
            score += 10
        if intent in manifest.name.lower():
            score += 5
        for word in intent_words:
            if word in manifest.description.lower():
                score += 2
            if word in manifest.name.lower():
                score += 1
        
        return score

    def get_available_tools(self) -> List[ToolManifest]:
        """获取所有可用工具"""
        return [m for m in self.manifests.values()]

    def get_tool_status(self, tool_id: str) -> ToolStatus:
        """获取工具状态"""
        if tool_id in self.status_cache:
            return self.status_cache[tool_id]
        
        manifest = self.get_manifest(tool_id)
        if not manifest:
            return ToolStatus(
                tool_id=tool_id,
                available=False,
                error="Tool not found"
            )
        
        import subprocess
        try:
            result = subprocess.run(
                manifest.check_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()[:50] if result.stdout else None
                status = ToolStatus(
                    tool_id=tool_id,
                    available=True,
                    version=version,
                    last_checked=datetime.now().isoformat()
                )
            else:
                status = ToolStatus(
                    tool_id=tool_id,
                    available=False,
                    error=result.stderr.strip()[:100] if result.stderr else "Command failed",
                    last_checked=datetime.now().isoformat()
                )
        except Exception as e:
            status = ToolStatus(
                tool_id=tool_id,
                available=False,
                error=str(e)[:100],
                last_checked=datetime.now().isoformat()
            )
        
        self.status_cache[tool_id] = status
        return status

    def refresh_status(self, tool_id: str = None):
        """刷新工具状态"""
        if tool_id:
            self.status_cache.pop(tool_id, None)
            self.get_tool_status(tool_id)
        else:
            self.status_cache.clear()
            for tid in self.manifests.keys():
                self.get_tool_status(tid)

    def _load_manifests(self):
        """从文件加载所有工具清单"""
        for manifest_file in self.manifest_dir.glob("*.json"):
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    manifest = ToolManifest(**data)
                    self.manifests[manifest.tool_id] = manifest
            except Exception as e:
                print(f"Failed to load manifest {manifest_file}: {e}")

    def _save_manifest(self, manifest: ToolManifest):
        """保存工具清单到文件"""
        manifest_file = self.manifest_dir / f"{manifest.tool_id}.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest.dict(), f, indent=2, ensure_ascii=False)

    def get_equivalent_tools(self, tool_id: str) -> List[ToolManifest]:
        """获取等价工具列表（包括降级工具）"""
        manifest = self.get_manifest(tool_id)
        if not manifest:
            return []
        
        results = []
        for fallback_id in manifest.fallback_tools:
            fallback_manifest = self.get_manifest(fallback_id)
            if fallback_manifest:
                results.append(fallback_manifest)
        
        return results


registry = ToolRegistry()
