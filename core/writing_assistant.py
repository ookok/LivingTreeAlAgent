"""
写作助手
集成本地模型和远程 API，支持小说创作、润色、大纲生成
"""
import json
import time
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Iterator

from .unified_model_client import (
    UnifiedModelClient,
    Message,
    GenerationConfig,
    create_local_client,
    create_remote_client,
)
from .llama_cpp_client import LlamaCppConfig
from core.logger import get_logger
logger = get_logger('writing_assistant')



class WritingAssistant:
    """
    写作助手
    支持本地 llama.cpp 模型和远程 API
    """

    SYSTEM_PROMPT = """你是一个专业的小说创作助手，擅长创作和润色长篇连载小说。

能力：
1. 根据前文生成连贯的后续情节
2. 创作详细的章节大纲
3. 润色文笔，提升文学性
4. 维护人物设定的一致性

风格要求：
- 注重情节和人物描写
- 保持故事连贯性
- 人物性格一致
- 世界观设定稳定"""

    def __init__(
        self,
        use_local: bool = True,
        local_model_path: Optional[str] = None,
        remote_api_url: Optional[str] = None,
        remote_api_key: Optional[str] = None,
        remote_model: str = "gpt-4",
        n_ctx: int = 16384,
        n_threads: int = 12,
    ):
        self.use_local = use_local
        self.model_client: Optional[UnifiedModelClient] = None
        self._history: List[Message] = []

        if local_model_path is None:
            local_model_path = self._get_default_model_path()

        if use_local:
            logger.info(f"正在初始化本地模型: {local_model_path}")
            try:
                self.model_client = create_local_client(
                    model_path=local_model_path,
                    backend="llama-cpp",
                    n_ctx=n_ctx,
                    n_threads=n_threads,
                )
                logger.info("本地模型加载完成")
            except Exception as e:
                logger.info(f"本地模型加载失败: {e}，将使用远程 API...")
                self.use_local = False

        if not self.use_local:
            logger.info(f"正在连接远程 API: {remote_api_url}")
            api_url = remote_api_url or "https://api.openai.com/v1"
            self.model_client = create_remote_client(
                api_url=api_url,
                api_key=remote_api_key or "",
                model_name=remote_model,
            )
            logger.info("远程 API 连接就绪")

        if not self.test_connection():
            raise RuntimeError("模型连接失败")

    def _get_default_model_path(self) -> str:
        candidates = [
            Path.home() / "models" / "deepseek-r1-7b.Q4_K_M.gguf",
            Path.home() / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf",
            Path.home() / ".hermes-desktop" / "models" / "default.gguf",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return str(candidates[0])

    def test_connection(self) -> bool:
        try:
            test_msg = [Message(role="user", content="请回复'模型工作正常'")]
            response = self.chat(test_msg, max_tokens=20)
            logger.info(f"测试响应: {response[:50]}...")
            return True
        except Exception as e:
            logger.info(f"连接测试失败: {e}")
            return False

    def chat(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
        system: Optional[str] = None,
    ) -> str:
        config = config or GenerationConfig(temperature=0.7, max_tokens=2048)
        full_messages = []
        sys_prompt = system or self.SYSTEM_PROMPT
        full_messages.append(Message(role="system", content=sys_prompt))
        full_messages.extend(messages)

        try:
            return self.model_client.chat(full_messages, config)
        except Exception as e:
            if self.use_local:
                logger.info(f"本地模型失败: {e}")
            raise

    def chat_stream(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
        system: Optional[str] = None,
    ) -> Iterator[str]:
        config = config or GenerationConfig(temperature=0.7, max_tokens=2048)
        full_messages = []
        sys_prompt = system or self.SYSTEM_PROMPT
        full_messages.append(Message(role="system", content=sys_prompt))
        full_messages.extend(messages)
        return self.model_client.chat_stream(full_messages, config)

    def generate_text(self, prompt: str, style: str = "novel", max_tokens: int = 1024) -> str:
        style_map = {
            "novel": "以小说风格写作，注重情节和人物描写",
            "poetic": "以诗意的文笔写作，使用丰富的修辞手法",
            "simple": "以简洁明了的文笔写作",
        }
        instruction = style_map.get(style, style_map["novel"])
        full_prompt = f"{instruction}\n\n{prompt}"
        config = GenerationConfig(temperature=0.8, max_tokens=max_tokens)
        return self.chat([Message(role="user", content=full_prompt)], config)

    def outline_chapter(self, previous_summary: str, chapter_number: int,
                        theme: str = "", max_tokens: int = 1024) -> str:
        prompt = f"""前文摘要：\n{previous_summary}\n\n请生成第{chapter_number}章的大纲。{"本章主题：" + theme if theme else ""}\n\n大纲格式：\n1. 章节标题\n2. 核心冲突\n3. 主要情节（分3-5个阶段）\n4. 关键转折点\n5. 结尾悬念"""
        config = GenerationConfig(temperature=0.7, max_tokens=max_tokens)
        return self.chat([Message(role="user", content=prompt)], config)

    def polish_text(self, text: str, style: str = "elegant", max_tokens: int = 2048) -> str:
        style_map = {
            "elegant": "使用优美、典雅的语言润色，适当使用成语和修辞",
            "concise": "使语言更加简洁有力，删除冗余表达",
            "dramatic": "增强戏剧性，使冲突更激烈，情感更浓烈",
        }
        instruction = style_map.get(style, style_map["elegant"])
        prompt = f"""{instruction}\n\n请润色以下文本：\n{text}\n\n润色要求：\n1. 保持原意不变\n2. 提升文笔质量\n3. 优化句式结构\n4. 保持风格一致\n\n润色后的文本："""
        config = GenerationConfig(temperature=0.6, max_tokens=max_tokens)
        return self.chat([Message(role="user", content=prompt)], config)

    def expand_scene(self, scene_summary: str, details: Optional[Dict] = None,
                     max_tokens: int = 2048) -> str:
        detail_str = ""
        if details:
            detail_str = "\n".join([f"- {k}: {v}" for k, v in details.items()])
        prompt = f"""请将以下场景概要扩展为详细的场景描写：

场景概要：
{scene_summary}

细节要求：
{detail_str or "无特殊要求"}

请写出500-1000字的场景描写，包含：环境描写、人物动作和心理、对话（如适用）、氛围渲染"""
        config = GenerationConfig(temperature=0.8, max_tokens=max_tokens)
        return self.chat([Message(role="user", content=prompt)], config)

    def continue_writing(self, previous_text: str, direction: str = "",
                         max_tokens: int = 2048) -> str:
        prompt = f"""前文内容：
{previous_text}

{"续写方向：" + direction if direction else "请自然地续写后续情节"}

续写要求：
1. 保持文风和人物一致性
2. 情节自然发展
3. 控制节奏
4. 适当制造悬念"""
        config = GenerationConfig(temperature=0.8, max_tokens=max_tokens)
        return self.chat([Message(role="user", content=prompt)], config)

    def batch_process(self, tasks: List[Dict[str, Any]]) -> List[str]:
        results = []
        for i, task in enumerate(tasks, 1):
            task_type = task.get("type", "unknown")
            params = task.get("params", {})
            logger.info(f"[{i}/{len(tasks)}] 处理任务: {task_type}")

            try:
                if task_type == "generate":
                    result = self.generate_text(**params)
                elif task_type == "outline":
                    result = self.outline_chapter(**params)
                elif task_type == "polish":
                    result = self.polish_text(**params)
                elif task_type == "expand":
                    result = self.expand_scene(**params)
                elif task_type == "continue":
                    result = self.continue_writing(**params)
                else:
                    result = f"[错误] 未知任务类型: {task_type}"
                results.append(result)
                logger.info(f"  ✓ 完成")
            except Exception as e:
                results.append(f"[错误] {str(e)}")
                logger.info(f"  ✗ 失败: {e}")

            progress = (i / len(tasks)) * 100
            logger.info(f"  进度: {progress:.0f}%")

        return results

    def save_session(self, filepath: str):
        history_data = [{"role": m.role, "content": m.content} for m in self._history]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        logger.info(f"会话已保存: {filepath}")

    def load_session(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            history_data = json.load(f)
        self._history = [Message(role=m["role"], content=m["content"]) for m in history_data]
        logger.info(f"会话已加载: {filepath}")
