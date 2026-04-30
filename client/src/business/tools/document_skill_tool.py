"""
DocumentSkillTool - 文档→Skill 自动提炼工具（通用·语义分析版）

功能：
1. 接收用户上传的任意文档（通知/通报/专家意见/…）
2. 自动提炼为 Skill（调用 DocumentSkillExtractor）
3. 对后续文档自动语义匹配并触发对应 Skill
4. 作为 BaseTool 注册到 ToolRegistry

使用方法：
    from business.tools.document_skill_tool import DocumentSkillTool

    tool = DocumentSkillTool()
    result = tool.execute(document_text="通知正文…", action="extract", skill_name="会议通知检查专家")

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import os
from typing import Any, Dict, List, Optional

from business.document_skill_extractor import DocumentSkillExtractor
from business.global_model_router import GlobalModelRouter, ModelCapability
from business.semantic_skill_matcher import SemanticSkillMatcher
from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult, SUCCESS, ERROR
from loguru import logger


# --------------------------------------------------------------------------- #
# DocumentSkillTool
# --------------------------------------------------------------------------- #

class DocumentSkillTool(BaseTool):
    """
    文档→Skill 自动提炼工具

    action 参数：
    - "extract"   ：从文档提炼 Skill（生成 SKILL.md + embedding.json）
    - "match"     ：对文档做语义匹配，返回最相似的 Skill
    - "auto_trigger"：自动触发（匹配则返 Skill 信息，否则提示创建）
    - "list"      ：列出所有已提炼的 Skill
    - "delete"     ：删除指定 Skill
    """

    def __init__(self):
        super().__init__(
            name="document_skill",
            description=(
                "从任意文档中自动提炼专家 Skill，"
                "并基于语义相似度自动触发匹配的 Skill。"
                "支持通知、通报、专家意见等多种文体。"
            ),
        )
        self._extractor = DocumentSkillExtractor()
        self._matcher    = SemanticSkillMatcher()
        self._router     = GlobalModelRouter()

    # ------------------------------------------------------------------ #
    # BaseTool 接口
    # ------------------------------------------------------------------ #

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["extract", "match", "auto_trigger", "list", "delete"],
                    "description": "操作类型",
                },
                "document_text": {
                    "type": "string",
                    "description": "文档文本（extract / match / auto_trigger 时必填）",
                },
                "skill_name": {
                    "type": "string",
                    "description": "Skill 名称（extract 时必填）",
                },
                "save_dir": {
                    "type": "string",
                    "description": "Skill 保存目录（相对项目根目录，extract 时使用）",
                },
                "skill_dir": {
                    "type": "string",
                    "description": "Skill 目录路径（delete 时使用）",
                },
                "threshold": {
                    "type": "number",
                    "description": "语义触发阈值（默认 0.75）",
                },
            },
            "required": ["action"],
        }

    def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "match")
        try:
            if action == "extract":
                return self._do_extract(kwargs)
            elif action == "match":
                return self._do_match(kwargs)
            elif action == "auto_trigger":
                return self._do_auto_trigger(kwargs)
            elif action == "list":
                return self._do_list(kwargs)
            elif action == "delete":
                return self._do_delete(kwargs)
            else:
                return ERROR(f"未知 action: {action}")
        except Exception as e:
            logger.error(f"[DocumentSkillTool] 执行失败: {e}")
            return ERROR(f"执行失败: {str(e)}")

    # ------------------------------------------------------------------ #
    # action 实现
    # ------------------------------------------------------------------ #

    def _do_extract(self, kwargs: dict) -> ToolResult:
        document_text = kwargs.get("document_text", "")
        skill_name    = kwargs.get("skill_name", "")
        save_dir      = kwargs.get("save_dir", "")

        if not document_text:
            return ERROR("document_text 不能为空")
        if not skill_name:
            return ERROR("skill_name 不能为空")
        if not save_dir:
            # 自动生成 save_dir
            safe_name = self._safe_dir_name(skill_name)
            save_dir  = f".livingtree/skills/{safe_name}"

        success, msg = self._extractor.extract_skill(
            document_text=document_text,
            skill_name=skill_name,
            save_dir=save_dir,
        )

        if success:
            # 刷新匹配器缓存
            self._matcher.refresh_cache()
            return SUCCESS(data={
                "action":       "extract",
                "skill_dir":    msg,
                "skill_name":   skill_name,
                "save_dir":    save_dir,
                "message":      f"Skill「{skill_name}」提炼成功！",
            })
        else:
            return ERROR(msg)

    def _do_match(self, kwargs: dict) -> ToolResult:
        document_text = kwargs.get("document_text", "")
        if not document_text:
            return ERROR("document_text 不能为空")

        results = self._matcher.match(document_text, top_k=3)
        return SUCCESS(data={
            "action":  "match",
            "matches": results,
            "count":   len(results),
        })

    def _do_auto_trigger(self, kwargs: dict) -> ToolResult:
        document_text = kwargs.get("document_text", "")
        threshold    = kwargs.get("threshold", 0.75)

        if not document_text:
            return ERROR("document_text 不能为空")

        triggered, msg = self._matcher.auto_trigger(document_text, threshold=threshold)

        if triggered:
            # 获取匹配的 Skill 详情
            best = self._matcher.match_best(document_text)
            return SUCCESS(data={
                "action":      "auto_trigger",
                "triggered":    True,
                "skill_name":   best["name"] if best else "",
                "skill_dir":    best["skill_dir"] if best else "",
                "similarity":   best["similarity"] if best else 0.0,
                "skill_md":     best["skill_md"] if best else "",
                "message":      msg,
            })
        else:
            return SUCCESS(data={
                "action":       "auto_trigger",
                "triggered":     False,
                "message":       msg,
                "suggest_create": True,
            })

    def _do_list(self, kwargs: dict) -> ToolResult:
        """列出所有已提炼的 Skill"""
        import glob

        base = os.path.join(
            os.path.dirname(__file__), "..", "..", ".livingtree", "skills"
        )
        base = os.path.abspath(base)

        skills = []
        if os.path.isdir(base):
            for entry in os.listdir(base):
                skill_dir = os.path.join(base, entry)
                skill_md   = os.path.join(skill_dir, "SKILL.md")
                emb_file  = os.path.join(skill_dir, "embedding.json")
                if os.path.isdir(skill_dir) and os.path.exists(skill_md):
                    # 读取 name
                    name = entry
                    try:
                        with open(skill_md, "r", encoding="utf-8") as f:
                            content = f.read(500)
                            m = __import__("re").search(r"name\s*:\s*(.+)", content)
                            if m:
                                name = m.group(1).strip()
                    except Exception:
                        pass
                    skills.append({
                        "name":      name,
                        "dir":        skill_dir,
                        "has_embed":  os.path.exists(emb_file),
                    })

        return SUCCESS(data={
            "action":  "list",
            "skills":  skills,
            "count":    len(skills),
        })

    def _do_delete(self, kwargs: dict) -> ToolResult:
        skill_dir = kwargs.get("skill_dir", "")
        if not skill_dir or not os.path.isdir(skill_dir):
            return ERROR("skill_dir 无效或不存在")

        import shutil
        try:
            shutil.rmtree(skill_dir)
            self._matcher.refresh_cache()
            return SUCCESS(data={
                "action":    "delete",
                "skill_dir": skill_dir,
                "message":   f"Skill 目录已删除: {skill_dir}",
            })
        except Exception as e:
            return ERROR(f"删除失败: {str(e)}")

    # ------------------------------------------------------------------ #
    # 便捷方法（供外部直接调用）
    # ------------------------------------------------------------------ #

    def extract_skill(self, document_text: str, skill_name: str, save_dir: str = "") -> dict:
        """便捷方法：提炼 Skill"""
        result = self.execute(
            action="extract",
            document_text=document_text,
            skill_name=skill_name,
            save_dir=save_dir,
        )
        return result.data if result.success else {"error": result.error}

    def match_skill(self, document_text: str) -> List[Dict]:
        """便捷方法：匹配 Skill"""
        result = self.execute(action="match", document_text=document_text)
        return result.data.get("matches", []) if result.success else []

    def auto_trigger(self, document_text: str, threshold: float = 0.75) -> dict:
        """便捷方法：自动触发"""
        result = self.execute(
            action="auto_trigger",
            document_text=document_text,
            threshold=threshold,
        )
        return result.data if result.success else {"error": result.error}

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #

    @staticmethod
    def _safe_dir_name(name: str) -> str:
        """将 Skill 名称转换为安全的目录名"""
        import re
        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "-", name).strip("-")
        return safe or "unnamed-skill"


# --------------------------------------------------------------------------- #
# 自动注册
# --------------------------------------------------------------------------- #

def auto_register():
    """自动注册到 ToolRegistry"""
    from business.tools.tool_registry import ToolRegistry

    registry = ToolRegistry.get_instance()
    tool = DocumentSkillTool()
    success = registry.register_tool(tool)
    if success:
        logger.info("[DocumentSkillTool] 已注册到 ToolRegistry")
    else:
        logger.warning("[DocumentSkillTool] 注册失败")
    return success


try:
    auto_register()
except Exception as e:
    logger.error(f"[DocumentSkillTool] 自动注册失败: {e}")
