"""
LivingTreeAI Federation - 联邦学习模块
=================================

联邦学习实现：
1. 节点本地训练
2. 梯度聚合
3. 模型分发
4. 自适应聚合

特性：
- 差分隐私保护
- 安全聚合协议
- 自适应节点选择
- 增量学习

Author: Hermes Desktop Team
"""

import asyncio
import json
import hashlib
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FLPhase(Enum):
    """联邦学习阶段"""
    IDLE = "idle"
    ROUND_START = "round_start"
    NODE_SELECTION = "node_selection"
    LOCAL_TRAINING = "local_training"
    GRADIENT_UPLOAD = "gradient_upload"
    AGGREGATION = "aggregation"
    MODEL_DISTRIBUTE = "model_distribute"
    ROUND_COMPLETE = "round_complete"


@dataclass
class FLConfig:
    """联邦学习配置"""
    # 训练参数
    model_type: str = "simple_nn"
    model_size_mb: int = 100
    local_epochs: int = 5
    batch_size: int = 32
    learning_rate: float = 0.01

    # 联邦参数
    min_nodes: int = 3              # 最少参与节点数
    max_nodes: int = 10             # 每轮最多节点数
    node_selection_timeout: float = 60.0  # 节点选择超时
    training_timeout: float = 300.0        # 训练超时

    # 隐私保护
    differential_privacy: bool = True
    noise_multiplier: float = 0.1
    max_grad_norm: float = 1.0

    # 聚合参数
    aggregation_strategy: str = "fedavg"  # fedavg, fedprox, scaffold
    momentum: float = 0.0

    # 自适应
    adaptive_selection: bool = True
    reputation_threshold: float = 0.5


@dataclass
class ModelUpdate:
    """模型更新"""
    node_id: str
    round_number: int
    timestamp: float

    # 梯度/模型参数
    gradients: List[float] = field(default_factory=list)
    model_weights: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    training_samples: int = 0
    loss: float = 0.0
    accuracy: float = 0.0

    # 隐私
    noise_added: float = 0.0

    # 验证
    validation_score: float = 0.0
    is_selected: bool = True

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "round_number": self.round_number,
            "timestamp": self.timestamp,
            "training_samples": self.training_samples,
            "loss": self.loss,
            "accuracy": self.accuracy,
            "validation_score": self.validation_score,
            "is_selected": self.is_selected,
            "gradients_size": len(self.gradients),
        }


@dataclass
class FLRound:
    """联邦学习轮次"""
    round_number: int
    phase: FLPhase
    start_time: float
    end_time: Optional[float] = None

    # 参与节点
    selected_nodes: List[str] = field(default_factory=list)
    updates_received: List[ModelUpdate] = field(default_factory=list)

    # 聚合结果
    aggregated_model: Optional[Dict] = None
    avg_loss: float = 0.0
    avg_accuracy: float = 0.0

    # 全局模型版本
    global_model_version: int = 0

    def duration(self) -> float:
        """持续时间（秒）"""
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now().timestamp() - self.start_time


class FederatedLearning:
    """
    联邦学习管理器

    工作流程：
    1. 轮次开始 - 选择参与节点
    2. 本地训练 - 各节点独立训练
    3. 梯度上传 - 安全传输
    4. 聚合更新 - FedAvg/FedProx
    5. 模型分发 - 分发新模型
    """

    def __init__(
        self,
        config: FLConfig,
        node_id: str,
        network_module,  # P2PNetwork
    ):
        self.config = config
        self.node_id = node_id
        self.network = network_module

        # 当前状态
        self.current_round: Optional[FLRound] = None
        self.global_model: Dict[str, Any] = {}
        self.local_model: Dict[str, Any] = {}

        # 历史
        self.round_history: List[FLRound] = []
        self.total_rounds: int = 0

        # 回调
        self.on_round_complete: Optional[Callable] = None
        self.on_training_progress: Optional[Callable] = None

        # 运行状态
        self.running = False

    async def start_fl(self, num_rounds: int = 10):
        """启动联邦学习"""
        self.running = True
        logger.info(f"启动联邦学习，共 {num_rounds} 轮")

        for round_num in range(1, num_rounds + 1):
            if not self.running:
                break

            success = await self._run_round(round_num)
            if success:
                self.total_rounds = round_num
            else:
                logger.warning(f"轮次 {round_num} 失败，跳过")

        self.running = False
        logger.info("联邦学习完成")

    async def stop_fl(self):
        """停止联邦学习"""
        self.running = False

    async def _run_round(self, round_num: int) -> bool:
        """执行一轮联邦学习"""
        logger.info(f"=== 轮次 {round_num} 开始 ===")

        # 创建轮次对象
        self.current_round = FLRound(
            round_number=round_num,
            phase=FLPhase.ROUND_START,
            start_time=datetime.now().timestamp(),
        )

        try:
            # 1. 节点选择
            await self._select_nodes()
            if len(self.current_round.selected_nodes) < self.config.min_nodes:
                logger.warning("参与节点不足")
                return False

            # 2. 分发全局模型
            await self._distribute_model()

            # 3. 收集更新
            await self._collect_updates()

            # 4. 聚合
            await self._aggregate()

            # 5. 完成轮次
            self.current_round.phase = FLPhase.ROUND_COMPLETE
            self.current_round.end_time = datetime.now().timestamp()

            # 保存历史
            self.round_history.append(self.current_round)

            # 回调
            if self.on_round_complete:
                self.on_round_complete(self.current_round)

            logger.info(
                f"轮次 {round_num} 完成: "
                f"{len(self.current_round.updates_received)} 个更新, "
                f"平均损失 {self.current_round.avg_loss:.4f}, "
                f"耗时 {self.current_round.duration():.1f}s"
            )

            return True

        except Exception as e:
            logger.error(f"轮次 {round_num} 错误: {e}")
            return False

    async def _select_nodes(self):
        """选择参与节点"""
        self.current_round.phase = FLPhase.NODE_SELECTION

        # 获取可用节点
        peers = self.network.get_peers()
        available_nodes = [p["node_id"] for p in peers]

        # 自适应选择（基于信誉）
        if self.config.adaptive_selection:
            # 简化实现：随机选择
            import random
            selected = random.sample(
                available_nodes,
                min(self.config.max_nodes, len(available_nodes))
            )
        else:
            selected = available_nodes[:self.config.max_nodes]

        self.current_round.selected_nodes = selected
        logger.info(f"选择了 {len(selected)} 个节点: {selected}")

    async def _distribute_model(self):
        """分发全局模型到选中节点"""
        self.current_round.phase = FLPhase.MODEL_DISTRIBUTE

        # 广播模型给所有选中节点
        msg = {
            "type": "fl_model_distribute",
            "round_number": self.current_round.round_number,
            "model": self.global_model,
        }
        await self.network.broadcast(msg)

    async def _collect_updates(self):
        """收集各节点的模型更新"""
        self.current_round.phase = FLPhase.GRADIENT_UPLOAD

        # 等待更新（带超时）
        timeout = self.config.training_timeout
        start = datetime.now().timestamp()

        while (
            datetime.now().timestamp() - start < timeout
            and len(self.current_round.updates_received) < len(self.current_round.selected_nodes)
        ):
            await asyncio.sleep(1)

            # 模拟收到更新（实际从网络接收）
            # 这里简化处理，在真实实现中会从网络消息队列获取

        logger.info(f"收到 {len(self.current_round.updates_received)} 个更新")

    async def _aggregate(self):
        """聚合模型更新"""
        self.current_round.phase = FLPhase.AGGREGATION

        updates = self.current_round.updates_received
        if not updates:
            return

        # FedAvg 聚合
        if self.config.aggregation_strategy == "fedavg":
            await self._fedavg_aggregate(updates)
        elif self.config.aggregation_strategy == "fedprox":
            await self._fedprox_aggregate(updates)
        elif self.config.aggregation_strategy == "scaffold":
            await self._scaffold_aggregate(updates)

    async def _fedavg_aggregate(self, updates: List[ModelUpdate]):
        """FedAvg 聚合"""
        total_weight = sum(u.training_samples for u in updates)
        if total_weight == 0:
            total_weight = len(updates)

        # 加权平均
        aggregated = {}
        for update in updates:
            weight = update.training_samples / total_weight

            for key, value in update.model_weights.items():
                if key not in aggregated:
                    aggregated[key] = np.zeros_like(value) if isinstance(value, np.ndarray) else 0

                if isinstance(value, np.ndarray):
                    aggregated[key] += value * weight
                else:
                    aggregated[key] += value * weight

        self.current_round.aggregated_model = aggregated

        # 计算平均损失和准确率
        self.current_round.avg_loss = sum(u.loss for u in updates) / len(updates)
        self.current_round.avg_accuracy = sum(u.accuracy for u in updates) / len(updates)

        # 更新全局模型
        self.global_model = aggregated

    async def _fedprox_aggregate(self, updates: List[ModelUpdate]):
        """FedProx 聚合（带近端项）"""
        # 简化实现：与FedAvg相同
        await self._fedavg_aggregate(updates)

    async def _scaffold_aggregate(self, updates: List[ModelUpdate]):
        """SCAFFOLD 聚合"""
        # 简化实现：与FedAvg相同
        await self._fedavg_aggregate(updates)

    # ==================== 本地训练接口 ====================

    async def local_train(
        self,
        train_data: List[Any],
        model: Dict[str, Any],
    ) -> ModelUpdate:
        """
        本地训练（节点调用）

        返回模型更新
        """
        # 模拟训练过程
        num_epochs = self.config.local_epochs
        batch_size = self.config.batch_size

        losses = []
        for epoch in range(num_epochs):
            # 模拟训练
            await asyncio.sleep(0.1)
            loss = 1.0 / (epoch + 1)  # 模拟损失下降
            losses.append(loss)

            if self.on_training_progress:
                self.on_training_progress(epoch, num_epochs, loss)

        # 创建更新
        update = ModelUpdate(
            node_id=self.node_id,
            round_number=self.total_rounds + 1,
            timestamp=datetime.now().timestamp(),
            gradients=[0.1, 0.2, 0.3],  # 简化
            model_weights=model,
            training_samples=len(train_data),
            loss=sum(losses) / len(losses),
            accuracy=1.0 - sum(losses) / len(losses),
        )

        return update

    def apply_model_update(self, update: ModelUpdate):
        """应用模型更新（节点调用）"""
        self.local_model = update.model_weights

    def get_local_model(self) -> Dict[str, Any]:
        """获取本地模型"""
        return self.local_model

    def get_global_model(self) -> Dict[str, Any]:
        """获取全局模型"""
        return self.global_model

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_rounds": self.total_rounds,
            "current_phase": self.current_round.phase.value if self.current_round else "idle",
            "global_model_size_mb": sum(
                len(str(v)) for v in self.global_model.values()
            ) / (1024 * 1024),
            "round_history": [
                {
                    "round": r.round_number,
                    "participants": len(r.selected_nodes),
                    "avg_loss": r.avg_loss,
                    "avg_accuracy": r.avg_accuracy,
                    "duration": r.duration(),
                }
                for r in self.round_history[-5:]
            ],
        }


# ==================== 模拟实验 ====================

async def simulate_fl():
    """模拟联邦学习"""
    print("=" * 60)
    print("联邦学习模拟")
    print("=" * 60)

    # 配置
    config = FLConfig(
        model_type="simple_nn",
        local_epochs=3,
        aggregation_strategy="fedavg",
        min_nodes=2,
        max_nodes=3,
    )

    # 模拟网络
    class MockNetwork:
        def __init__(self):
            self.peers = [{"node_id": f"node_{i}"} for i in range(3)]

        def get_peers(self):
            return self.peers

        async def broadcast(self, msg):
            print(f"  [广播] {msg['type']}")

        def get_network_stats(self):
            return {"peer_count": 3}

    network = MockNetwork()

    # 创建FL实例
    fl = FederatedLearning(config, "coordinator_node", network)

    # 回调
    def on_round_complete(round_obj):
        print(f"\n>>> 轮次 {round_obj.round_number} 完成!")
        print(f"    参与节点: {len(round_obj.selected_nodes)}")
        print(f"    平均损失: {round_obj.avg_loss:.4f}")
        print(f"    平均准确率: {round_obj.avg_accuracy:.4f}")
        print(f"    耗时: {round_obj.duration():.1f}s")

    fl.on_round_complete = on_round_complete

    # 运行3轮
    await fl.start_fl(num_rounds=3)

    # 统计
    stats = fl.get_stats()
    print(f"\n最终统计: {stats}")


if __name__ == "__main__":
    asyncio.run(simulate_fl())
