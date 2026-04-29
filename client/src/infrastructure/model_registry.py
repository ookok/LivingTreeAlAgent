"""
模型注册表 - 使用索引+分片策略优化内存使用

功能特点：
1. 分级同步：索引文件 + 分片数据
2. 按需加载：只加载需要的模型系列
3. 压缩存储：使用 gzip 压缩分片数据
4. 缓存机制：已加载的系列缓存在内存中
"""

import json
import gzip
import requests
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Optional, Any

import httpx
from loguru import logger


class ModelRegistrySync:
    """
    优化的模型库同步器
    生成轻量级索引 + 分片数据，避免一次性加载整个模型库
    """
    
    SOURCES = {
        "primary": {
            "name": "yuma-shintani/ollama-model-library",
            "url": "https://yuma-shintani.github.io/ollama-model-library/model.json",
        },
        "secondary": {
            "name": "frefrik/ollama-models-api",
            "url": "https://raw.githubusercontent.com/frefrik/ollama-models-api/main/models.json",
        }
    }
    
    # 常见模型系列
    FAMILIES = [
        "qwen", "qwen2", "qwen3", 
        "llama", "llama2", "llama3", "llama3.1",
        "mistral", "mixtral",
        "gemma", "gemma2",
        "phi", "phi2", "phi3",
        "deepseek",
        "command",
        "codellama",
        "vicuna",
        "zephyr",
        "dolphin",
        "starling",
        "openchat",
        "yi",
        "solar",
        "nous",
        "orca",
        "falcon",
        "mpt",
        "bloom",
        "redpajama",
        "falcon",
        "llava",
        "moondream",
        "bakllava",
        "smollm",
        "tinyllama",
    ]
    
    def __init__(self, registry_dir: str = None):
        if registry_dir is None:
            self.registry_dir = Path(__file__).parent / "model_registry"
        else:
            self.registry_dir = Path(registry_dir)
        
    def sync_models(self, force: bool = False) -> bool:
        """
        同步模型库：生成索引文件 + 分片数据
        
        Args:
            force: 是否强制更新（忽略缓存时间）
        
        Returns:
            是否同步成功
        """
        # 检查缓存是否有效（24小时内）
        index_file = self.registry_dir / "index.json"
        if not force and index_file.exists():
            mtime = index_file.stat().st_mtime
            if datetime.now().timestamp() - mtime < 24 * 3600:
                logger.info("模型注册表缓存有效，跳过同步")
                return True
        
        logger.info("开始同步模型库...")
        
        # 获取模型数据
        all_models = self._fetch_all_models()
        if not all_models:
            logger.error("无法获取模型数据")
            return False
        
        # 确保输出目录存在
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成索引和分片
        self._build_index_and_shards(all_models)
        
        logger.info(f"✅ 同步完成！共处理 {len(all_models)} 个模型")
        logger.info(f"📁 索引文件: {index_file}")
        logger.info(f"📁 分片目录: {self.registry_dir}")
        return True
    
    def _fetch_all_models(self) -> List[dict]:
        """从外部源获取所有模型数据"""
        for source_name, source in self.SOURCES.items():
            try:
                logger.info(f"尝试从 {source['name']} 获取模型列表...")
                response = httpx.get(source["url"], timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # 处理不同的数据格式
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "models" in data:
                    return data["models"]
                else:
                    logger.warning(f"未知的数据格式: {type(data)}")
                    continue
                    
            except Exception as e:
                logger.warning(f"从 {source['name']} 获取失败: {e}")
                continue
        
        return []
    
    def _build_index_and_shards(self, all_models: List[dict]):
        """构建索引文件和分片数据"""
        index_data = {}
        model_families = defaultdict(list)
        
        for item in all_models:
            model_name = item.get("name", "")
            if not model_name:
                continue
            
            # 提取模型系列
            family = self._extract_family(model_name)
            
            # 添加到对应系列
            model_families[family].append(item)
            
            # 构建索引条目（轻量级）
            index_data[model_name] = {
                "family": family,
                "description": item.get("description", ""),
                "tags": item.get("size", []),
                "has_instruct": self._has_instruct(item),
                "updated": item.get("updated", "unknown")
            }
        
        # 保存分片数据（使用 PeaZip 压缩）
        for family, models in model_families.items():
            family_file = self.registry_dir / f"{family}.json.gz"
            
            # 使用 PeaZip 进行压缩（如果可用）
            from .compression_utils import PeaZipIntegration
            
            try:
                # 将数据写入临时文件，然后压缩
                temp_file = self.registry_dir / f"{family}_temp.json"
                temp_file.write_text(json.dumps(models, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                
                # 使用 PeaZip 压缩
                PeaZipIntegration.compress(temp_file, family_file)
                temp_file.unlink()
                
                logger.debug(f"  ✅ 保存系列: {family} ({len(models)} 个模型)")
            except Exception as e:
                # 回退到标准 gzip 压缩
                logger.debug(f"PeaZip 不可用，使用标准压缩: {e}")
                with gzip.open(family_file, "wt", encoding="utf-8") as f:
                    json.dump(models, f, ensure_ascii=False, separators=(",", ":"))
        
        # 保存其他系列（未匹配到已知系列的模型）
        if "other" in model_families:
            other_file = self.registry_dir / "other.json.gz"
            with gzip.open(other_file, "wt", encoding="utf-8") as f:
                json.dump(model_families["other"], f, ensure_ascii=False, separators=(",", ":"))
        
        # 保存索引文件
        index_file = self.registry_dir / "index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "total_models": len(all_models),
                "families": list(model_families.keys()),
                "models": index_data
            }, f, indent=2, ensure_ascii=False)
    
    def _extract_family(self, model_name: str) -> str:
        """提取模型系列"""
        model_lower = model_name.lower()
        for family in self.FAMILIES:
            if model_lower.startswith(family):
                return family
        
        # 默认处理
        if "-" in model_name:
            return model_name.split("-")[0]
        elif ":" in model_name:
            return model_name.split(":")[0]
        else:
            return "other"
    
    def _has_instruct(self, item: dict) -> bool:
        """检查是否有 instruct 版本"""
        description = item.get("description", "").lower()
        tags = item.get("size", [])
        
        if isinstance(tags, list):
            return any("instruct" in str(tag).lower() for tag in tags) or "instruct" in description
        else:
            return "instruct" in description
    
    def get_registry_dir(self) -> Path:
        """获取注册表目录"""
        return self.registry_dir


class LazyModelRegistry:
    """
    懒加载模型注册表
    只加载索引，按需加载特定模型系列
    """
    
    def __init__(self, registry_dir: str = None):
        if registry_dir is None:
            self.registry_dir = Path(__file__).parent / "model_registry"
        else:
            self.registry_dir = Path(registry_dir)
        
        self.index = None
        self._loaded_families = {}  # 缓存已加载的系列
    
    def load_index(self) -> Dict:
        """加载索引文件（内存占用很小）"""
        index_file = self.registry_dir / "index.json"
        if not index_file.exists():
            logger.warning("索引文件不存在，尝试同步...")
            sync = ModelRegistrySync(str(self.registry_dir))
            if not sync.sync_models():
                raise FileNotFoundError("无法加载索引文件")
        
        with open(index_file, "r", encoding="utf-8") as f:
            self.index = json.load(f)
        
        return self.index
    
    def get_model_info(self, model_name: str) -> Optional[dict]:
        """获取单个模型的详细信息（按需加载）"""
        if self.index is None:
            self.load_index()
        
        if model_name not in self.index.get("models", {}):
            return None
        
        # 获取模型所属系列
        model_info = self.index["models"][model_name]
        family = model_info["family"]
        
        # 按需加载该系列
        if family not in self._loaded_families:
            self._load_family(family)
        
        # 在系列数据中查找完整信息
        for model in self._loaded_families.get(family, []):
            if model.get("name") == model_name:
                return model
        
        return None
    
    def _load_family(self, family: str):
        """加载单个模型系列的数据（使用 PeaZip 解压）"""
        family_file = self.registry_dir / f"{family}.json.gz"
        
        if not family_file.exists():
            family_file = self.registry_dir / "other.json.gz"
            if not family_file.exists():
                logger.warning(f"系列文件不存在: {family}")
                self._loaded_families[family] = []
                return
        
        # 使用 PeaZip 解压（如果可用）
        from .compression_utils import PeaZipIntegration
        
        try:
            # 创建临时目录
            temp_dir = self.registry_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            # 使用 PeaZip 解压
            PeaZipIntegration.decompress(family_file, temp_dir)
            
            # 读取解压后的文件
            extracted_file = temp_dir / f"{family}.json"
            if not extracted_file.exists():
                extracted_file = temp_dir / f"{family}_temp.json"
            
            if extracted_file.exists():
                with open(extracted_file, "r", encoding="utf-8") as f:
                    self._loaded_families[family] = json.load(f)
                extracted_file.unlink()
            else:
                # 回退到标准解压
                with gzip.open(family_file, "rt", encoding="utf-8") as f:
                    self._loaded_families[family] = json.load(f)
            
            # 清理临时目录
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            # 回退到标准 gzip 解压
            logger.debug(f"PeaZip 解压失败，使用标准解压: {e}")
            with gzip.open(family_file, "rt", encoding="utf-8") as f:
                self._loaded_families[family] = json.load(f)
        
        logger.debug(f"已加载系列: {family} ({len(self._loaded_families[family])} 个模型)")
    
    def get_candidates_for_family(self, family_name: str, max_count: int = 10) -> List[dict]:
        """获取某个系列下最可能用到的模型"""
        if family_name not in self._loaded_families:
            self._load_family(family_name)
        
        models = self._loaded_families.get(family_name, [])
        
        # 优先选择常见标签的模型
        priority_tags = ["latest", "instruct", "chat", "q4", "q5", "q8", "fp16"]
        
        def priority_score(model: dict) -> int:
            """计算模型优先级分数"""
            score = 0
            tags = model.get("size", [])
            if isinstance(tags, list):
                for tag in tags:
                    tag_lower = str(tag).lower()
                    if tag_lower in priority_tags:
                        score += 10
                    if any(p in tag_lower for p in priority_tags):
                        score += 1
            return score
        
        # 按优先级排序并返回
        models.sort(key=priority_score, reverse=True)
        return models[:max_count]
    
    def search_models(self, query: str) -> List[dict]:
        """搜索模型（基于索引）"""
        if self.index is None:
            self.load_index()
        
        results = []
        for model_name, info in self.index.get("models", {}).items():
            if query.lower() in model_name.lower() or \
               query.lower() in info.get("description", "").lower():
                results.append({
                    "name": model_name,
                    "family": info["family"],
                    "description": info["description"]
                })
        
        return results[:20]
    
    def get_all_families(self) -> List[str]:
        """获取所有模型系列"""
        if self.index is None:
            self.load_index()
        return self.index.get("families", [])
    
    def get_models_by_family(self, family_name: str) -> List[str]:
        """获取某个系列的所有模型名称"""
        if self.index is None:
            self.load_index()
        
        models = []
        for model_name, info in self.index.get("models", {}).items():
            if info["family"] == family_name:
                models.append(model_name)
        
        return models
    
    def clear_cache(self):
        """清除已加载系列的缓存"""
        self._loaded_families.clear()
        logger.debug("已清除系列缓存")


# 单例模式
_registry_instance = None

def get_model_registry() -> LazyModelRegistry:
    """获取模型注册表实例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = LazyModelRegistry()
    return _registry_instance


def sync_model_registry(force: bool = False) -> bool:
    """快捷函数：同步模型注册表"""
    sync = ModelRegistrySync()
    return sync.sync_models(force)


# 测试代码
if __name__ == "__main__":
    # 测试同步
    print("=" * 60)
    print("测试模型注册表同步")
    print("=" * 60)
    
    sync = ModelRegistrySync()
    success = sync.sync_models()
    print(f"同步结果: {'成功' if success else '失败'}")
    
    # 测试懒加载
    print("\n" + "=" * 60)
    print("测试懒加载模型注册表")
    print("=" * 60)
    
    registry = LazyModelRegistry()
    
    # 获取所有系列
    families = registry.get_all_families()
    print(f"可用系列: {len(families)} 个")
    print(f"系列列表: {families[:10]}...")
    
    # 搜索模型
    results = registry.search_models("qwen")
    print(f"\n搜索 'qwen' 结果: {len(results)} 个")
    for r in results[:5]:
        print(f"  - {r['name']}: {r['description']}")
    
    # 获取 Qwen 系列候选模型
    candidates = registry.get_candidates_for_family("qwen")
    print(f"\nQwen 系列候选模型:")
    for c in candidates[:5]:
        print(f"  - {c.get('name', '')}")
    
    # 获取单个模型信息
    model_info = registry.get_model_info("qwen3.5")
    if model_info:
        print(f"\n模型 'qwen3.5' 信息:")
        print(f"  描述: {model_info.get('description', '')}")
        print(f"  标签: {model_info.get('size', [])}")
    
    print("\n" + "=" * 60)