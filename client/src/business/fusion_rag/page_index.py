"""
PageIndex - 无向量倒排索引系统

参考 PageIndex 设计理念，提供：
1. 层次化文档索引（按页/段落组织）
2. 倒排索引支持快速关键词检索
3. 位置感知检索（支持邻近查询）
4. 增量更新能力
5. 多维度元数据过滤

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import re
import threading
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from loguru import logger


class PageIndex:
    """层次化文档索引 - 类似 PageIndex 的无向量检索系统"""
    
    def __init__(self):
        # 页面存储: page_id -> {content, metadata, position}
        self.pages: Dict[str, Dict] = {}
        
        # 倒排索引: term -> [(page_id, position_score)]
        self.inverted_index: Dict[str, List[Tuple[str, float]]] = {}
        
        # 文档索引: doc_id -> [page_ids]
        self.document_index: Dict[str, List[str]] = {}
        
        # 元数据索引: meta_key -> value -> [page_ids]
        self.metadata_index: Dict[str, Dict[str, List[str]]] = {}
        
        # 统计信息
        self.stats = {
            "total_pages": 0,
            "total_terms": 0,
            "total_documents": 0,
            "query_count": 0,
            "hit_count": 0
        }
        
        self.lock = threading.RLock()
        logger.info("PageIndex 初始化完成")
    
    def _tokenize(self, text: str) -> List[str]:
        """中英文分词"""
        text = text.lower()
        # 匹配中文和英文单词
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        # 过滤短词
        words = [w for w in words if len(w) >= 2]
        return words
    
    def _calculate_position_score(self, position: int, total_pages: int) -> float:
        """计算位置分数（靠前的页面权重更高）"""
        return max(0.1, 1.0 - (position / total_pages) * 0.5)
    
    def add_document(self, doc_id: str, content: str, metadata: Optional[Dict] = None):
        """
        添加文档到索引
        
        Args:
            doc_id: 文档唯一标识
            content: 文档内容
            metadata: 元数据字典
        """
        with self.lock:
            # 按段落分割页面
            pages = self._split_content(content)
            total_pages = len(pages)
            
            # 记录文档的页面列表
            self.document_index[doc_id] = []
            
            for page_num, page_content in enumerate(pages):
                page_id = f"{doc_id}__page_{page_num}"
                
                # 存储页面信息
                self.pages[page_id] = {
                    "content": page_content,
                    "metadata": metadata or {},
                    "position": page_num,
                    "total_pages": total_pages,
                    "parent_doc": doc_id
                }
                
                # 添加到文档索引
                self.document_index[doc_id].append(page_id)
                
                # 更新倒排索引
                position_score = self._calculate_position_score(page_num, total_pages)
                terms = self._tokenize(page_content)
                
                for term in terms:
                    if term not in self.inverted_index:
                        self.inverted_index[term] = []
                    # 添加 (page_id, position_score)
                    if page_id not in [p[0] for p in self.inverted_index[term]]:
                        self.inverted_index[term].append((page_id, position_score))
                
                # 更新元数据索引
                if metadata:
                    for key, value in metadata.items():
                        if key not in self.metadata_index:
                            self.metadata_index[key] = {}
                        if value not in self.metadata_index[key]:
                            self.metadata_index[key][value] = []
                        if page_id not in self.metadata_index[key][value]:
                            self.metadata_index[key][value].append(page_id)
            
            # 更新统计
            self.stats["total_pages"] += len(pages)
            self.stats["total_terms"] = len(self.inverted_index)
            self.stats["total_documents"] += 1
            
            logger.debug(f"文档 {doc_id} 已索引，共 {len(pages)} 页")
    
    def _split_content(self, content: str) -> List[str]:
        """按段落分割内容"""
        # 按换行符或段落标记分割
        paragraphs = re.split(r'\n\n+|\r\n\r\n+', content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # 如果段落过长，进一步分割
        result = []
        for para in paragraphs:
            if len(para) > 512:
                # 按句子分割
                sentences = re.split(r'[。！？.!?]+', para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) < 512:
                        current += sent
                    else:
                        if current:
                            result.append(current)
                        current = sent
                if current:
                    result.append(current)
            else:
                result.append(para)
        
        return result
    
    def update_document(self, doc_id: str, content: str, metadata: Optional[Dict] = None):
        """更新文档（先删除再添加）"""
        self.delete_document(doc_id)
        self.add_document(doc_id, content, metadata)
    
    def delete_document(self, doc_id: str):
        """删除文档"""
        with self.lock:
            if doc_id not in self.document_index:
                return
            
            # 获取所有页面 ID
            page_ids = self.document_index[doc_id]
            
            # 从页面存储中删除
            for page_id in page_ids:
                if page_id in self.pages:
                    del self.pages[page_id]
            
            # 从倒排索引中删除
            for term in list(self.inverted_index.keys()):
                self.inverted_index[term] = [
                    (pid, score) for pid, score in self.inverted_index[term]
                    if pid not in page_ids
                ]
                if not self.inverted_index[term]:
                    del self.inverted_index[term]
            
            # 从元数据索引中删除
            for key in list(self.metadata_index.keys()):
                for value in list(self.metadata_index[key].keys()):
                    self.metadata_index[key][value] = [
                        pid for pid in self.metadata_index[key][value]
                        if pid not in page_ids
                    ]
                    if not self.metadata_index[key][value]:
                        del self.metadata_index[key][value]
                if not self.metadata_index[key]:
                    del self.metadata_index[key]
            
            # 删除文档索引
            del self.document_index[doc_id]
            
            # 更新统计
            self.stats["total_pages"] -= len(page_ids)
            self.stats["total_terms"] = len(self.inverted_index)
            self.stats["total_documents"] -= 1
            
            logger.debug(f"文档 {doc_id} 已删除")
    
    def search(self, query: str, top_k: int = 10, filters: Optional[Dict] = None) -> List[Dict]:
        """
        搜索查询
        
        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 元数据过滤器
        
        Returns:
            搜索结果列表
        """
        with self.lock:
            self.stats["query_count"] += 1
            
            query_terms = self._tokenize(query)
            if not query_terms:
                return []
            
            # 收集候选页面
            candidate_scores: Dict[str, float] = defaultdict(float)
            
            for term in query_terms:
                if term in self.inverted_index:
                    for page_id, position_score in self.inverted_index[term]:
                        # 词频加分 + 位置加分
                        candidate_scores[page_id] += (1.0 + position_score)
            
            # 应用元数据过滤
            if filters:
                for key, value in filters.items():
                    if key in self.metadata_index and value in self.metadata_index[key]:
                        valid_pages = set(self.metadata_index[key][value])
                        candidate_scores = {
                            pid: score for pid, score in candidate_scores.items()
                            if pid in valid_pages
                        }
            
            # 排序并返回
            sorted_results = sorted(
                candidate_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_k]
            
            results = []
            for page_id, score in sorted_results:
                if page_id in self.pages:
                    page = self.pages[page_id]
                    results.append({
                        "page_id": page_id,
                        "doc_id": page["parent_doc"],
                        "content": page["content"],
                        "metadata": page["metadata"],
                        "score": score,
                        "position": page["position"]
                    })
            
            if results:
                self.stats["hit_count"] += 1
            
            logger.debug(f"搜索 '{query}' 返回 {len(results)} 条结果")
            return results
    
    def search_with_proximity(self, query: str, window_size: int = 3, top_k: int = 10) -> List[Dict]:
        """
        邻近搜索 - 查找包含多个关键词且位置相近的页面
        
        Args:
            query: 查询文本
            window_size: 邻近窗口大小
            top_k: 返回数量
        
        Returns:
            搜索结果列表
        """
        with self.lock:
            query_terms = self._tokenize(query)
            if len(query_terms) < 2:
                return self.search(query, top_k)
            
            # 找到包含所有关键词的页面
            common_pages = None
            for term in query_terms:
                if term in self.inverted_index:
                    term_pages = set(p[0] for p in self.inverted_index[term])
                    if common_pages is None:
                        common_pages = term_pages
                    else:
                        common_pages.intersection_update(term_pages)
            
            if not common_pages:
                return []
            
            # 计算邻近分数
            results = []
            for page_id in common_pages:
                if page_id in self.pages:
                    content = self.pages[page_id]["content"].lower()
                    
                    # 找到所有关键词的位置
                    positions = []
                    for term in query_terms:
                        idx = content.find(term)
                        if idx != -1:
                            positions.append(idx)
                    
                    if positions:
                        # 计算位置分散度（越小越好）
                        min_pos = min(positions)
                        max_pos = max(positions)
                        spread = max_pos - min_pos
                        
                        # 邻近分数：分散度越小分数越高
                        proximity_score = max(0, 1.0 - spread / (len(content) + 1))
                        
                        results.append({
                            "page_id": page_id,
                            "doc_id": self.pages[page_id]["parent_doc"],
                            "content": self.pages[page_id]["content"],
                            "metadata": self.pages[page_id]["metadata"],
                            "score": proximity_score,
                            "position": self.pages[page_id]["position"],
                            "proximity_spread": spread
                        })
            
            # 按邻近分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
    
    def get_document_pages(self, doc_id: str) -> List[Dict]:
        """获取文档的所有页面"""
        if doc_id not in self.document_index:
            return []
        
        pages = []
        for page_id in self.document_index[doc_id]:
            if page_id in self.pages:
                pages.append(self.pages[page_id])
        
        return sorted(pages, key=lambda x: x["position"])
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self.stats.copy()
    
    def clear(self):
        """清空索引"""
        with self.lock:
            self.pages.clear()
            self.inverted_index.clear()
            self.document_index.clear()
            self.metadata_index.clear()
            self.stats = {
                "total_pages": 0,
                "total_terms": 0,
                "total_documents": 0,
                "query_count": 0,
                "hit_count": 0
            }
            logger.info("PageIndex 已清空")