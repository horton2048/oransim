# 无人值守执行运行手册（LOOP-RUNBOOK）

> 目的：让 Claude 在你离开后，于本机自驱推进 `docs/plans/` 的开发与验收计划，从 M0 跑到 M8。
> 已配置：本机 `/loop` 自驱 · 全程你决策（自行决断并记录，绝不停等）· bypass 权限。

## 一次性骨架（已就位）

- `docs/plans/LEDGER.md` —— 唯一事实来源（进度账本，里程碑 + 逐 AT 用例 + 当前指针）。
- `docs/plans/DECISIONS.md` —— 自主决策日志；产品级决策标 `⚠ 待复核`。
- `scripts/accept.ps1` —— 验收闸（mock 全绿 / 可加 `-Reg4`）。纯 ASCII，抗 GBK 码页。
- 基线已刷绿：M-1 修掉 5 个 Windows 平台测试 portability bug（见 DECISIONS）。当前 `104 passed, 3 skipped, 0 failed`。

## 离开前你要做的 3 步

1. **确认电脑不休眠**：电源设置 → 睡眠 → 接通电源时「永不」。合盖也设为不休眠（否则进程冻结）。
2. **切到 bypass 权限模式**：在 Claude Code 里切到 “bypass permissions” 模式（你已选定此姿态），否则我会卡在授权弹窗。
3. **粘贴下面的 `/loop` 启动指令**，回车后离开。

## 启动指令（复制整段粘贴给 Claude）

```
/loop 按 docs/plans/LEDGER.md 自驱推进上市模拟后端开发与验收。每一轮：
1. 读 LEDGER.md 找到「当前指针」指向的下一个未完成 AT 用例（遵守里程碑依赖序 M0→(M1‖M4)→M2→M3→M5→M6→M7→M8，不跳跃）。
2. 对照三份文档实现：方案(plan) > 规范(dev-spec) > 用例集(test-cases) 优先级；严守四条铁律与全部红线。
3. 纪律：先写测试让它红 → 写功能让它绿（新 Scenario 字段必须先红后绿、进 hash_tuple）。测试落 tests/（禁止 backend/tests/），mock 模式。
4. 跑验收闸 `pwsh scripts/accept.ps1`（M1 起加 -Reg4）。必须全绿（含已累积 AT + REG 回归）才算过；红则修到绿，绝不顺手更新黄金快照。
5. 回写 LEDGER.md：勾选完成的用例、更新「当前指针」「上轮结束于」。
6. 遇到计划没覆盖的歧义：按四条铁律自行决断、在 DECISIONS.md 记一行；产品级决策（黄金快照变更/置信度阈值/方案级取舍）即使已决断也标「⚠ 待复核」继续，绝不停等。
7. 每完成一个 AT 用例就 git commit（mod/dev 分支，遵守 fork 工作流，提交信息引用 AT 编号）。一个里程碑全绿再进下一个。
8. 若验收闸连续 3 轮无法转绿且非产品级阻塞，在 LEDGER「全局阻塞」记下卡点与已试方案，跳到同里程碑下一个可独立推进的 AT，不空转。
持续循环直到 LEDGER 全部里程碑 DONE（AT-M2-02 live LLM 与 AT-M8 的 live 复跑除外——那两个需真实 LLM，标注留给我手动复跑）。
```

## 你回来后

1. 看 `LEDGER.md` —— 进度一目了然（当前指针 + 勾选状态）。
2. 过 `DECISIONS.md` 里所有 `⚠ 待复核` 行 —— 这是我替你做的产品级决断，逐条确认或回滚。
3. 跑 `git log --oneline` 看提交链；要回滚某步直接 revert 对应 commit。
4. AT-M2-02 / M8 live 复跑：设 `LLM_MODE=api` + key，手动跑一次。

## 故障恢复

- 进程被杀 / 机器重启后：重新粘贴同一条 `/loop` 指令即可。LEDGER 是事实来源，会从「当前指针」无缝接续，不会重做已勾选的用例。
- 上下文被压缩：同理，LEDGER + DECISIONS 让我恢复全部状态。
- 验收闸编码报错：accept.ps1 已纯 ASCII；若新写 .ps1 仍要避免非 ASCII，或存为 UTF-8 with BOM。
