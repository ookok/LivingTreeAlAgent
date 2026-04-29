"""
计算指纹 (Computation Fingerprint)
==============================

核心理念：
- 每次计算都有唯一的"数字指纹"
- 指纹 = 计算输入 + 参数 + 结果 的哈希
- 用于审计追溯、结果验证、版本对比

指纹链：
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   输入哈希   │ →  │   参数哈希   │ →  │   输出哈希   │
│  (InputHash) │    │ (ParamHash) │    │ (OutputHash)│
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │   包哈希 (PK)    │
                                    │  FingerprintID  │
                                    └─────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │  区块链式存储    │
                                    │  (不可篡改)     │
                                    └─────────────────┘
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class FingerprintStatus(Enum):
    """指纹状态"""
    ACTIVE = "active"           # 有效
    VERIFIED = "verified"        # 已验证
    EXPIRED = "expired"          # 已过期
    REVOKED = "revoked"          # 已撤销


@dataclass
class Fingerprint:
    """计算指纹"""
    fingerprint_id: str           # 指纹ID (pk_xxx)
    version: str = "1.0"         # 指纹版本

    # 组成哈希
    input_hash: str = ""         # 输入哈希
    parameter_hash: str = ""     # 参数哈希
    output_hash: str = ""        # 输出哈希
    package_hash: str = ""       # 包哈希 (指纹本身)

    # 元数据
    model_type: str = ""          # 模型类型
    model_version: str = ""       # 模型版本
    engine_version: str = ""      # 引擎版本

    # 关联数据
    project_id: str = ""          # 项目ID
    section_id: str = ""          # 章节ID
    computation_time: float = 0.0 # 计算耗时

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    verified_at: datetime = None

    # 状态
    status: FingerprintStatus = FingerprintStatus.ACTIVE

    # 前序指纹（区块链）
    previous_fingerprint: str = ""  # 前一个指纹ID

    # 签名
    signature: str = ""          # 数字签名（可选）

    # 额外数据
    metadata: dict = field(default_factory=dict)


@dataclass
class FingerprintChain:
    """指纹链"""
    chain_id: str
    project_id: str

    # 链信息
    fingerprints: list[Fingerprint] = field(default_factory=list)
    genesis_fingerprint: str = ""  # 创世指纹

    # 统计
    total_computations: int = 0
    verified_count: int = 0

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class ComputationFingerprintGenerator:
    """
    计算指纹生成器

    核心理念：
    - 为每次计算生成唯一、不可篡改的指纹
    - 支持指纹链追溯
    - 可用于审计和验证

    用法:
        generator = ComputationFingerprintGenerator()

        # 生成指纹
        fp = generator.generate(
            model_type="gaussian_plume",
            inputs={"sources": [...]},
            parameters={"emission_rate": 0.5},
            output={"max_concentration": 0.08}
        )

        # 验证指纹
        is_valid = generator.verify(fp)

        # 添加到链
        generator.add_to_chain(fp, chain_id)

        # 验证链完整性
        is_chain_valid = generator.verify_chain(chain_id)
    """

    HASH_ALGORITHM = "sha256"
    HASH_PREFIX = "eia"  # 环评标识

    def __init__(self, data_dir: str = "./data/eia/fingerprints"):
        self.data_dir = data_dir
        self._fingerprints: dict[str, Fingerprint] = {}
        self._chains: dict[str, FingerprintChain] = {}

    def generate(
        self,
        model_type: str,
        inputs: dict,
        parameters: dict,
        output: dict,
        project_id: str = "",
        section_id: str = "",
        metadata: dict = None,
        previous_fingerprint: str = ""
    ) -> Fingerprint:
        """
        生成计算指纹

        Args:
            model_type: 模型类型
            inputs: 输入数据
            parameters: 参数数据
            output: 输出结果
            project_id: 项目ID
            section_id: 章节ID
            metadata: 额外元数据
            previous_fingerprint: 前一个指纹ID

        Returns:
            Fingerprint: 计算指纹
        """
        # 计算各部分哈希
        input_hash = self._compute_hash(inputs)
        parameter_hash = self._compute_hash(parameters)
        output_hash = self._compute_hash(output)

        # 计算包哈希
        package_data = {
            "input_hash": input_hash,
            "parameter_hash": parameter_hash,
            "output_hash": output_hash,
            "model_type": model_type,
            "timestamp": datetime.now().isoformat()
        }
        package_hash = self._compute_hash(package_data)

        # 生成指纹ID
        fingerprint_id = self._generate_id(
            model_type, input_hash, output_hash
        )

        # 创建指纹
        fp = Fingerprint(
            fingerprint_id=fingerprint_id,
            version="1.0",
            input_hash=input_hash,
            parameter_hash=parameter_hash,
            output_hash=output_hash,
            package_hash=package_hash,
            model_type=model_type,
            project_id=project_id,
            section_id=section_id,
            previous_fingerprint=previous_fingerprint,
            metadata=metadata or {},
            created_at=datetime.now()
        )

        # 存储
        self._fingerprints[fingerprint_id] = fp

        return fp

    def _compute_hash(self, data: Any) -> str:
        """
        计算数据哈希

        Args:
            data: 任意可序列化数据

        Returns:
            str: 16位哈希值
        """
        # 序列化
        if isinstance(data, dict):
            serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        elif isinstance(data, (list, tuple)):
            serialized = json.dumps(list(data), sort_keys=True, ensure_ascii=False)
        else:
            serialized = str(data)

        # 计算哈希
        hash_obj = hashlib.sha256(serialized.encode())
        return hash_obj.hexdigest()[:16]

    def _generate_id(
        self,
        model_type: str,
        input_hash: str,
        output_hash: str
    ) -> str:
        """生成指纹ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        raw_id = f"{self.HASH_PREFIX}_{model_type}_{input_hash[:4]}_{output_hash[:4]}_{timestamp}"
        hash_suffix = hashlib.sha256(raw_id.encode()).hexdigest()[:8]
        return f"fp_{hash_suffix}"

    def verify(self, fingerprint: Fingerprint) -> bool:
        """
        验证指纹完整性

        Args:
            fingerprint: 指纹

        Returns:
            bool: 是否有效
        """
        # 重新计算哈希
        input_hash = self._compute_hash(
            fingerprint.metadata.get("inputs", {})
        )
        parameter_hash = self._compute_hash(
            fingerprint.metadata.get("parameters", {})
        )
        output_hash = self._compute_hash(
            fingerprint.metadata.get("output", {})
        )

        # 比较
        return (
            fingerprint.input_hash == input_hash and
            fingerprint.parameter_hash == parameter_hash and
            fingerprint.output_hash == output_hash
        )

    def add_to_chain(
        self,
        fingerprint: Fingerprint,
        chain_id: str,
        project_id: str = ""
    ) -> None:
        """
        将指纹添加到链

        Args:
            fingerprint: 指纹
            chain_id: 链ID
            project_id: 项目ID
        """
        # 获取或创建链
        if chain_id not in self._chains:
            chain = FingerprintChain(
                chain_id=chain_id,
                project_id=project_id,
                genesis_fingerprint=fingerprint.fingerprint_id
            )
            self._chains[chain_id] = chain

            # 设置创世指纹
            fingerprint.previous_fingerprint = ""

        else:
            chain = self._chains[chain_id]
            # 设置前序指纹
            fingerprint.previous_fingerprint = chain.fingerprints[-1].fingerprint_id if chain.fingerprints else ""

        # 添加到链
        chain.fingerprints.append(fingerprint)
        chain.total_computations += 1
        chain.last_updated = datetime.now()

    def verify_chain(self, chain_id: str) -> dict:
        """
        验证链完整性

        Args:
            chain_id: 链ID

        Returns:
            dict: {
                "valid": bool,
                "broken_at": int,  # 如果无效，断开位置
                "total": int,
                "verified": int
            }
        """
        if chain_id not in self._chains:
            return {"valid": False, "error": "Chain not found"}

        chain = self._chains[chain_id]
        fingerprints = chain.fingerprints

        if not fingerprints:
            return {"valid": True, "total": 0, "verified": 0}

        # 验证每个指纹
        verified_count = 0
        broken_at = -1

        for i, fp in enumerate(fingerprints):
            # 验证哈希
            if self.verify(fp):
                verified_count += 1
            else:
                broken_at = i
                break

            # 验证链连接
            if i > 0:
                prev_fp = fingerprints[i - 1]
                if fp.previous_fingerprint != prev_fp.fingerprint_id:
                    broken_at = i
                    break

        return {
            "valid": broken_at == -1,
            "broken_at": broken_at,
            "total": len(fingerprints),
            "verified": verified_count
        }

    def get_fingerprint(self, fingerprint_id: str) -> Fingerprint:
        """获取指纹"""
        return self._fingerprints.get(fingerprint_id)

    def get_chain(self, chain_id: str) -> FingerprintChain:
        """获取链"""
        return self._chains.get(chain_id)

    def get_project_fingerprints(
        self,
        project_id: str,
        limit: int = 100
    ) -> list[Fingerprint]:
        """获取项目的所有指纹"""
        fps = [
            fp for fp in self._fingerprints.values()
            if fp.project_id == project_id
        ]

        # 按时间排序
        fps.sort(key=lambda x: x.created_at, reverse=True)

        return fps[:limit]

    def export_fingerprint_package(
        self,
        fingerprint_id: str
    ) -> dict:
        """
        导出指纹包（用于分享和归档）

        Args:
            fingerprint_id: 指纹ID

        Returns:
            dict: 可序列化的指纹包
        """
        fp = self._fingerprints.get(fingerprint_id)
        if not fp:
            return {}

        return {
            "fingerprint_id": fp.fingerprint_id,
            "version": fp.version,
            "hashes": {
                "input": fp.input_hash,
                "parameter": fp.parameter_hash,
                "output": fp.output_hash,
                "package": fp.package_hash
            },
            "metadata": {
                "model_type": fp.model_type,
                "model_version": fp.model_version,
                "engine_version": fp.engine_version,
                "project_id": fp.project_id,
                "section_id": fp.section_id,
                "computation_time": fp.computation_time
            },
            "timestamps": {
                "created": fp.created_at.isoformat(),
                "verified": fp.verified_at.isoformat() if fp.verified_at else None
            },
            "chain": {
                "previous": fp.previous_fingerprint,
                "status": fp.status.value
            },
            "signature": fp.signature
        }

    def import_fingerprint_package(self, package: dict) -> Fingerprint:
        """
        导入指纹包

        Args:
            package: 指纹包

        Returns:
            Fingerprint: 指纹对象
        """
        fp = Fingerprint(
            fingerprint_id=package["fingerprint_id"],
            version=package.get("version", "1.0"),
            input_hash=package["hashes"]["input"],
            parameter_hash=package["hashes"]["parameter"],
            output_hash=package["hashes"]["output"],
            package_hash=package["hashes"]["package"],
            model_type=package["metadata"]["model_type"],
            project_id=package["metadata"].get("project_id", ""),
            section_id=package["metadata"].get("section_id", ""),
            created_at=datetime.fromisoformat(package["timestamps"]["created"]),
            previous_fingerprint=package["chain"]["previous"],
            signature=package.get("signature", "")
        )

        if package["timestamps"].get("verified"):
            fp.verified_at = datetime.fromisoformat(package["timestamps"]["verified"])
            fp.status = FingerprintStatus.VERIFIED

        self._fingerprints[fp.fingerprint_id] = fp

        return fp

    def generate_report(self, project_id: str) -> str:
        """生成指纹报告"""
        fps = self.get_project_fingerprints(project_id)

        if not fps:
            return "# 计算指纹报告\n\n暂无计算记录"

        # 统计
        by_model = {}
        for fp in fps:
            model = fp.model_type
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(fp)

        # 构建报告
        report = f"""
# 计算指纹报告

## 项目信息
- 项目ID: {project_id}
- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 统计概览
- 总计算次数: {len(fps)}
- 模型类型: {len(by_model)}

## 模型使用分布

| 模型 | 计算次数 | 占比 |
|------|---------|------|
"""

        for model, model_fps in by_model.items():
            pct = len(model_fps) / len(fps) * 100
            report += f"| {model} | {len(model_fps)} | {pct:.1f}% |\n"

        report += """
## 计算记录

| 时间 | 模型 | 指纹ID | 状态 |
|------|------|--------|------|
"""

        for fp in fps[:20]:  # 只显示最近20条
            status_icon = "✅" if fp.status == FingerprintStatus.VERIFIED else "⏳"
            report += f"| {fp.created_at.strftime('%m-%d %H:%M')} | {fp.model_type} | `{fp.fingerprint_id}` | {status_icon} |\n"

        return report


def create_fingerprint_generator(
    data_dir: str = "./data/eia/fingerprints"
) -> ComputationFingerprintGenerator:
    """创建指纹生成器实例"""
    return ComputationFingerprintGenerator(data_dir=data_dir)