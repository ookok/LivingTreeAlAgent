"""
agency-agents-zh 专家角色库适配工具
将专家角色文件适配为 WorkBuddy 技能格式
"""

import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Optional


# 路径配置（优先输出到项目内置目录）
PROJECT_DIR = Path("d:/mhzyapp/LivingTreeAlAgent")

# 源目录（references，保留原始文件）
REFERENCES_DIR = PROJECT_DIR / ".livingtree" / "references" / "agency-agents-zh"
# 如果内置目录不存在，使用 .workbuddy 作为源
if not REFERENCES_DIR.exists():
    REFERENCES_DIR = PROJECT_DIR / ".workbuddy" / "references" / "agency-agents-zh"

# 输出目录（项目内置目录，作为内置集成）
SKILLS_DIR = PROJECT_DIR / ".livingtree" / "skills" / "agency-agents-zh"

# 跳过的目录
SKIP_DIRS = {".git", "scripts", "integrations", ".github", "examples"}


def adapt_agent_to_skill(agent_md: Path, output_dir: Path) -> bool:
    """
    将专家角色文件适配为 WorkBuddy 技能格式
    
    Args:
        agent_md: 专家角色 .md 文件路径
        output_dir: 输出目录
        
    Returns:
        是否成功适配
    """
    try:
        text = agent_md.read_text(encoding="utf-8")
        
        # 解析现有的 YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                content = parts[2].strip()
                
                # 解析现有字段
                name = ""
                description = ""
                color = ""
                for line in fm_text.split("\n"):
                    line = line.strip()
                    if line.startswith("name:"):
                        name = line[5:].strip()
                    elif line.startswith("description:"):
                        description = line[12:].strip()
                    elif line.startswith("color:"):
                        color = line[6:].strip()
                
                # 构建新的内容（添加 location 字段到 YAML frontmatter）
                new_content = f"""---
name: {name}
description: {description}
location: user
color: {color}
---

{content}"""
                
                # 创建输出目录：使用技能名作为子目录，文件名为SKILL.md
                # 例如：agency-agents-zh/engineering-ai-engineer/SKILL.md
                skill_name = agent_md.stem
                output_skill_dir = output_dir / skill_name
                output_skill_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_skill_dir / "SKILL.md"
                
                # 写入适配后的文件
                output_file.write_text(new_content, encoding="utf-8")
                return True
        
        # 如果没有 YAML frontmatter，创建默认的
        if not text.startswith("---"):
            lines = text.split("\n")
            title = lines[0].strip("# ").strip() if lines else agent_md.stem
            description = lines[1].strip() if len(lines) > 1 else ""
            
            new_content = f"""---
name: {title}
description: {description[:200] if description else '专家角色'}
location: user
---

{text}"""
            
            skill_name = agent_md.stem
            output_skill_dir = output_dir / skill_name
            output_skill_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_skill_dir / "SKILL.md"
            output_file.write_text(new_content, encoding="utf-8")
            return True
            
    except Exception as e:
        print(f"[错误] 适配失败: {agent_md} - {e}")
        return False
    
    return False


def scan_and_adapt_all() -> Dict[str, int]:
    """
    扫描并适配所有专家角色
    
    Returns:
        适配统计信息
    """
    if not REFERENCES_DIR.exists():
        print(f"[错误] 专家角色库目录不存在: {REFERENCES_DIR}")
        return {"total": 0, "success": 0, "failed": 0}
    
    # 创建输出目录
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    
    stats = {"total": 0, "success": 0, "failed": 0}
    
    # 扫描所有部门目录
    for dept_dir in REFERENCES_DIR.iterdir():
        if not dept_dir.is_dir() or dept_dir.name.startswith('.') or dept_dir.name in SKIP_DIRS:
            continue
        
        print(f"[扫描] 部门: {dept_dir.name}")
        
        # 扫描该部门下的所有 .md 文件
        for md_file in dept_dir.glob("*.md"):
            if md_file.name.startswith("README"):
                continue
            
            stats["total"] += 1
            rel_path = md_file.relative_to(REFERENCES_DIR)
            
            if adapt_agent_to_skill(md_file, SKILLS_DIR):
                stats["success"] += 1
                print(f"  [完成] {rel_path}")
            else:
                stats["failed"] += 1
                print(f"  [失败] {rel_path}")
    
    return stats


def copy_scripts() -> int:
    """
    复制脚本文件到技能目录
    
    Returns:
        复制的文件数量
    """
    scripts_dir = REFERENCES_DIR / "scripts"
    if not scripts_dir.exists():
        return 0
    
    output_scripts_dir = SKILLS_DIR / "scripts"
    output_scripts_dir.mkdir(parents=True, exist_ok=True)
    
    count = 0
    for script_file in scripts_dir.iterdir():
        if script_file.is_file():
            shutil.copy2(script_file, output_scripts_dir / script_file.name)
            count += 1
            print(f"[脚本] 已复制: {script_file.name}")
    
    return count


def main():
    """主函数"""
    print("=" * 60)
    print("agency-agents-zh 专家角色库适配工具")
    print("=" * 60)
    print()
    
    # 1. 适配所有专家角色
    print("[1/2] 适配专家角色...")
    stats = scan_and_adapt_all()
    print()
    print(f"[统计] 总数: {stats['total']}, 成功: {stats['success']}, 失败: {stats['failed']}")
    print()
    
    # 2. 复制脚本文件
    print("[2/2] 复制脚本文件...")
    scripts_count = copy_scripts()
    print(f"[统计] 复制脚本: {scripts_count} 个")
    print()
    
    # 3. 生成集成说明
    print("[完成] 专家角色库适配完成！")
    print()
    print("输出目录:", SKILLS_DIR)
    print()
    print("下一步:")
    print("  1. 重启 LivingTreeAI 客户端")
    print("  2. 在左侧菜单点击「技能中心」")
    print("  3. 在「专家角色」标签页浏览所有角色")
    print("  4. 点击「启用」将角色加载到对话中")
    print()


if __name__ == "__main__":
    main()
