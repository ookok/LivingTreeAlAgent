"""
mattpocock/skills 格式适配工具
将 Claude Code 格式的 Skills 转换为 WorkBuddy 格式

使用方式:
    python skills_adapter.py --source <source_dir> --target <target_dir> [--skill <skill_name>]
"""

import argparse
import os
import re
import shutil
from pathlib import Path
from typing import Optional


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter"""
    if not content.startswith('---'):
        return {}, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    fm_text = parts[1].strip()
    body = parts[2].strip()
    
    frontmatter = {}
    for line in fm_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, _, value = line.partition(':')
            frontmatter[key.strip()] = value.strip()
    
    return frontmatter, body


def convert_description(desc: str) -> str:
    """转换描述格式：适配 WorkBuddy 触发词"""
    # mattpocock 格式: "Use when ..." 在 description 末尾
    # WorkBuddy 格式: description 字段包含触发词列表
    return desc


def _extract_trigger_words(desc: str) -> str:
    """从原始描述中提取触发词（简化版）"""
    # 如果描述中包含 "Use when"，提取该部分
    if 'Use when' in desc:
        return desc.split('Use when')[0].strip()
    return desc[:50] + '...' if len(desc) > 50 else desc


def adapt_skill_md(source_skill_dir: Path, target_skill_dir: Path) -> bool:
    """
    适配单个技能的 SKILL.md
    返回是否成功
    """
    source_md = source_skill_dir / 'SKILL.md'
    if not source_md.exists():
        print(f"  [跳过] {source_skill_dir.name}: 无 SKILL.md")
        return False
    
    target_skill_dir.mkdir(parents=True, exist_ok=True)
    
    # 读取源文件
    content = source_md.read_text(encoding='utf-8')
    fm, body = parse_frontmatter(content)
    
    name = fm.get('name', source_skill_dir.name)
    desc = fm.get('description', '')
    
    # 构建 WorkBuddy 格式的 SKILL.md（带 YAML frontmatter）
    # WorkBuddy 需要: name, description, location 字段
    adapted_content = f"""---
name: {name}
description: {desc} (触发词: {_extract_trigger_words(desc)})
location: user
---

# {name}

> **来源**: mattpocock/skills (`{source_skill_dir.name}`)
> **原始描述**: {desc}

{body}
"""
    
    # 复制 SKILL.md（写入带 YAML frontmatter 的适配版本）
    target_md = target_skill_dir / 'SKILL.md'
    target_md.write_text(adapted_content, encoding='utf-8')
    
    # 复制其他参考文档
    for ext in ['.md', '.txt', '.json']:
        for f in source_skill_dir.glob(f'*{ext}'):
            if f.name != 'SKILL.md':
                shutil.copy2(f, target_skill_dir / f.name)
    
    # 复制 scripts 目录
    source_scripts = source_skill_dir / 'scripts'
    if source_scripts.exists():
        target_scripts = target_skill_dir / 'scripts'
        if target_scripts.exists():
            shutil.rmtree(target_scripts)
        shutil.copytree(source_scripts, target_scripts)
        
        # 为 Shell 脚本添加 Windows 兼容说明
        _add_windows_notes(target_skill_dir, source_skill_dir.name)
    
    print(f"  [完成] {source_skill_dir.name} -> {target_skill_dir}")
    return True


def _add_windows_notes(target_dir: Path, skill_name: str):
    """为包含 Shell 脚本的技能添加 Windows 兼容说明"""
    readme = target_dir / 'WINDOWS_NOTES.md'
    notes = f"""# Windows 兼容性说明

本技能包含 Shell 脚本，在 Windows 上需要以下任一环境：

1. **Git Bash** (推荐) - 随 Git for Windows 安装
2. **WSL** - Windows Subsystem for Linux
3. **Cygwin** - POSIX 兼容层

## 脚本调用方式

原脚本通过 stdin 接收 JSON 输入：

```bash
echo '{{"tool_input":{{"command":"git push origin main"}}}}' | scripts/block-dangerous-git.sh
```

在 WorkBuddy 中，通过 `execute_command` 工具调用时，
需要确保脚本路径和 JSON 转义正确。

## 注意事项

- 部分技能依赖 Claude Code 专用 Hook 系统，需要额外适配
- GitHub 相关技能需要配置 GitHub Token
- 建议优先使用纯提示词类技能（不依赖外部脚本）
"""
    readme.write_text(notes, encoding='utf-8')


def batch_adapt(source_dir: Path, target_dir: Path, skill_name: Optional[str] = None):
    """批量适配技能"""
    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    
    if skill_name:
        # 适配单个技能
        source_skill = source_dir / skill_name
        target_skill = target_dir / skill_name
        if not source_skill.exists():
            print(f"[错误] 技能目录不存在: {source_skill}")
            return
        print(f"适配单个技能: {skill_name}")
        adapt_skill_md(source_skill, target_skill)
    else:
        # 适配所有技能
        print(f"批量适配所有技能: {source_dir} -> {target_dir}")
        success = 0
        failed = 0
        for skill_dir in sorted(source_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith('.'):
                continue
            try:
                if adapt_skill_md(skill_dir, target_dir / skill_dir.name):
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  [错误] {skill_dir.name}: {e}")
                failed += 1
        
        print(f"\n总计: {success} 成功, {failed} 跳过/失败")


def create_skill_index(target_dir: Path):
    """创建适配后的技能索引"""
    target_dir = Path(target_dir)
    index_path = target_dir / 'INDEX.md'
    
    lines = [
        "# mattpocock/skills 适配索引",
        "",
        "> 自动转换自 https://github.com/mattpocock/skills",
        "> 转换工具: `client/src/business/skills_adapter.py`",
        "",
        "| 技能名 | 功能 | 依赖 | 状态 |",
        "|--------|------|------|------|",
    ]
    
    for skill_dir in sorted(target_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name == '.git':
            continue
        
        skill_md = skill_dir / 'SKILL.md'
        has_scripts = (skill_dir / 'scripts').exists()
        
        # 读取描述
        desc = ""
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            _, body = parse_frontmatter(content)
            # 取前50字作为描述
            desc = body.replace('\n', ' ')[:50]
        
        dep = "Shell脚本" if has_scripts else "纯提示词"
        status = "✅ 已适配"
        
        lines.append(f"| {skill_dir.name} | {desc} | {dep} | {status} |")
    
    lines.extend([
        "",
        "## 使用方式",
        "",
        "将技能目录复制到以下位置之一：",
        "- 用户级: `~/.workbuddy/skills/`",
        "- 项目级: `<workspace>/.workbuddy/skills/`",
        "",
        "WorkBuddy 会自动加载 `.workbuddy/skills/` 下的所有 SKILL.md 文件。",
    ])
    
    index_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\n索引已生成: {index_path}")


def main():
    parser = argparse.ArgumentParser(description='mattpocock/skills 格式适配工具')
    parser.add_argument('--source', type=str, default='.workbuddy/references/mattpocock-skills',
                        help='mattpocock/skills 仓库路径')
    parser.add_argument('--target', type=str, default='.livingtree/skills/mattpocock',
                        help='输出目录（默认：项目内置目录 .livingtree/skills/mattpocock/）')
    parser.add_argument('--skill', type=str, default=None,
                        help='适配单个技能（按名称）')
    
    args = parser.parse_args()
    
    # 处理相对路径（相对于项目根目录）
    source_dir = Path(args.source)
    target_dir = Path(args.target)
    
    if not source_dir.is_absolute():
        source_dir = Path.cwd() / source_dir
    
    if not target_dir.is_absolute():
        target_dir = Path.cwd() / target_dir
    
    if not source_dir.exists():
        print(f"[错误] 源目录不存在: {source_dir}")
        print("请先克隆仓库: git clone https://github.com/mattpocock/skills.git .workbuddy/references/mattpocock-skills")
        return
    
    print("=" * 60)
    print("mattpocock/skills → WorkBuddy 格式适配工具")
    print("=" * 60)
    print(f"\n源目录: {source_dir}")
    print(f"输出目录: {target_dir} (项目内置目录)\n")
    
    batch_adapt(source_dir, target_dir, args.skill)
    create_skill_index(target_dir)
    
    print("\n[完成] 适配完成！")
    print(f"   输出目录: {target_dir.absolute()}")
    print(f"   查看索引: {target_dir.absolute() / 'INDEX.md'}")
    print(f"\n   这些技能已作为项目内置技能集成到 LivingTreeAI。")


if __name__ == '__main__':
    main()
