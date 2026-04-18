"""
数据库模块
Database Module

提供数据库连接和迁移管理
"""

from pathlib import Path

# 数据库目录
DATABASE_DIR = Path(__file__).parent
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

# 数据库文件
MAIN_DB = DATABASE_DIR / "main.db"
MCP_DB = DATABASE_DIR / "mcp.db"
SKILLS_DB = DATABASE_DIR / "skills.db"
LAN_CHAT_DB = DATABASE_DIR / "lan_chat.db"
