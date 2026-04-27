"""
迁移训练器 (Transfer Trainer)
==============================

支持:
1. 领域适配训练
2. 联合训练 (Joint Training)
3. 微调 (Fine-tuning)
"""

import random
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class TransferTrainer:
    """
    迁移训练器
    
    协调源领域和目标领域数据，训练领域适配器和任务分类器。
    简化版，不依赖深度学习框架。
    """
    
    def __init__(
        self,
        model: "SimpleDomainAdapter",
        source_data: "DomainData",
        target_data: "DomainData",
        lr: float = 1e-4,
        alpha: float = 0.5,  # 领域分类损失权重
    ):
        """
        初始化迁移训练器
        
        Args:
            model: 领域适配器模型
            source_data: 源领域数据
            target_data: 目标领域数据
            lr: 学习率
            alpha: 领域对抗损失权重
        """
        self.model = model
        self.source_data = source_data
        self.target_data = target_data
        self.lr = lr
        self.alpha = alpha
        
        # 训练统计
        self.stats = {
            'epochs': 0,
            'task_losses': [],
            'domain_losses': [],
            'source_accuracy': 0.0,
            'target_accuracy': 0.0,
        }
        
        logger.info(f"[TransferTrainer] 初始化完成，α={alpha}")
    
    def train(self, epochs: int = 100, batch_size: int = 32):
        """
        训练循环
        
        Args:
            epochs: 训练轮数
            batch_size: 批次大小
        """
        logger.info(f"[TransferTrainer] 开始训练，轮数: {epochs}")
        
        for epoch in range(epochs):
            total_task_loss = 0.0
            total_domain_loss = 0.0
            n_batches = 0
            
            # 训练源领域
            self.model.train()
            for i in range(0, len(self.source_data), batch_size):
                batch_features, batch_labels = self.source_data.get_batch(batch_size)
                
                # 提取特征
                features = [self.model.extract_features(x) for x in batch_features]
                
                # 任务损失 (简化版：假设是二分类)
                task_loss = 0.0
                for h, y in zip(features, batch_labels):
                    pred = self.model.domain_predict(h)
                    task_loss += (pred - y) ** 2
                
                # 领域分类损失 (希望分类器无法区分)
                domain_loss = 0.0
                for h in features:
                    domain_pred = self.model.domain_predict(h)
                    # 希望输出接近 0.5 (无法区分)
                    domain_loss += (domain_pred - 0.5) ** 2
                
                # 总损失
                total_loss = task_loss + self.alpha * domain_loss
                total_task_loss += task_loss
                total_domain_loss += domain_loss
                n_batches += 1
                
                # 反向传播 (简化版)
                # 实际应该调用 model.backward()
                pass  # 简化版跳过
            
            # 训练目标领域 (领域分类器)
            for i in range(0, len(self.target_data), batch_size):
                batch_features, _ = self.target_data.get_batch(batch_size)
                
                # 提取特征
                features = [self.model.extract_features(x) for x in batch_features]
                
                # 领域分类损失 (希望分类器能区分)
                domain_loss = 0.0
                for h in features:
                    domain_pred = self.model.domain_predict(h)
                    # 希望输出接近 1.0 (目标领域)
                    domain_loss += (domain_pred - 1.0) ** 2
                
                total_domain_loss += domain_loss
                n_batches += 1
            
            # 记录统计
            avg_task_loss = total_task_loss / max(1, n_batches)
            avg_domain_loss = total_domain_loss / max(1, n_batches)
            
            self.stats['task_losses'].append(avg_task_loss)
            self.stats['domain_losses'].append(avg_domain_loss)
            
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"[TransferTrainer] Epoch {epoch+1}/{epochs}, "
                    f"Task Loss: {avg_task_loss:.4f}, "
                    f"Domain Loss: {avg_domain_loss:.4f}"
                )
                print(
                    f"Epoch {epoch+1}/{epochs}, "
                    f"Task Loss: {avg_task_loss:.4f}, "
                    f"Domain Loss: {avg_domain_loss:.4f}"
                )
        
        self.stats['epochs'] = epochs
        logger.info("[TransferTrainer] 训练完成")
        print("Transfer learning completed!")
    
    def evaluate(self, data: "DomainData", is_target: bool = True) -> float:
        """
        评估模型
        
        Args:
            data: 评估数据
            is_target: 是否是目标领域
            
        Returns:
            准确率 (简化版)
        """
        self.model.eval()
        
        correct = 0
        total = len(data)
        
        for x, y in zip(data.features, data.labels or []):
            features = self.model.extract_features(x)
            pred = self.model.domain_predict(features)
            
            # 简化：假设 pred > 0.5 预测为 1
            pred_label = 1 if pred > 0.5 else 0
            if pred_label == y:
                correct += 1
        
        accuracy = correct / total if total > 0 else 0.0
        
        if is_target:
            self.stats['target_accuracy'] = accuracy
        else:
            self.stats['source_accuracy'] = accuracy
        
        logger.info(f"[TransferTrainer] 评估准确率: {accuracy:.2%}")
        return accuracy
    
    def fine_tune(self, target_data: "DomainData", epochs: int = 10, lr: float = None):
        """
        微调 (Fine-tuning)
        
        Args:
            target_data: 目标领域数据
            epochs: 微调轮数
            lr: 微调学习率 (None 则使用初始学习率)
        """
        fine_tune_lr = lr or self.lr
        
        logger.info(f"[TransferTrainer] 开始微调，轮数: {epochs}, LR: {fine_tune_lr}")
        
        for epoch in range(epochs):
            total_loss = 0.0
            
            for x, y in zip(target_data.features, target_data.labels or []):
                # 提取特征
                features = self.model.extract_features(x)
                
                # 任务损失
                pred = self.model.domain_predict(features)
                loss = (pred - y) ** 2
                total_loss += loss
                
                # 反向传播 (简化版)
                pass  # 简化版跳过
            
            avg_loss = total_loss / len(target_data)
            
            if (epoch + 1) % 5 == 0:
                logger.debug(f"[TransferTrainer] Fine-tune Epoch {epoch+1}, Loss: {avg_loss:.4f}")
        
        logger.info("[TransferTrainer] 微调完成")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取训练统计"""
        return self.stats.copy()


if __name__ == "__main__":
    # 简单测试
    from .domain_adapter import SimpleDomainAdapter, DomainData
    
    # 创建模拟数据
    def create_dummy_data(n_samples: int, input_dim: int, is_source: bool = True):
        features = []
        labels = []
        for _ in range(n_samples):
            x = [random.uniform(-1, 1) for _ in range(input_dim)]
            # 简化：源领域和目标领域有不同的分布
            y = 1 if sum(x) > 0 else 0
            features.append(x)
            labels.append(y)
        return DomainData(name="source" if is_source else "target", 
                        features=features, labels=labels)
    
    input_dim = 10
    hidden_dim = 64
    
    # 创建模型和数据
    model = SimpleDomainAdapter(input_dim=input_dim, hidden_dim=hidden_dim)
    source_data = create_dummy_data(100, input_dim, is_source=True)
    target_data = create_dummy_data(50, input_dim, is_source=False)
    
    # 创建训练器
    trainer = TransferTrainer(model, source_data, target_data, lr=1e-4)
    
    # 训练
    trainer.train(epochs=50, batch_size=32)
    
    # 评估
    source_acc = trainer.evaluate(source_data, is_target=False)
    target_acc = trainer.evaluate(target_data, is_target=True)
    
    print(f"源领域准确率: {source_acc:.2%}")
    print(f"目标领域准确率: {target_acc:.2%}")
