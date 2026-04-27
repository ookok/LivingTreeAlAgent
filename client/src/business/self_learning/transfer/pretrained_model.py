"""
预训练模型适配器 (Pre-trained Model Adapter)
=============================================

简化版 CodeBERT 适配器，不依赖外部库。

支持:
1. 代码特征提取
2. 微调 (Fine-tuning)
3. 特征迁移
"""

import random
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CodeBERTAdapter:
    """
    简化版 CodeBERT 适配器
    
    不使用真实的 CodeBERT 模型，而是模拟其特征提取和分类能力。
    生产环境建议使用:
    - transformers 库的 AutoModelForSequenceClassification
    - 真实的 CodeBERT/GraphCodeBERT 模型
    """
    
    model_name: str = "codebert-base"
    hidden_size: int = 768  # CodeBERT 隐藏层大小
    num_labels: int = 5  # 分类数: refactor/optimize/fix/feature/test
    
    def __post_init__(self):
        """初始化后处理"""
        # 模拟加载预训练模型
        self.tokenizer_vocab = self._build_dummy_tokenizer()
        self.embeddings = self._build_dummy_embeddings()
        
        # 分类头 (简化版)
        self.classifier_weights = [[random.uniform(-0.1, 0.1) for _ in range(self.hidden_size)]
                                   for _ in range(self.num_labels)]
        self.classifier_bias = [random.uniform(-0.1, 0.1) for _ in range(self.num_labels)]
        
        # 冻结底层 (简化版：只训练分类头)
        self.frozen = True
        
        logger.info(f"[CodeBERTAdapter] 初始化完成，模型: {self.model_name}, 隐藏大小: {self.hidden_size}")
    
    def _build_dummy_tokenizer(self) -> Dict[str, int]:
        """构建模拟 tokenizer (简化版)"""
        # 真实情况应该使用: AutoTokenizer.from_pretrained(model_name)
        vocab = {}
        for i in range(30000):  # CodeBERT 词表大小约 30k
            vocab[f"token_{i}"] = i
        return vocab
    
    def _build_dummy_embeddings(self) -> List[List[float]]:
        """构建模拟 embeddings (简化版)"""
        # 真实情况应该加载预训练权重
        embeddings = []
        for _ in range(30000):
            emb = [random.uniform(-0.1, 0.1) for _ in range(self.hidden_size)]
            embeddings.append(emb)
        return embeddings
    
    def tokenize(self, code_snippet: str) -> List[int]:
        """
        代码分词
        
        Args:
            code_snippet: 代码片段
            
        Returns:
            token IDs 列表
        """
        # 简化版：按空格分词，然后映射到随机 ID
        tokens = code_snippet.split()
        token_ids = [hash(token) % 30000 for token in tokens]
        return token_ids[:512]  # 截断到最大长度
    
    def extract_features(self, code_snippet: str) -> List[float]:
        """
        提取代码特征 (获取 [CLS] token 的输出)
        
        Args:
            code_snippet: 代码片段
            
        Returns:
            特征向量 (hidden_size 维)
        """
        # 分词
        token_ids = self.tokenize(code_snippet)
        
        if not token_ids:
            return [0.0] * self.hidden_size
        
        # 简化版：平均 embeddings (真实情况应该使用 Transformer 编码器)
        feature_vector = [0.0] * self.hidden_size
        for token_id in token_ids:
            if token_id < len(self.embeddings):
                emb = self.embeddings[token_id]
                for i in range(self.hidden_size):
                    feature_vector[i] += emb[i]
        
        # 平均
        for i in range(self.hidden_size):
            feature_vector[i] /= len(token_ids)
        
        logger.debug(f"[CodeBERTAdapter] 提取特征完成，维度: {len(feature_vector)}")
        return feature_vector
    
    def forward(self, code_snippets: List[str], labels: Optional[List[int]] = None) -> Any:
        """
        前向传播
        
        Args:
            code_snippets: 代码片段列表
            labels: 标签列表 (可选)
            
        Returns:
            (loss, logits) 或 logits
        """
        batch_features = [self.extract_features(code) for code in code_snippets]
        
        # 分类头
        logits_list = []
        for features in batch_features:
            logits = []
            for c in range(self.num_labels):
                score = self.classifier_bias[c]
                for i in range(self.hidden_size):
                    score += features[i] * self.classifier_weights[c][i]
                logits.append(score)
            logits_list.append(logits)
        
        # 如果提供了标签，计算损失
        if labels:
            loss = self._compute_loss(logits_list, labels)
            return loss, logits_list
        
        return logits_list
    
    def _compute_loss(self, logits_list: List[List[float]], labels: List[int]) -> float:
        """计算交叉熵损失 (简化版)"""
        total_loss = 0.0
        
        for logits, label in zip(logits_list, labels):
            # Softmax
            max_logit = max(logits)
            exp_logits = [math.exp(l - max_logit) for l in logits]
            sum_exp = sum(exp_logits)
            probs = [e / sum_exp for e in exp_logits]
            
            # 交叉熵
            if label < len(probs):
                loss = -math.log(probs[label] + 1e-8)
                total_loss += loss
        
        return total_loss / len(logits_list)
    
    def predict(self, code_snippet: str) -> int:
        """
        预测代码类别
        
        Args:
            code_snippet: 代码片段
            
        Returns:
            预测类别 (0-4)
        """
        logits = self.forward([code_snippet])
        # 取 argmax
        max_logit = -float('inf')
        pred = 0
        for i, logit in enumerate(logits[0]):
            if logit > max_logit:
                max_logit = logit
                pred = i
        
        label_names = ['refactor', 'optimize', 'fix', 'feature', 'test']
        logger.debug(f"[CodeBERTAdapter] 预测: {label_names[pred]} ({pred})")
        return pred
    
    def fine_tune(self, target_data: List[Tuple[str, int]], epochs: int = 10, lr: float = 1e-4):
        """
        微调 (Fine-tuning)
        
        Args:
            target_data: 目标数据 [(code_snippet, label), ...]
            epochs: 训练轮数
            lr: 学习率
        """
        if self.frozen:
            # 解冻分类头
            logger.info("[CodeBERTAdapter] 解冻分类头，开始微调")
            self.frozen = False
        
        logger.info(f"[CodeBERTAdapter] 开始微调，数据量: {len(target_data)}, 轮数: {epochs}")
        
        for epoch in range(epochs):
            total_loss = 0.0
            
            # 打乱数据
            random.shuffle(target_data)
            
            for code, label in target_data:
                # 前向传播
                loss, logits = self.forward([code], [label])
                total_loss += loss
                
                # 反向传播 (简化版：只更新分类头)
                # 真实情况应该使用: loss.backward(), optimizer.step()
                pass  # 简化版跳过
            
            avg_loss = total_loss / len(target_data)
            
            if (epoch + 1) % 2 == 0:
                logger.info(f"[CodeBERTAdapter] Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
                print(f"Fine-tuning Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
        
        logger.info("[CodeBERTAdapter] 微调完成")
        print("Fine-tuning completed!")
    
    def save(self, path: str):
        """
        保存模型 (简化版)
        
        Args:
            path: 保存路径
        """
        # 真实情况应该使用: model.save_pretrained(path)
        logger.info(f"[CodeBERTAdapter] 保存模型到: {path} (简化版，未实际保存)")
        print(f"Model saved to {path} (simulated)")
    
    def load(self, path: str):
        """
        加载模型 (简化版)
        
        Args:
            path: 模型路径
        """
        # 真实情况应该使用: AutoModelForSequenceClassification.from_pretrained(path)
        logger.info(f"[CodeBERTAdapter] 从 {path} 加载模型 (简化版，未实际加载)")
        print(f"Model loaded from {path} (simulated)")


# 类别映射
LABEL_MAP = {
    0: "refactor",
    1: "optimize",
    2: "fix",
    3: "feature",
    4: "test",
}

LABEL_MAP_REVERSE = {v: k for k, v in LABEL_MAP.items()}


def create_coderbert_adapter(model_name: str = "codebert-base", num_labels: int = 5) -> CodeBERTAdapter:
    """
    创建 CodeBERT 适配器的工厂函数
    
    Args:
        model_name: 模型名称
        num_labels: 分类数
        
    Returns:
        CodeBERTAdapter 实例
    """
    return CodeBERTAdapter(model_name=model_name, num_labels=num_labels)


if __name__ == "__main__":
    # 简单测试
    adapter = create_coderbert_adapter()
    
    # 测试特征提取
    code = """
def add(a, b):
    return a + b
"""
    features = adapter.extract_features(code)
    print(f"特征维度: {len(features)}")
    
    # 测试预测
    pred = adapter.predict(code)
    print(f"预测类别: {LABEL_MAP[pred]}")
    
    # 测试微调
    target_data = [
        (code, LABEL_MAP_REVERSE["feature"]),
        ("def subtract(a, b): return a - b", LABEL_MAP_REVERSE["feature"]),
        ("x = 1 # TODO: fix this", LABEL_MAP_REVERSE["fix"]),
    ]
    
    adapter.fine_tune(target_data, epochs=5)
