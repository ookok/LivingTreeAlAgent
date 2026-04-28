---
name: tdd
description: 测试驱动开发（TDD）流程引导。当用户要求"TDD"、"测试驱动"、"红绿重构"、"test-driven"、"先写测试"时触发。支持功能开发、Bug修复的TDD循环。
location: user
---

# Test-Driven Development (TDD)

> **来源**: mattpocock/skills (`tdd`)
> **原始描述**: Test-driven development with red-green-refactor loop

## Philosophy

**Core principle**: Tests should verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs. They describe _what_ the system does, not _how_ it does it. A good test reads like a specification - "user can checkout with valid cart" tells you exactly what capability exists. These tests survive refactors because they don't care about internal structure.

**Bad tests** are coupled to implementation. They mock internal collaborators, test private methods, or verify through external means (like querying a database directly instead of using the interface). The warning sign: your test breaks when you refactor, but behavior hasn't changed. If you rename an internal function and tests fail, those tests were testing implementation, not behavior.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation.** This is "horizontal slicing" - treating RED as "write all tests" and GREEN as "write all code."

This produces **crap tests**:

- Tests written in bulk test _imagined_ behavior, not _actual_ behavior
- You end up testing the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests become insensitive to real changes - they pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: Vertical slices via tracer bullets. One test → one implementation → repeat. Each test responds to what you learned from the previous cycle. Because you just wrote the code, you know exactly what behavior matters and how to verify it.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```

## Workflow

### 1. Planning

Before writing any code:

- [ ] Confirm with user what interface changes are needed
- [ ] Confirm with user which behaviors to test (prioritize)
- [ ] Identify opportunities for [deep modules](deep-modules.md) (small interface, deep implementation)
- [ ] Design interfaces for [testability](interface-design.md)
- [ ] List the behaviors to test (not implementation steps)
- [ ] Get user approval on the plan

Ask: "What should the public interface look like? Which behaviors are most important to test?"

**You can't test everything.** Confirm with the user exactly which behaviors matter most. Focus testing effort on critical paths and complex logic, not every possible edge case.

### 2. Tracer Bullet

Write ONE test that confirms ONE thing about the system:

```
RED:   Write test for first behavior → test fails
GREEN: Write minimal code to pass → test passes
```

This is your tracer bullet - proves the path works end-to-end.

### 3. Incremental Loop

For each remaining behavior:

```
RED:   Write next test → fails
GREEN: Minimal code to pass → passes
```

Rules:

- One test at a time
- Only enough code to pass current test
- Don't anticipate future tests
- Keep tests focused on observable behavior

### 4. Refactor

After all tests pass, look for [refactor candidates](refactoring.md):

- [ ] Extract duplication
- [ ] Deepen modules (move complexity behind simple interfaces)
- [ ] Apply SOLID principles where natural
- [ ] Consider what new code reveals about existing code
- [ ] Run tests after each refactor step

**Never refactor while RED.** Get to GREEN first.

## Checklist Per Cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
```

## LivingTreeAlAgent 适配说明

本技能已适配 LivingTreeAlAgent，使用时：

1. **规划阶段**：与用户确认接口设计、测试重点
2. **红绿循环**：每轮只写一个测试 + 对应实现
3. **重构阶段**：确保所有测试通过后再重构
4. **Python 适配**：使用 `pytest` 作为测试框架

### 示例：为 LivingTreeAlAgent 添加新功能

```
用户: 用 TDD 方式实现 ModelRouter 的 fallback 机制

TDD 流程:
1. RED: 写测试 - test_fallback_when_primary_fails()
2. GREEN: 最小实现 - 在 ModelRouter 中添加 fallback 逻辑
3. REFACTOR: 优化 fallback 选择策略
4. 重复: 为其他场景写测试（全部 primary 失败、fallback 也失败等）
```

## 参考文档

- [tests.md](tests.md) - 测试示例
- [mocking.md](mocking.md) - Mock 使用指南
- [deep-modules.md](deep-modules.md) - 深模块设计
- [interface-design.md](interface-design.md) - 接口设计原则
- [refactoring.md](refactoring.md) - 重构指南
