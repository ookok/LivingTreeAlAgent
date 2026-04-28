# Windows 兼容性说明

本技能包含 Shell 脚本，在 Windows 上需要以下任一环境：

1. **Git Bash** (推荐) - 随 Git for Windows 安装
2. **WSL** - Windows Subsystem for Linux
3. **Cygwin** - POSIX 兼容层

## 脚本调用方式

原脚本通过 stdin 接收 JSON 输入：

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | scripts/block-dangerous-git.sh
```

在 WorkBuddy 中，通过 `execute_command` 工具调用时，
需要确保脚本路径和 JSON 转义正确。

## 注意事项

- 部分技能依赖 Claude Code 专用 Hook 系统，需要额外适配
- GitHub 相关技能需要配置 GitHub Token
- 建议优先使用纯提示词类技能（不依赖外部脚本）
