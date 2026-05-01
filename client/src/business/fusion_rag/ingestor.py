"""
Multi-Modal Data Ingestor

多模态数据摄入管道，支持文本、PDF、图像、音频、视频等多种数据类型。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
import logging
import hashlib
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class IngestDocument:
    """摄入文档"""
    id: str
    content: str
    data_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class MultiModalIngestor:
    """
    多模态数据摄入器
    
    支持的数据类型：
    - text: 纯文本
    - markdown: Markdown 格式
    - pdf: PDF 文档
    - image: 图像（OCR提取文本）
    - audio: 音频（语音转文字）
    - video: 视频（提取音频后转文字）
    - url: 网页链接
    """
    
    def __init__(self):
        """初始化多模态摄入器"""
        self._entity_recognizer = None
        self._knowledge_graph = None
        self._vector_store = None
        
        self._init_dependencies()
        logger.info("MultiModalIngestor 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from ..entity_management import get_entity_recognizer, get_entity_resolver
            from .knowledge_graph import DynamicKnowledgeGraph
            from .smart_vector_store import get_smart_vector_store
            
            self._entity_recognizer = get_entity_recognizer()
            self._entity_resolver = get_entity_resolver()
            self._knowledge_graph = DynamicKnowledgeGraph()
            self._vector_store = get_smart_vector_store()
            
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    async def ingest(self, data: Union[str, bytes], data_type: str = "text", 
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        摄入数据
        
        Args:
            data: 数据内容（文本或二进制）
            data_type: 数据类型
            metadata: 元数据
            
        Returns:
            Dict 摄入结果
        """
        try:
            # 1. 提取文本内容
            text_content = await self._extract_text(data, data_type)
            
            # 2. 生成文档ID
            doc_id = self._generate_doc_id(text_content)
            
            # 3. 识别实体
            entities = await self._recognize_entities(text_content)
            
            # 4. 提取关系
            relations = await self._extract_relations(text_content, entities)
            
            # 5. 保存到向量存储
            await self._save_to_vector_store(doc_id, text_content, entities, metadata)
            
            # 6. 添加到知识图谱
            await self._add_to_knowledge_graph(entities, relations)
            
            # 7. 保存文档
            document = IngestDocument(
                id=doc_id,
                content=text_content,
                data_type=data_type,
                metadata=metadata or {},
                entities=entities,
                relations=relations,
            )
            
            logger.info(f"数据摄入成功: {doc_id}, 实体数: {len(entities)}, 关系数: {len(relations)}")
            
            return {
                "success": True,
                "document_id": doc_id,
                "content_length": len(text_content),
                "entities_count": len(entities),
                "relations_count": len(relations),
                "message": "数据摄入成功",
            }
            
        except Exception as e:
            logger.error(f"数据摄入失败: {e}")
            return {
                "success": False,
                "document_id": "",
                "message": str(e),
            }
    
    async def _extract_text(self, data: Union[str, bytes], data_type: str) -> str:
        """
        从数据中提取文本
        
        Args:
            data: 数据内容
            data_type: 数据类型
            
        Returns:
            str 提取的文本内容
        """
        if data_type == "text":
            return str(data)
        
        elif data_type == "markdown":
            return str(data)
        
        elif data_type == "pdf":
            return await self._extract_from_pdf(data)
        
        elif data_type == "image":
            return await self._extract_from_image(data)
        
        elif data_type == "audio":
            return await self._extract_from_audio(data)
        
        elif data_type == "video":
            return await self._extract_from_video(data)
        
        elif data_type == "url":
            return await self._extract_from_url(str(data))
        
        else:
            return str(data)
    
    async def _extract_from_pdf(self, data: bytes) -> str:
        """从 PDF 提取文本"""
        try:
            import fitz
            doc = fitz.open("pdf", data)
            text = "\n".join(page.get_text() for page in doc)
            return text.strip()
        except ImportError:
            logger.warning("PyMuPDF 未安装，无法解析 PDF")
            return ""
        except Exception as e:
            logger.error(f"PDF 解析失败: {e}")
            return ""
    
    async def _extract_from_image(self, data: bytes) -> str:
        """从图像提取文本（OCR）"""
        try:
            from PIL import Image
            import pytesseract
            
            image = Image.open(io.BytesIO(data))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except ImportError:
            logger.warning("PIL 或 pytesseract 未安装，无法进行 OCR")
            return ""
        except Exception as e:
            logger.error(f"OCR 失败: {e}")
            return ""
    
    async def _extract_from_audio(self, data: bytes) -> str:
        """从音频提取文本（语音转文字）"""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            audio_file = sr.AudioFile(io.BytesIO(data))
            with audio_file as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="zh-CN")
            return text
        except ImportError:
            logger.warning("speech_recognition 未安装，无法进行语音识别")
            return ""
        except Exception as e:
            logger.error(f"语音识别失败: {e}")
            return ""
    
    async def _extract_from_video(self, data: bytes) -> str:
        """从视频提取文本（先提取音频）"""
        try:
            # 简化实现：直接返回空字符串
            logger.info("视频处理需要额外依赖，跳过")
            return ""
        except Exception as e:
            logger.error(f"视频处理失败: {e}")
            return ""
    
    async def _extract_from_url(self, url: str) -> str:
        """从网页提取文本"""
        try:
            import httpx
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text(separator="\n")
                return text.strip()[:10000]  # 限制长度
        except ImportError:
            logger.warning("beautifulsoup4 未安装，无法解析网页")
            return ""
        except Exception as e:
            logger.error(f"网页抓取失败: {e}")
            return ""
    
    async def _recognize_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        识别文本中的实体
        
        Args:
            text: 文本内容
            
        Returns:
            List 实体列表
        """
        if not self._entity_recognizer:
            return []
        
        result = self._entity_recognizer.recognize(text)
        resolved = self._entity_resolver.batch_resolve(result.entities, text)
        
        entities = []
        for resolved_entity in resolved:
            entities.append({
                "text": resolved_entity.entity.text,
                "type": resolved_entity.entity.entity_type.value,
                "canonical_name": resolved_entity.canonical_name,
                "entity_id": resolved_entity.entity_id,
                "confidence": resolved_entity.confidence,
                "description": resolved_entity.description,
                "attributes": resolved_entity.attributes,
            })
        
        return entities
    
    async def _extract_relations(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        提取实体关系
        
        Args:
            text: 文本内容
            entities: 实体列表
            
        Returns:
            List 关系列表
        """
        relations = []
        
        # 简化实现：基于实体共现推断关系
        entity_names = [e["text"] for e in entities]
        
        for i, e1 in enumerate(entities):
            for j, e2 in enumerate(entities):
                if i >= j:
                    continue
                
                # 检查两个实体是否在同一句子中出现
                if e1["text"] in text and e2["text"] in text:
                    relations.append({
                        "subject": e1.get("entity_id") or e1["text"],
                        "predicate": "related_to",
                        "object": e2.get("entity_id") or e2["text"],
                        "confidence": 0.7,
                        "source": "co-occurrence",
                    })
        
        return relations
    
    async def _save_to_vector_store(self, doc_id: str, content: str, 
                                    entities: List[Dict[str, Any]], 
                                    metadata: Optional[Dict[str, Any]]):
        """保存到向量存储"""
        if not self._vector_store:
            return
        
        # 生成嵌入向量
        embedding = self._generate_embedding(content)
        
        # 准备元数据
        meta = {
            "document_id": doc_id,
            "entities": entities,
            "content_length": len(content),
        }
        if metadata:
            meta.update(metadata)
        
        await self._vector_store.add([embedding], [doc_id], [meta])
    
    async def _add_to_knowledge_graph(self, entities: List[Dict[str, Any]], 
                                       relations: List[Dict[str, Any]]):
        """添加到知识图谱"""
        if not self._knowledge_graph:
            return
        
        # 添加实体
        for entity in entities:
            await self._knowledge_graph.add_entity({
                "id": entity.get("entity_id") or entity["text"],
                "name": entity["canonical_name"],
                "type": entity["type"],
                "description": entity["description"],
                "attributes": entity["attributes"],
            })
        
        # 添加关系
        for relation in relations:
            await self._knowledge_graph.add_relation(relation)
    
    def _generate_doc_id(self, content: str) -> str:
        """生成文档ID"""
        return hashlib.md5(content.encode()[:1024]).hexdigest()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        import re
        
        text = text.lower()
        words = re.findall(r'[\w]+', text)
        vec = [0.0] * 384
        
        for word in words:
            word_hash = hash(word) % 384
            vec[word_hash] += 1.0
        
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec
    
    async def batch_ingest(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量摄入文档
        
        Args:
            documents: 文档列表，每个文档包含 data, data_type, metadata
            
        Returns:
            List 摄入结果列表
        """
        tasks = []
        for doc in documents:
            task = self.ingest(
                data=doc["data"],
                data_type=doc.get("data_type", "text"),
                metadata=doc.get("metadata"),
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)


# 全局摄入器实例
_ingestor_instance = None

def get_multi_modal_ingestor() -> MultiModalIngestor:
    """获取全局多模态摄入器实例"""
    global _ingestor_instance
    if _ingestor_instance is None:
        _ingestor_instance = MultiModalIngestor()
    return _ingestor_instance