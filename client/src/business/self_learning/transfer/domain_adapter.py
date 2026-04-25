"""
迁移学习适配器
实现领域自适应和知识迁移
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SourceDomain:
    """源领域"""
    name: str
    data: np.ndarray
    labels: Optional[np.ndarray] = None
    features: Optional[np.ndarray] = None


@dataclass
class TargetDomain:
    """目标领域"""
    name: str
    data: np.ndarray
    labels: Optional[np.ndarray] = None
    features: Optional[np.ndarray] = None


class DomainAdapter:
    """领域适配器（迁移学习）"""

    def __init__(self, adaptation_method: str = "dann"):
        """
        初始化领域适配器

        Args:
            adaptation_method: 自适应方法
                - "dann": Domain-Adversarial Neural Networks
                - "finetune": 微调
                - "instance_weighting": 实例加权
                - "feature_selection": 特征选择
        """
        self.adaptation_method = adaptation_method
        self.source_domain = None
        self.target_domain = None
        self.adapter_model = None

        logger.info(f"领域适配器初始化: method={adaptation_method}")

    def fit(self, source: SourceDomain, target: TargetDomain, **kwargs):
        """训练领域适配器"""
        self.source_domain = source
        self.target_domain = target

        if self.adaptation_method == "dann":
            return self._fit_dann(source, target, **kwargs)
        elif self.adaptation_method == "finetune":
            return self._fit_finetune(source, target, **kwargs)
        elif self.adaptation_method == "instance_weighting":
            return self._fit_instance_weighting(source, target, **kwargs)
        elif self.adaptation_method == "feature_selection":
            return self._fit_feature_selection(source, target, **kwargs)
        else:
            raise ValueError(f"不支持的方法: {self.adaptation_method}")

    def adapt(self, data: np.ndarray, from_domain: str, to_domain: str) -> np.ndarray:
        """迁移数据到目标领域"""
        if self.adapter_model is None:
            raise ValueError("适配器尚未训练")

        if self.adaptation_method == "dann":
            return self._adapt_dann(data)
        elif self.adaptation_method == "finetune":
            return self._adapt_finetune(data)
        else:
            raise ValueError(f"不支持的方法: {self.adaptation_method}")

    def evaluate_transfer(self, target_test_data: np.ndarray, target_test_labels: np.ndarray) -> Dict[str, float]:
        """评估迁移效果"""
        if self.adapter_model is None:
            raise ValueError("适配器尚未训练")

        # 在目标领域上评估
        adapted_data = self.adapt(target_test_data, "source", "target")

        # 训练分类器
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, f1_score

        classifier = LogisticRegression()
        classifier.fit(adapted_data, target_test_labels)

        predictions = classifier.predict(adapted_data)
        accuracy = accuracy_score(target_test_labels, predictions)
        f1 = f1_score(target_test_labels, predictions, average='weighted')

        return {
            'accuracy': accuracy,
            'f1_score': f1,
            'n_samples': len(target_test_data),
        }

    def _fit_dann(self, source: SourceDomain, target: TargetDomain, **kwargs) -> Dict[str, float]:
        """训练 DANN（Domain-Adversarial Neural Networks）"""
        logger.info("训练 DANN...")

        # 1. 构建 DANN 模型
        feature_extractor = nn.Sequential(
            nn.Linear(source.data.shape[1], 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
        )

        classifier = nn.Linear(128, len(np.unique(source.labels)))

        discriminator = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )

        # 2. 训练
        optimizer = torch.optim.Adam(
            list(feature_extractor.parameters()) +
            list(classifier.parameters()) +
            list(discriminator.parameters()),
            lr=kwargs.get('learning_rate', 0.001)
        )

        criterion_cls = nn.CrossEntropyLoss()
        criterion_dom = nn.BCELoss()

        n_epochs = kwargs.get('n_epochs', 100)
        batch_size = kwargs.get('batch_size', 32)

        source_tensor = torch.FloatTensor(source.data)
        source_labels = torch.LongTensor(source.labels)
        target_tensor = torch.FloatTensor(target.data)

        for epoch in range(n_epochs):
            # 批次训练
            n_batches = min(len(source.data), len(target.data)) // batch_size

            for batch in range(n_batches):
                # 1. 分类损失
                source_batch = source_tensor[batch * batch_size:(batch + 1) * batch_size]
                source_labels_batch = source_labels[batch * batch_size:(batch + 1) * batch_size]

                features = feature_extractor(source_batch)
                cls_output = classifier(features)
                loss_cls = criterion_cls(cls_output, source_labels_batch)

                # 2. 领域对抗损失
                target_batch = target_tensor[batch * batch_size:(batch + 1) * batch_size]

                source_features = feature_extractor(source_batch)
                target_features = feature_extractor(target_batch)

                # 领域标签：source=0, target=1
                domain_labels_source = torch.zeros(source_features.shape[0], 1)
                domain_labels_target = torch.ones(target_features.shape[0], 1)

                domain_output_source = discriminator(source_features)
                domain_output_target = discriminator(target_features)

                loss_dom = criterion_dom(domain_output_source, domain_labels_source) + \
                           criterion_dom(domain_output_target, domain_labels_target)

                # 3. 总损失
                loss = loss_cls - kwargs.get('lambda_dom', 0.1) * loss_dom

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{n_epochs}, Loss: {loss.item():.4f}")

        # 保存模型
        self.adapter_model = {
            'feature_extractor': feature_extractor,
            'classifier': classifier,
            'discriminator': discriminator,
        }

        return {'loss': loss.item()}

    def _adapt_dann(self, data: np.ndarray) -> np.ndarray:
        """使用 DANN 迁移数据"""
        feature_extractor = self.adapter_model['feature_extractor']
        with torch.no_grad():
            features = feature_extractor(torch.FloatTensor(data))
        return features.numpy()

    def _fit_finetune(self, source: SourceDomain, target: TargetDomain, **kwargs) -> Dict[str, float]:
        """微调（Fine-tuning）"""
        logger.info("训练 Fine-tune...")

        # 1. 在源领域预训练
        from sklearn.linear_model import LogisticRegression

        source_model = LogisticRegression()
        source_model.fit(source.data, source.labels)

        # 2. 在目标领域微调
        if target.labels is not None:
            # 有标签：全量微调
            target_model = LogisticRegression()
            target_model.fit(target.data, target.labels)
            self.adapter_model = target_model
        else:
            # 无标签：使用源模型作为初始，部分更新
            self.adapter_model = source_model

        return {'method': 'finetune', 'status': 'completed'}

    def _adapt_finetune(self, data: np.ndarray) -> np.ndarray:
        """使用微调模型预测"""
        predictions = self.adapter_model.predict(data)
        return predictions

    def _fit_instance_weighting(self, source: SourceDomain, target: TargetDomain, **kwargs) -> Dict[str, float]:
        """实例加权"""
        logger.info("训练 Instance Weighting...")

        # 1. 计算实例权重（基于密度比）
        from sklearn.neighbors import KernelDensity

        # 源领域密度
        kde_source = KernelDensity(kernel='gaussian', bandwidth=0.5)
        kde_source.fit(source.data)

        # 目标领域密度
        kde_target = KernelDensity(kernel='gaussian', bandwidth=0.5)
        kde_target.fit(target.data)

        # 密度比作为权重
        log_density_source = kde_source.score_samples(source.data)
        log_density_target = kde_target.score_samples(source.data)
        weights = np.exp(log_density_target - log_density_source)

        # 2. 使用加权逻辑回归
        from sklearn.linear_model import LogisticRegression

        weighted_model = LogisticRegression()
        # 注意：sklearn 的 sample_weight 参数
        weighted_model.fit(source.data, source.labels, sample_weight=weights)

        self.adapter_model = {
            'model': weighted_model,
            'weights': weights,
        }

        return {'method': 'instance_weighting', 'status': 'completed'}

    def _fit_feature_selection(self, source: SourceDomain, target: TargetDomain, **kwargs) -> Dict[str, float]:
        """特征选择"""
        logger.info("训练 Feature Selection...")

        # 1. 找到在源领域和目标领域都重要的特征
        from sklearn.feature_selection import mutual_info_classif

        # 源领域的特征重要性
        mi_source = mutual_info_classif(source.data, source.labels)

        # 目标领域的特征重要性（如果有标签）
        if target.labels is not None:
            mi_target = mutual_info_classif(target.data, target.labels)
            # 选择两者都重要的特征
            selected_features = np.where((mi_source > 0.1) & (mi_target > 0.1))[0]
        else:
            # 无标签：选择源领域重要且目标领域方差大的特征
            target_variance = np.var(target.data, axis=0)
            selected_features = np.where((mi_source > 0.1) & (target_variance > 0.1))[0]

        # 2. 使用选择的特征训练模型
        from sklearn.linear_model import LogisticRegression

        selected_data = source.data[:, selected_features]
        selected_target_data = target.data[:, selected_features]

        model = LogisticRegression()
        model.fit(selected_data, source.labels)

        self.adapter_model = {
            'model': model,
            'selected_features': selected_features,
        }

        return {'method': 'feature_selection', 'n_selected_features': len(selected_features)}

    def visualize_domain_shift(self, output_path: str):
        """可视化领域偏移（t-SNE）"""
        try:
            from sklearn.manifold import TSNE
            import matplotlib.pyplot as plt

            # 合并源领域和目标领域数据
            combined_data = np.vstack([self.source_domain.data, self.target_domain.data])
            labels = ['source'] * len(self.source_domain.data) + ['target'] * len(self.target_domain.data)

            # t-SNE 降维
            tsne = TSNE(n_components=2, random_state=42)
            embedded = tsne.fit_transform(combined_data)

            # 可视化
            plt.figure(figsize=(10, 8))
            for label in ['source', 'target']:
                idx = [i for i, l in enumerate(labels) if l == label]
                plt.scatter(embedded[idx, 0], embedded[idx, 1], label=label, alpha=0.6)

            plt.legend()
            plt.title("Domain Shift Visualization (t-SNE)")
            plt.savefig(output_path)
            plt.close()

            logger.info(f"领域偏移可视化已保存: {output_path}")

        except ImportError:
            logger.warning("需要 matplotlib 和 scikit-learn 来可视化领域偏移")


class TransferLearningPipeline:
    """迁移学习流水线"""

    def __init__(self):
        self.adapters = {}
        logger.info("迁移学习流水线初始化完成")

    def add_adapter(self, name: str, adapter: DomainAdapter):
        """添加适配器"""
        self.adapters[name] = adapter
        logger.info(f"适配器已添加: {name}")

    def run_pipeline(self, source_domains: List[SourceDomain], target_domain: TargetDomain) -> Dict[str, float]:
        """运行迁移学习流水线"""
        results = {}

        for source in source_domains:
            adapter_name = f"{source.name}_to_{target_domain.name}"
            adapter = DomainAdapter(adaptation_method="dann")
            adapter.fit(source, target_domain)

            # 评估
            if target_domain.labels is not None:
                eval_result = adapter.evaluate_transfer(target_domain.data, target_domain.labels)
                results[adapter_name] = eval_result

            self.adapters[adapter_name] = adapter

        return results

    def transfer_knowledge(self, source_name: str, target_name: str, data: np.ndarray) -> np.ndarray:
        """迁移知识"""
        adapter_name = f"{source_name}_to_{target_name}"
        if adapter_name not in self.adapters:
            raise ValueError(f"适配器不存在: {adapter_name}")

        adapter = self.adapters[adapter_name]
        return adapter.adapt(data, source_name, target_name)
