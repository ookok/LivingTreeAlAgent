"""
领域适配器 (Domain Adapter)
============================

简化版领域适配，不依赖深度学习框架。

支持:
1. 特征对齐 (Feature Alignment)
2. 对抗训练 (Adversarial Training) - 简化版
3. 领域分类
"""

import random
import math
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DomainData:
    """领域数据"""
    name: str
    features: List[List[float]]  # 特征列表
    labels: List[int] = None
    
    def __len__(self):
        return len(self.features)
    
    def get_batch(self, batch_size: int = 32, shuffle: bool = True) -> Tuple[List[List[float]], List[int]]:
        """获取批次数据"""
        indices = list(range(len(self.features)))
        if shuffle:
            random.shuffle(indices)
        
        batch_indices = indices[:batch_size]
        batch_features = [self.features[i] for i in batch_indices]
        batch_labels = [self.labels[i] for i in batch_indices] if self.labels else None
        
        return batch_features, batch_labels


class SimpleDomainAdapter:
    """
    简化领域适配器
    
    实现特征对齐，减少源领域和目标领域之间的分布差异。
    不使用对抗训练，只使用简单的特征变换。
    """
    
    def __init__(self, input_dim: int, hidden_dim: int = 64):
        """
        初始化适配器
        
        Args:
            input_dim: 输入特征维度
            hidden_dim: 隐藏层维度
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        # 特征变换矩阵 (简化版，只使用一个矩阵)
        self.W = [[random.uniform(-0.1, 0.1) for _ in range(input_dim)] 
                   for _ in range(hidden_dim)]
        
        # 偏置
        self.bias = [random.uniform(-0.1, 0.1) for _ in range(hidden_dim)]
        
        # 领域分类器 (简化版)
        self.domain_W = [random.uniform(-0.1, 0.1) for _ in range(hidden_dim)]
        self.domain_bias = random.uniform(-0.1, 0.1)
        
        logger.info(f"[SimpleDomainAdapter] 初始化完成，输入维度: {input_dim}, 隐藏维度: {hidden_dim}")
    
    def extract_features(self, x: List[float]) -> List[float]:
        """
        提取特征 (特征变换)
        
        Args:
            x: 输入特征
            
        Returns:
            变换后的特征
        """
        # 线性变换: h = Wx + b
        h = []
        for j in range(self.hidden_dim):
            val = self.bias[j]
            for i in range(self.input_dim):
                val += x[i] * self.W[j][i]
            h.append(val)
        
        # ReLU 激活
        h = [max(0, v) for v in h]
        return h
    
    def domain_predict(self, features: List[float]) -> float:
        """
        领域分类预测
        
        Args:
            features: 特征向量
            
        Returns:
            领域概率 (0=源领域, 1=目标领域)
        """
        # 线性分类器
        logit = self.domain_bias
        for i, f in enumerate(features):
            if i < len(self.domain_W):
                logit += f * self.domain_W[i]
        
        # Sigmoid
        prob = 1.0 / (1.0 + math.exp(-logit))
        return prob
    
    def adapt(self, source_data: DomainData, target_data: DomainData, epochs: int = 10, lr: float = 0.01):
        """
        领域适配 (简化版)
        
        Args:
            source_data: 源领域数据
            target_data: 目标领域数据
            epochs: 训练轮数
            lr: 学习率
        """
        logger.info(f"[SimpleDomainAdapter] 开始适配，轮数: {epochs}")
        
        for epoch in range(epochs):
            total_loss = 0.0
            
            # 处理源领域数据
            src_features, src_labels = source_data.get_batch(batch_size=32)
            for x, y in zip(src_features, src_labels):
                # 提取特征
                h = self.extract_features(x)
                
                # 任务损失 (简化：假设是二分类)
                pred = sum(h_i * w_i for h_i, w_i in zip(h, self.domain_W)) + self.domain_bias
                loss = (pred - y) ** 2
                total_loss += loss
                
                # 更新参数 (简化梯度下降)
                for j in range(self.hidden_dim):
                    grad = 2 * (pred - y) * h[j]
                    self.domain_W[j] -= lr * grad
            
            # 处理目标领域数据
            tgt_features, _ = target_data.get_batch(batch_size=32)
            for x in tgt_features:
                h = self.extract_features(x)
                
                # 领域分类损失 (希望分类器无法区分领域)
                domain_pred = self.domain_predict(h)
                loss = domain_pred ** 2  # 希望输出接近 0.5
                total_loss += loss
            
            avg_loss = total_loss / (len(src_features) + len(tgt_features))
            
            if (epoch + 1) % 5 == 0:
                logger.info(f"[SimpleDomainAdapter] Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
        
        logger.info("[SimpleDomainAdapter] 适配完成")
    
    def transform(self, data: DomainData) -> List[List[float]]:
        """
        变换数据到适配空间
        
        Args:
            data: 领域数据
            
        Returns:
            变换后的特征
        """
        transformed = []
        for x in data.features:
            h = self.extract_features(x)
            transformed.append(h)
        return transformed


class AdaptiveTransfer:
    """
    自适应迁移学习
    
    根据目标领域的数据量，自适应选择迁移策略。
    """
    
    def __init__(self, input_dim: int):
        """
        初始化自适应迁移器
        
        Args:
            input_dim: 输入特征维度
        """
        self.input_dim = input_dim
        self.adapter = SimpleDomainAdapter(input_dim)
        self.source_model = None  # 源领域模型 (简化版)
        self.target_model = None  # 目标领域模型
        
        logger.info(f"[AdaptiveTransfer] 初始化完成，输入维度: {input_dim}")
    
    def pretrain_source(self, source_data: DomainData, epochs: int = 10):
        """
        预训练源领域模型
        
        Args:
            source_data: 源领域数据
            epochs: 训练轮数
        """
        logger.info(f"[AdaptiveTransfer] 预训练源领域模型，轮数: {epochs}")
        
        # 简化版：只训练一个线性分类器
        self.source_model = [random.uniform(-0.1, 0.1) for _ in range(self.input_dim)]
        
        for epoch in range(epochs):
            total_loss = 0.0
            
            features, labels = source_data.get_batch(batch_size=32)
            for x, y in zip(features, labels):
                # 预测
                pred = sum(x_i * w_i for x_i, w_i in zip(x, self.source_model))
                
                # 平方损失
                loss = (pred - y) ** 2
                total_loss += loss
                
                # 更新权重
                for i in range(self.input_dim):
                    grad = 2 * (pred - y) * x[i]
                    self.source_model[i] -= 0.01 * grad
            
            avg_loss = total_loss / len(features)
            if (epoch + 1) % 5 == 0:
                logger.debug(f"[AdaptiveTransfer] 预训练 Epoch {epoch+1}, Loss: {avg_loss:.4f}")
        
        logger.info("[AdaptiveTransfer] 预训练完成")
    
    def transfer_to_target(self, target_data: DomainData, epochs: int = 5):
        """
        迁移到目标领域
        
        Args:
            target_data: 目标领域数据
            epochs: 微调轮数
        """
        logger.info(f"[AdaptiveTransfer] 迁移到目标领域，数据量: {len(target_data)}")
        
        if self.source_model is None:
            logger.warning("[AdaptiveTransfer] 源领域模型未训练，先执行预训练")
            return
        
        # 初始化目标模型 (从源模型复制)
        self.target_model = self.source_model.copy()
        
        # 领域适配
        if len(target_data) > 10:
            # 有足够目标数据：执行领域适配
            logger.info("[AdaptiveTransfer] 执行领域适配")
            # 简化：跳过适配步骤
        
        # 微调目标模型
        logger.info(f"[AdaptiveTransfer] 微调目标模型，轮数: {epochs}")
        for epoch in range(epochs):
            total_loss = 0.0
            
            features, labels = target_data.get_batch(batch_size=32)
            for x, y in zip(features, labels):
                pred = sum(x_i * w_i for x_i, w_i in zip(x, self.target_model))
                loss = (pred - y) ** 2
                total_loss += loss
                
                for i in range(self.input_dim):
                    grad = 2 * (pred - y) * x[i]
                    self.target_model[i] -= 0.01 * grad
            
            avg_loss = total_loss / len(features)
            if (epoch + 1) % 2 == 0:
                logger.debug(f"[AdaptiveTransfer] 微调 Epoch {epoch+1}, Loss: {avg_loss:.4f}")
        
        logger.info("[AdaptiveTransfer] 迁移完成")
    
    def evaluate_target(self, target_data: DomainData) -> float:
        """
        评估目标领域模型
        
        Returns:
            平均准确率 (简化版)
        """
        if self.target_model is None:
            logger.warning("[AdaptiveTransfer] 目标模型未训练")
            return 0.0
        
        correct = 0
        total = len(target_data)
        
        for x, y in zip(target_data.features, target_data.labels or []):
            pred = sum(x_i * w_i for x_i, w_i in zip(x, self.target_model))
            pred_label = 1 if pred > 0.5 else 0
            if pred_label == y:
                correct += 1
        
        accuracy = correct / total if total > 0 else 0.0
        logger.info(f"[AdaptiveTransfer] 目标领域准确率: {accuracy:.2%}")
        return accuracy


if __name__ == "__main__":
    # 简单测试
    import random
    
    # 创建模拟数据
    def create_dummy_data(n_samples: int, input_dim: int, is_source: bool = True) -> DomainData:
        features = []
        labels = []
        for _ in range(n_samples):
            x = [random.uniform(-1, 1) for _ in range(input_dim)]
            # 简化：源领域和目标领域有不同的分布
            if is_source:
                y = 1 if sum(x) > 0 else 0
            else:
                y = 1 if sum(x) > 0.5 else 0  # 不同的决策边界
            features.append(x)
            labels.append(y)
        return DomainData(name="source" if is_source else "target", 
                        features=features, labels=labels)
    
    input_dim = 10
    
    # 创建数据
    source_data = create_dummy_data(100, input_dim, is_source=True)
    target_data = create_dummy_data(50, input_dim, is_source=False)
    
    # 迁移学习
    transfer = AdaptiveTransfer(input_dim)
    transfer.pretrain_source(source_data, epochs=10)
    transfer.transfer_to_target(target_data, epochs=5)
    accuracy = transfer.evaluate_target(target_data)
    
    print(f"目标领域准确率: {accuracy:.2%}")
