"""
AgentReachTool - Agent Reach 多平台搜索工具

参考 Agent Reach 项目（https://github.com/Panniantong/Agent-Reach）：
- 统一 CLI 接口读取和搜索 14 个平台内容
- 零 API 费用（使用 twitter-cli、rdt-cli、yt-dlp 等开源工具）
- 支持平台：Twitter/X、Reddit、YouTube、GitHub、Bilibili、小红书、抖音、微博、微信公众号等

集成方案：
1. 通过 subprocess 调用 agent-reach CLI
2. 支持搜索和读取两种模式
3. 处理 cookie 认证配置
4. 封装为 BaseTool 供智能体调用

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import subprocess
import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum

from client.src.business.tools.base_tool import BaseTool


class Platform(Enum):
    """支持的平台枚举"""
    TWITTER = "twitter"       # Twitter/X
    REDDIT = "reddit"         # Reddit
    YOUTUBE = "youtube"       # YouTube
    GITHUB = "github"         # GitHub
    BILIBILI = "bilibili"     # B站
    XIAOHONGSHU = "xiaohongshu"  # 小红书
    DOUYIN = "douyin"         # 抖音
    WEIBO = "weibo"           # 微博
    WECHAT = "wechat"         # 微信公众号
    LINKEDIN = "linkedin"     # LinkedIn
    INSTAGRAM = "instagram"   # Instagram
    RSS = "rss"               # RSS
    V2EX = "v2ex"             # V2EX
    SNOWBALL = "snowball"     # 雪球


class SearchMode(Enum):
    """搜索模式"""
    SEARCH = "search"         # 搜索模式
    READ = "read"             # 读取模式（读取指定 URL）
    LIST = "list"             # 列出支持的平台


@dataclass
class SearchResult:
    """搜索结果"""
    platform: str
    title: str
    url: str
    content: str = ""
    summary: str = ""
    timestamp: str = ""
    author: str = ""
    likes: int = 0
    comments: int = 0


class AgentReachTool(BaseTool):
    """
    Agent Reach 多平台搜索工具
    
    功能：
    1. 通过 Agent Reach CLI 搜索多个平台内容
    2. 支持搜索和读取两种模式
    3. 零 API 费用
    4. 支持 14+ 平台
    
    使用方式：
        tool = AgentReachTool()
        result = await tool.execute(query="人工智能", platforms=["twitter", "github"])
    """
    
    def __init__(self):
        super().__init__()
        self._logger = logger.bind(component="AgentReachTool")
        self._agent_reach_available = self._check_agent_reach_availability()
        self._cookie_path = self._get_cookie_path()
    
    @property
    def name(self) -> str:
        return "agent_reach_search"
    
    @property
    def description(self) -> str:
        return "通过 Agent Reach 搜索 14+ 平台（Twitter/Reddit/YouTube/GitHub/Bilibili/小红书/微博等），零 API 费用。支持搜索和读取模式。"
    
    @property
    def category(self) -> str:
        return "search"
    
    @property
    def node_type(self) -> str:
        return "deterministic"  # 确定性工具（CLI调用）
    
    def _check_agent_reach_availability(self) -> bool:
        """检查 Agent Reach 是否可用"""
        try:
            result = subprocess.run(
                ["agent-reach", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self._logger.info(f"Agent Reach 可用，版本: {result.stdout.strip()}")
                return True
            else:
                self._logger.warning(f"Agent Reach 返回错误: {result.stderr}")
                return False
        except FileNotFoundError:
            self._logger.warning("Agent Reach 未安装，请运行: pip install agent-reach 然后 agent-reach install")
            return False
        except Exception as e:
            self._logger.error(f"检查 Agent Reach 可用性失败: {e}")
            return False
    
    def _get_cookie_path(self) -> str:
        """获取 cookie 配置路径"""
        return os.path.join(os.path.expanduser("~"), ".agent-reach", "cookies")
    
    def is_available(self) -> bool:
        """检查工具是否可用"""
        return self._agent_reach_available
    
    def get_supported_platforms(self) -> List[str]:
        """获取支持的平台列表"""
        return [p.value for p in Platform]
    
    async def execute(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        mode: str = "search",
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行多平台搜索
        
        Args:
            query: 搜索关键词或 URL（read 模式时）
            platforms: 平台列表，如 ["twitter", "github"]，None 表示全部支持的平台
            mode: search=搜索，read=读取URL内容，list=列出支持的平台
            
        Returns:
            搜索结果
        """
        if mode == "list":
            return {
                "success": True,
                "message": "支持的平台列表",
                "data": self.get_supported_platforms()
            }
        
        if not self._agent_reach_available:
            return {
                "success": False,
                "message": "Agent Reach 不可用，请先安装: pip install agent-reach && agent-reach install",
                "data": []
            }
        
        if not query:
            return {
                "success": False,
                "message": "查询内容不能为空",
                "data": []
            }
        
        try:
            # 构建命令
            cmd = ["agent-reach", mode, query]
            
            # 添加平台参数
            if platforms:
                # 验证平台名称
                valid_platforms = self.get_supported_platforms()
                valid_platforms_list = [p for p in platforms if p in valid_platforms]
                
                if valid_platforms_list:
                    cmd.extend(["--platforms", ",".join(valid_platforms_list)])
                
                # 报告无效平台
                invalid_platforms = [p for p in platforms if p not in valid_platforms]
                if invalid_platforms:
                    self._logger.warning(f"无效的平台: {invalid_platforms}")
            
            # 添加 cookie 路径（如果存在）
            if os.path.exists(self._cookie_path):
                cmd.extend(["--cookie-dir", self._cookie_path])
            
            self._logger.debug(f"执行命令: {' '.join(cmd)}")
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                # 解析结果
                parsed_results = self._parse_results(result.stdout)
                
                self._logger.info(f"搜索完成: 找到 {len(parsed_results)} 条结果")
                
                return {
                    "success": True,
                    "message": "搜索成功",
                    "data": parsed_results,
                    "platforms_used": platforms or "all"
                }
            else:
                error_msg = result.stderr.strip()[:500] if result.stderr else "未知错误"
                self._logger.error(f"Agent Reach 执行失败: {error_msg}")
                return {
                    "success": False,
                    "message": f"搜索失败: {error_msg}",
                    "data": [],
                    "platforms_used": platforms or "all"
                }
        
        except subprocess.TimeoutExpired:
            self._logger.error("Agent Reach 执行超时")
            return {
                "success": False,
                "message": "搜索超时",
                "data": []
            }
        except Exception as e:
            self._logger.error(f"搜索过程中发生错误: {e}")
            return {
                "success": False,
                "message": str(e),
                "data": []
            }
    
    def _parse_results(self, output: str) -> List[Dict[str, Any]]:
        """
        解析 Agent Reach 输出结果
        
        Args:
            output: CLI 输出文本
            
        Returns:
            解析后的结果列表
        """
        results = []
        
        try:
            # 尝试 JSON 解析
            data = json.loads(output)
            if isinstance(data, list):
                for item in data:
                    results.append({
                        "platform": item.get("platform", ""),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "summary": item.get("summary", ""),
                        "timestamp": item.get("timestamp", ""),
                        "author": item.get("author", ""),
                        "likes": item.get("likes", 0),
                        "comments": item.get("comments", 0)
                    })
            return results
        except json.JSONDecodeError:
            # 如果不是 JSON，按行解析
            lines = output.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    # 尝试解析简单格式
                    parts = line.split('|')
                    if len(parts) >= 3:
                        results.append({
                            "platform": parts[0].strip(),
                            "title": parts[1].strip(),
                            "url": parts[2].strip() if len(parts) > 2 else "",
                            "content": "",
                            "summary": ""
                        })
        
        return results
    
    def configure_platform(self, platform: str, cookie_data: Optional[str] = None):
        """
        配置平台认证（如 Twitter、小红书需要 cookie）
        
        Args:
            platform: 平台名称
            cookie_data: Cookie 数据（可选，通过 Cookie-Editor 导出）
        """
        if platform not in self.get_supported_platforms():
            self._logger.error(f"不支持的平台: {platform}")
            return False
        
        try:
            # 确保 cookie 目录存在
            os.makedirs(self._cookie_path, exist_ok=True)
            
            if cookie_data:
                # 保存 cookie 到文件
                cookie_file = os.path.join(self._cookie_path, f"{platform}.json")
                with open(cookie_file, 'w', encoding='utf-8') as f:
                    # 尝试解析 JSON
                    try:
                        cookie_json = json.loads(cookie_data)
                        json.dump(cookie_json, f, ensure_ascii=False, indent=2)
                    except json.JSONDecodeError:
                        # 如果不是 JSON，直接保存
                        f.write(cookie_data)
                
                self._logger.info(f"已配置 {platform} 的 cookie")
                return True
            
            # 没有 cookie，尝试自动配置
            result = subprocess.run(
                ["agent-reach", "config", platform],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self._logger.info(f"成功配置 {platform}")
                return True
            else:
                self._logger.warning(f"配置 {platform} 失败: {result.stderr}")
                return False
                
        except Exception as e:
            self._logger.error(f"配置平台失败: {e}")
            return False
    
    def get_platform_status(self, platform: str) -> Dict[str, Any]:
        """
        获取平台状态（是否已配置）
        
        Args:
            platform: 平台名称
            
        Returns:
            状态信息
        """
        if platform not in self.get_supported_platforms():
            return {"platform": platform, "configured": False, "error": "不支持的平台"}
        
        # 检查 cookie 文件
        cookie_file = os.path.join(self._cookie_path, f"{platform}.json")
        has_cookie = os.path.exists(cookie_file)
        
        return {
            "platform": platform,
            "configured": has_cookie,
            "cookie_file": cookie_file if has_cookie else None
        }
    
    def get_all_platform_status(self) -> List[Dict[str, Any]]:
        """获取所有平台状态"""
        status_list = []
        for platform in self.get_supported_platforms():
            status_list.append(self.get_platform_status(platform))
        return status_list
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体调用信息"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或 URL（read 模式时）",
                    "required": True
                },
                "platforms": {
                    "type": "array",
                    "description": f"平台列表，可选值: {self.get_supported_platforms()}",
                    "required": False,
                    "default": None
                },
                "mode": {
                    "type": "string",
                    "description": "模式: search（搜索）/ read（读取URL）/ list（列出平台）",
                    "required": False,
                    "default": "search",
                    "enum": ["search", "read", "list"]
                }
            },
            "examples": [
                {
                    "input": {"query": "人工智能 LLM", "platforms": ["twitter", "github"]},
                    "description": "在 Twitter 和 GitHub 上搜索人工智能 LLM"
                },
                {
                    "input": {"query": "https://www.youtube.com/watch?v=xxx", "mode": "read"},
                    "description": "读取 YouTube 视频内容"
                },
                {
                    "input": {"mode": "list"},
                    "description": "列出所有支持的平台"
                }
            ],
            "supported_platforms": self.get_supported_platforms()
        }


# 创建工具实例
agent_reach_tool = AgentReachTool()


def get_agent_reach_tool() -> AgentReachTool:
    """获取 Agent Reach 工具实例"""
    return agent_reach_tool


# 测试函数
async def test_agent_reach_tool():
    """测试 Agent Reach 工具"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 AgentReachTool")
    print("=" * 60)
    
    tool = AgentReachTool()
    print(f"\nAgent Reach 可用: {'✓' if tool.is_available() else '✗'}")
    
    if tool.is_available():
        # 测试列出平台
        print("\n[1] 测试列出平台:")
        result = await tool.execute(mode="list")
        if result["success"]:
            platforms = result["data"]
            print(f"  支持 {len(platforms)} 个平台:")
            for p in platforms:
                print(f"    - {p}")
        
        # 测试搜索
        print("\n[2] 测试搜索:")
        result = await tool.execute(
            query="AI agent",
            platforms=["github", "reddit"],
            mode="search"
        )
        
        if result["success"]:
            print(f"  搜索成功，找到 {len(result['data'])} 条结果")
            for item in result["data"][:3]:
                print(f"    - [{item.get('platform')}] {item.get('title', '')[:40]}...")
        else:
            print(f"  搜索失败: {result['message']}")
        
        # 测试平台状态
        print("\n[3] 测试平台状态:")
        status_list = tool.get_all_platform_status()
        configured_count = sum(1 for s in status_list if s["configured"])
        print(f"  已配置平台: {configured_count}/{len(status_list)}")
        
    else:
        print("⚠️ Agent Reach 不可用，跳过功能测试")
        
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent_reach_tool())