"""
文档 QA 测试脚本

测试基于单个文档的提问和回答功能
"""

import os
import sys
import asyncio
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_document_qa():
    """测试文档 QA 功能"""
    logger.info("=== 测试文档 QA 功能 ===")
    
    try:
        # 导入文档 QA 模块
        from core.living_tree_ai.knowledge.document_qa import DocumentQA, DocumentQAConfig
        
        # 创建文档 QA 实例
        config = DocumentQAConfig(
            embedding_model="text-embedding-ada-002",
            llm_model="gpt-4o",
            temperature=0.7,
            top_k=3
        )
        
        qa = DocumentQA(config)
        
        # 创建测试文本
        test_text = """
        人工智能（Artificial Intelligence，简称 AI）是指由人制造出来的机器所表现出来的智能。
        人工智能的发展可以分为几个阶段：
        1. 早期阶段（1950s-1970s）：符号主义 AI，基于规则和逻辑
        2. 中期阶段（1980s-1990s）：机器学习的兴起，特别是神经网络
        3. 现代阶段（2000s-至今）：深度学习的突破，如卷积神经网络和Transformer
        
        人工智能的应用领域包括：
        - 自然语言处理
        - 计算机视觉
        - 语音识别
        - 自动驾驶
        - 医疗诊断
        - 金融分析
        
        人工智能的挑战包括：
        - 数据隐私
        - 伦理问题
        - 就业影响
        - 算法偏见
        """
        
        # 加载文本
        logger.info("加载测试文本...")
        success = qa.load_text(test_text, source="test_ai.txt")
        
        if not success:
            logger.error("加载文本失败")
            return
        
        logger.info("文本加载成功")
        
        # 测试查询
        test_questions = [
            "人工智能的定义是什么？",
            "人工智能的发展阶段有哪些？",
            "人工智能的应用领域包括什么？",
            "人工智能面临哪些挑战？"
        ]
        
        for question in test_questions:
            logger.info(f"\n查询: {question}")
            result = qa.query(question)
            
            if result:
                logger.info(f"回答: {result.answer}")
                logger.info(f"处理时间: {result.processing_time:.2f} 秒")
                logger.info(f"置信度: {result.confidence:.2f}")
                
                if result.sources:
                    logger.info("来源:")
                    for i, source in enumerate(result.sources):
                        logger.info(f"  {i+1}. {source['content'][:100]}...")
            else:
                logger.error("查询失败")
        
        # 测试保存和加载索引
        logger.info("\n测试保存和加载索引...")
        index_path = "test_qa_index"
        
        # 保存索引
        qa.save_index(index_path)
        logger.info("索引保存成功")
        
        # 创建新实例并加载索引
        new_qa = DocumentQA(config)
        new_qa.load_index(index_path)
        logger.info("索引加载成功")
        
        # 测试加载后的查询
        test_question = "人工智能的应用领域有哪些？"
        logger.info(f"\n测试加载索引后的查询: {test_question}")
        result = new_qa.query(test_question)
        
        if result:
            logger.info(f"回答: {result.answer}")
        else:
            logger.error("查询失败")
        
        # 清理测试文件
        import shutil
        if os.path.exists(index_path):
            shutil.rmtree(index_path)
            logger.info("测试索引清理成功")
        
        logger.info("\n文档 QA 测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_document_qa()
