# 关闭 oh-my-opencode 插件

## TL;DR
> **Quick Summary**: 将 opencode.jsonc 中 `plugin` 设为空数组，禁用 oh-my-openagent 插件。
> **Deliverables**: 修改后的 `C:\Users\Administrator\.config\opencode\opencode.jsonc`
> **Estimated Effort**: Quick
> **Parallel Execution**: N/A - 单文件修改

---

## Context
用户在 opencode 启动时加载了 `oh-my-openagent@latest` 插件，需要禁用它。

当前配置 (`opencode.jsonc` 第 2 行):
```jsonc
"plugin": ["oh-my-openagent@latest"],
```

---

## Work Objectives
- 禁用 oh-my-openagent 插件

---

## TODOs

- [x] 1. 将 plugin 设为空数组

  **What to do**:
  - 修改 `C:\Users\Administrator\.config\opencode\opencode.jsonc`
  - 将 `"plugin": ["oh-my-openagent@latest"],` 改为 `"plugin": [],`

  **Recommended Agent Profile**:
  - **Category**: `quick` - 单行修改，无需技能

  **Acceptance Criteria**:
  - [ ] 文件第 2 行为 `"plugin": [],`

  **QA Scenarios**:

  ```
  Scenario: 确认 plugin 已禁用
    Tool: Bash
    Steps:
      1. grep "plugin" C:\Users\Administrator\.config\opencode\opencode.jsonc
    Expected Result: 输出 `"plugin": [],`
    Evidence: .sisyphus/evidence/task-1-plugin-disabled.txt
  ```

---

## Success Criteria
- `opencode.jsonc` 中 plugin 为空数组
- 重启 opencode 后不再加载 oh-my-openagent
