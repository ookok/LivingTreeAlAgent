# debate_engine.py — 本地左右互搏辩论引擎
# Hermes 分饰 保守派/激进派，对同一议题辩论

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from .models import (
    DebateRecord, DebateArgument, DebateRole, DebateVerdict,
    HumanVerdict, SystemConfig
)


class DebateEngine:
    """
    本地左右互搏引擎

    核心机制：
    1. 给定辩题，生成保守派和激进派论点
    2. 双方论点互相反驳
    3. 调解者综合得出结论
    4. 标记矛盾点，供人工审核
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "self_upgrade"
        self.debates_dir = self.data_dir / "debates"
        self.debates_dir.mkdir(parents=True, exist_ok=True)

        # 保守派和激进派的系统提示词
        self._conservative_prompt = """你是一个谨慎稳健的思考者，代号「守」。

特点：
- 强调风险控制和稳定性
- 倾向于渐进式改进，而非激进变革
- 关注潜在失败模式和最坏情况
- 偏好经过验证的方案

请针对以下辩题，提出 {n} 个有力论点。每个论点包含：
1. 核心观点（一句话）
2. 支持论据（2-3条）
3. 可能的反驳及回应

以JSON格式输出："""

        self._radical_prompt = """你是一个创新进取的思考者，代号「进」。

特点：
- 强调创新和突破
- 愿意承担可控风险以换取更大收益
- 关注机会和潜在收益
- 偏好新方法和颠覆性思维

请针对以下辩题，提出 {n} 个有力论点。每个论点包含：
1. 核心观点（一句话）
2. 支持论据（2-3条）
3. 可能的反驳及回应

以JSON格式输出："""

        self._mediator_prompt = """你是一个智慧的调解者，代号「衡」。

你的任务：
1. 理解保守派和激进派的核心论点
2. 找出双方的合理内核
3. 提出平衡的折中方案
4. 判断哪一方在当前场景下更优

最终输出：
- 判定结果（保守派胜/激进派胜/妥协/未决）
- 综合结论（一段话）
- 需要人工审核的矛盾点

以JSON格式输出："""

    def _generate_id(self) -> str:
        return f"debate_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async def debate(
        self,
        topic: str,
        topic_category: str,
        context: Optional[Dict[str, Any]] = None,
        n_arguments: int = 3,
        use_local_model: bool = True
    ) -> DebateRecord:
        """
        执行完整辩论流程

        Args:
            topic: 辩题
            topic_category: 类别
            context: 额外上下文
            n_arguments: 每方论点数量
            use_local_model: 是否使用本地模型

        Returns:
            DebateRecord: 完整辩论记录
        """
        record = DebateRecord(
            id=self._generate_id(),
            topic=topic,
            topic_category=topic_category,
            context=context or {}
        )

        # 阶段1：保守派立论
        conservative_args = await self._generate_arguments(
            role=DebateRole.CONSERVATIVE,
            topic=topic,
            context=context,
            n=n_arguments,
            use_local=use_local_model
        )
        record.conservative_args = conservative_args

        # 阶段2：激进派立论
        radical_args = await self._generate_arguments(
            role=DebateRole.RADICAL,
            topic=topic,
            context=context,
            n=n_arguments,
            use_local=use_local_model
        )
        record.radical_args = radical_args

        # 阶段3：反驳阶段
        record = await self._cross_examine(record, use_local_model)

        # 阶段4：调解者裁决
        record = await self._mediate(record, use_local_model)

        # 标记矛盾点
        record.contradictions = self._find_contradictions(record)

        # 保存记录
        self._save_record(record)

        return record

    async def _generate_arguments(
        self,
        role: DebateRole,
        topic: str,
        context: Optional[Dict[str, Any]],
        n: int,
        use_local: bool
    ) -> List[DebateArgument]:
        """生成某一方的论点"""
        if role == DebateRole.CONSERVATIVE:
            prompt = self._conservative_prompt.format(n=n)
        else:
            prompt = self._radical_prompt.format(n=n)

        context_str = ""
        if context:
            context_str = "\n\n参考上下文：\n" + json.dumps(context, ensure_ascii=False, indent=2)

        full_prompt = f"""{prompt}

辩题：{topic}
{context_str}

输出格式：
{{
  "arguments": [
    {{
      "论点": "...",
      "论据": ["...", "..."],
      "反驳": "...",
      "confidence": 0.7
    }}
  ]
}}"""

        # 尝试使用本地模型
        if use_local:
            try:
                result = await self._call_local_model(full_prompt)
                return self._parse_arguments(result, role)
            except Exception as e:
                logger.info(f"[DebateEngine] Local model failed: {e}, falling back to template")

        # 回退到内置模板
        return self._generate_fallback_arguments(role, topic, n)

    async def _call_local_model(self, prompt: str) -> str:
        """调用本地模型"""
        # 复用 system_brain 的本地模型
        try:
            from core.system_brain import get_system_brain
from core.logger import get_logger
logger = get_logger('self_upgrade.debate_engine')

            brain = get_system_brain()
            result = await brain.generate(prompt, max_tokens=500)
            return result
        except ImportError:
            raise RuntimeError("system_brain not available")

    def _parse_arguments(self, response: str, role: DebateRole) -> List[DebateArgument]:
        """解析模型输出为论点列表"""
        try:
            data = json.loads(response)
            args = []
            for item in data.get("arguments", []):
                args.append(DebateArgument(
                    role=role,
                    论点=item.get("论点", ""),
                    论据=item.get("论据", []),
                    反驳=item.get("反驳", ""),
                    confidence=item.get("confidence", 0.5)
                ))
            return args
        except json.JSONDecodeError:
            # 尝试从响应中提取
            return self._generate_fallback_arguments(role, "", 3)

    async def _cross_examine(self, record: DebateRecord, use_local: bool) -> DebateRecord:
        """
        反驳阶段：让每方对对方论点进行反驳
        """
        # 保守派反驳激进派论点
        for radical_arg in record.radical_args:
            # 构造反驳请求
            cross_prompt = f"""你是保守派「守」，请反驳以下激进派观点：

激进派观点：{radical_arg.论点}
论据：{'; '.join(radical_arg.论据)}

请简洁地指出该观点的问题（50字以内）："""

            if use_local:
                try:
                    rebuttal = await self._call_local_model(cross_prompt)
                    radical_arg.反驳 = rebuttal.strip()[:200]
                except:
                    radical_arg.反驳 = "[保守派反驳：需要人工审核]"
            else:
                radical_arg.反驳 = "[保守派反驳：需要人工审核]"

        # 激进派反驳保守派论点
        for conservative_arg in record.conservative_args:
            cross_prompt = f"""你是激进派「进」，请反驳以下保守派观点：

保守派观点：{conservative_arg.论点}
论据：{'; '.join(conservative_arg.论据)}

请简洁地指出该观点的问题（50字以内）："""

            if use_local:
                try:
                    rebuttal = await self._call_local_model(cross_prompt)
                    conservative_arg.反驳 = rebuttal.strip()[:200]
                except:
                    conservative_arg.反驳 = "[激进派反驳：需要人工审核]"
            else:
                conservative_arg.反驳 = "[激进派反驳：需要人工审核]"

        return record

    async def _mediate(self, record: DebateRecord, use_local: bool) -> DebateRecord:
        """调解者综合"""
        conservative_viewpoints = "\n".join([
            f"- {arg.论点} (置信度:{arg.confidence})" 
            for arg in record.conservative_args
        ])
        radical_viewpoints = "\n".join([
            f"- {arg.论点} (置信度:{arg.confidence})" 
            for arg in record.radical_args
        ])

        mediator_prompt = f"""你是调解者「衡」，请综合以下辩论：

辩题：{record.topic}

保守派「守」观点：
{conservative_viewpoints}

激进派「进」观点：
{radical_viewpoints}

请输出JSON：
{{
  "verdict": "conservative_wins/radical_wins/compromise/inconclusive",
  "conclusion": "综合结论（100字以内）",
  "key_insight": "核心洞见（30字以内）"
}}"""

        if use_local:
            try:
                result = await self._call_local_model(mediator_prompt)
                data = json.loads(result)
                verdict_str = data.get("verdict", "inconclusive").lower()
                if "conservative" in verdict_str:
                    record.verdict = DebateVerdict.CONSERVATIVE_WINS
                elif "radical" in verdict_str:
                    record.verdict = DebateVerdict.RADICAL_WINS
                elif "compromise" in verdict_str or "inconclusive" in verdict_str:
                    record.verdict = DebateVerdict.COMPROMISE
                else:
                    record.verdict = DebateVerdict.INCONCLUSIVE

                record.final_conclusion = data.get("conclusion", "")
            except:
                record.verdict = DebateVerdict.INCONCLUSIVE
                record.final_conclusion = "[需要人工裁决]"
        else:
            record.verdict = DebateVerdict.INCONCLUSIVE
            record.final_conclusion = "[需要人工裁决]"

        record.updated_at = datetime.now()
        return record

    def _find_contradictions(self, record: DebateRecord) -> List[str]:
        """找出辩论中的矛盾点"""
        contradictions = []

        # 检查置信度差异大的论点
        for con_arg in record.conservative_args:
            for rad_arg in record.radical_args:
                diff = abs(con_arg.confidence - rad_arg.confidence)
                if diff > 0.4:
                    contradictions.append(
                        f"置信度冲突：保守派({con_arg.confidence}) vs 激进派({rad_arg.confidence})"
                    )

        # 检查结论是否未决
        if record.verdict == DebateVerdict.INCONCLUSIVE:
            contradictions.append("辩论未能得出明确结论，需人工裁决")

        return contradictions

    def _generate_fallback_arguments(
        self, role: DebateRole, topic: str, n: int
    ) -> List[DebateArgument]:
        """生成内置回退论点（当模型不可用时）"""
        if role == DebateRole.CONSERVATIVE:
            templates = [
                ("稳定性优先", ["当前方案经过验证", "风险可控", "用户熟悉"], 0.7),
                ("渐进改进更安全", ["避免剧烈变化", "便于回滚", "降低学习成本"], 0.6),
                ("保守策略降低风险", ["减少未知因素", "保护已有投入", "稳妥推进"], 0.5),
            ]
        else:
            templates = [
                ("创新带来突破", ["可能获得更大收益", "解决根本问题", "创造新机会"], 0.7),
                ("敢于尝试新方法", ["探索更多可能性", "发现隐藏机会", "突破思维定式"], 0.6),
                ("激进策略加速进化", ["快速试错迭代", "抓住窗口期", "领先竞争对手"], 0.5),
            ]

        args = []
        for i in range(min(n, len(templates))):
            论点, 论据, conf = templates[i]
            args.append(DebateArgument(
                role=role,
                论点=f"{topic} - {论点}",
                论据=论据,
                反驳="",
                confidence=conf
            ))
        return args

    def _save_record(self, record: DebateRecord):
        """保存辩论记录"""
        file_path = self.debates_dir / f"{record.id}.json"
        data = {
            "id": record.id,
            "topic": record.topic,
            "topic_category": record.topic_category,
            "context": record.context,
            "conservative_args": [
                {
                    "论点": a.论点,
                    "论据": a.论据,
                    "反驳": a.反驳,
                    "confidence": a.confidence
                } for a in record.conservative_args
            ],
            "radical_args": [
                {
                    "论点": a.论点,
                    "论据": a.论据,
                    "反驳": a.反驳,
                    "confidence": a.confidence
                } for a in record.radical_args
            ],
            "verdict": record.verdict.value,
            "final_conclusion": record.final_conclusion,
            "contradictions": record.contradictions,
            "human_verdict": record.human_verdict.value,
            "human_notes": record.human_notes,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_record(self, debate_id: str) -> Optional[DebateRecord]:
        """加载辩论记录"""
        file_path = self.debates_dir / f"{debate_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        record = DebateRecord(
            id=data["id"],
            topic=data["topic"],
            topic_category=data["topic_category"],
            context=data.get("context", {}),
            verdict=DebateVerdict(data.get("verdict", "tbd")),
            final_conclusion=data.get("final_conclusion", ""),
            contradictions=data.get("contradictions", []),
            human_verdict=HumanVerdict(data.get("human_verdict", "pending")),
            human_notes=data.get("human_notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

        record.conservative_args = [
            DebateArgument(
                role=DebateRole.CONSERVATIVE,
                论点=a["论点"],
                论据=a["论据"],
                反驳=a.get("反驳", ""),
                confidence=a.get("confidence", 0.5)
            ) for a in data.get("conservative_args", [])
        ]

        record.radical_args = [
            DebateArgument(
                role=DebateRole.RADICAL,
                论点=a["论点"],
                论据=a["论据"],
                反驳=a.get("反驳", ""),
                confidence=a.get("confidence", 0.5)
            ) for a in data.get("radical_args", [])
        ]

        return record

    def list_records(self, limit: int = 20) -> List[DebateRecord]:
        """列出最近的辩论记录"""
        records = []
        for f in sorted(self.debates_dir.glob("debate_*.json"), reverse=True)[:limit]:
            record = self.load_record(f.stem)
            if record:
                records.append(record)
        return records

    def update_human_verdict(
        self,
        debate_id: str,
        verdict: HumanVerdict,
        notes: str = ""
    ) -> bool:
        """更新人工裁决"""
        record = self.load_record(debate_id)
        if not record:
            return False

        record.human_verdict = verdict
        record.human_notes = notes
        record.updated_at = datetime.now()
        self._save_record(record)
        return True


# 全局单例
_debate_engine: Optional[DebateEngine] = None


def get_debate_engine() -> DebateEngine:
    global _debate_engine
    if _debate_engine is None:
        _debate_engine = DebateEngine()
    return _debate_engine
