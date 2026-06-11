# 无人值守自主决策日志（DECISIONS）

> 策略：用户已授权「遇到计划没覆盖的歧义/卡点时，按四条铁律自行决断并记录，绝不停等」。
> 每条决策一行记录：日期、上下文（哪个 AT/文件）、歧义是什么、依据哪条铁律/红线、最终决定。
> 产品级决策（黄金快照变更、置信度阈值改动、方案级取舍）即使已自行决断，也在此**显式标 `⚠ 待复核`**，回来后逐条过。

| 日期 | 上下文 | 歧义 | 依据 | 决定 | 待复核? |
|---|---|---|---|---|---|
| 2026-06-11 | （骨架搭建） | — | — | 建立 LEDGER/DECISIONS/accept.ps1/RUNBOOK | — |
| 2026-06-11 | AT-M0-02 黄金快照 · api_helpers.py | `creative_id = f"cr_{int(time.time()*1000)%100000}"` 每次调用生成不同 ID → 破坏字节级兼容 (铁律 1) | 铁律 1 (字节级兼容) | 改为 sha256(caption:style:mood:dur:celeb)[:10] 内容寻址，同一 creative 输入永远映射同一 ID。纯工程修复，无业务语义变更 | 否 |
| 2026-06-11 | AT-M0-02 黄金快照 · schema_outputs 运行 ID | `schema_outputs.*` 的 run_id/plan_id/fit_id/simulation_id 等使用 `uuid.uuid4()` 和 `time.strftime()`，每次调用不同 → 字节不稳定。`macro.world.fetched_at` 同理 | 铁律 1 (字节级兼容) 的实用解释：保护 KPI 值、字段结构，不保护运行元数据 ID | 快照比对前做 normalize 规整化（替换所有 run_id/timestamp 为占位符），再做字节比较。这等价于 "结构+数值字节级稳定"，符合 §8.2-2 的保护意图。未来 M7 可把所有 ID 改为 hash-based，届时去掉 normalize | ⚠ 待复核（M7 时把 uuid.uuid4() 改为 seed-based hash，届时可移除 normalize） |
| 2026-06-11 | M-1 基线刷绿 · tests/test_smoke.py | 基线 5 红挡住 REG-3「全绿」前提：3×`read_text` 无 encoding（GBK 炸）、1×`pytest.raises(match=)` 未 re.escape Windows 路径、1×`grep` 子进程 Windows 无此二进制 | 铁律 4（M0 前置于一切，先有绿基线）；纯测试侧 portability，不碰业务 | read_text 加 `encoding="utf-8"`；match 加 `re.escape`；grep 测试 `shutil.which("grep") is None` 时 skip（保留 CI/Linux 守门）。结果 104 passed/3 skipped/0 failed | 否（纯测试 portability，无产品语义） |
