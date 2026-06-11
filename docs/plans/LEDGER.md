# 上市模拟后端 · 无人值守执行账本（LEDGER）

> 这是 `/loop` 自驱执行的**唯一事实来源**。每轮循环：①读本文件找下一个未完成项 → ②实现 → ③跑验收闸 → ④回写本文件 → ⑤决定下一步。
> 上下文被压缩后，仅凭本文件即可无缝接续，不会重头来。
> 主键来自 `2026-06-11-launch-acceptance-test-cases.md` §11 出口闸表。
> 状态值：`TODO` / `IN_PROGRESS` / `BLOCKED` / `DONE`。
> 里程碑依赖序：`M0 → (M1 ‖ M4) → M2 → M3 → M5 → M6 → M7 → M8`（不许跳跃；M4 可与 M1–M3 并行）。

## 当前指针

- **当前里程碑**：M1
- **当前用例**：AT-M1-01
- **上轮结束于**：M0 全部 3 AT 绿，commit e596eff（2026-06-11）。AT-M0-02 根因修复：hash(plat)→SHA256、report_content 嵌入时间戳移除、accept.ps1 pin PYTHONHASHSEED=0。下一步：开 M1（spec schema + 骨架）。
- **全局阻塞**：无

> M-1（前置·已完成）：基线刷绿——见 DECISIONS.md。验收闸 `pwsh scripts/accept.ps1` 当前 exit 0。

## 验收闸（每个里程碑合入前必过）

- 命令：`pwsh scripts/accept.ps1`（等价：`$env:LLM_MODE='mock'; pytest tests/`）
- 必须**全绿、零网络出站**。这天然覆盖 REG-1/2/3 与已累积的全部 AT。
- M2 起额外跑 REG-5（黄金集准确率不回退）；M1 起额外跑 REG-4（引擎层无 `import oransim.spec`）。

---

## 里程碑进度表

| 里程碑 | 必绿用例 | 必跑回归 | 状态 | 备注 / 阻塞 |
|---|---|---|---|---|
| M0 | AT-M0-01…03 | — | DONE | commit e596eff 2026-06-11 |
| M1 | AT-M1-01…07 + 黄金集交付 | REG-1/2/3 | TODO | 可与 M4 并行 |
| M2 | AT-M2-01/03…07（02 发版前补） | REG-1…4 | TODO | |
| M3 | AT-M3-01…08 | REG-1…4 | TODO | |
| M4 | AT-M4-01…08 | REG-1…4 | TODO | 可与 M1–M3 并行 |
| M5 | AT-M5-01…08 | REG-1…5 | TODO | |
| M6 | AT-M6-01…07 | REG-1…5 | TODO | |
| M7 | AT-M7-01…14 | REG-1…5 | TODO | 最高优先级 e2e=AT-M7-01 |
| M8 | AT-M8-01…04 + AT-M2-02 live 复跑 | REG-1…5 全量 | TODO | M2-02 需 live LLM，留给你手动复跑 |

---

## 逐用例清单（勾选粒度）

> 实现一个用例 = 测试先红 → 写功能 → 测试绿 → 在此打 `[x]` 并附测试函数名。

### M0 — 回归地基（DONE）
- [x] AT-M0-01 hash 反射回归（单测）→ `test_at_m0_01_hash_reflection` (e596eff)
- [x] AT-M0-02 `/api/predict` 黄金快照（e2e，3 组 payload）→ `test_at_m0_02_golden_snapshot` (e596eff)
- [x] AT-M0-03 scale_kpi 乘法不变量（单测）→ `test_at_m0_03_aov_invariant` (e596eff)

### M1 — Spec schema + 骨架
- [ ] AT-M1-01 ProductSpec schema 严格性
- [ ] AT-M1-02 无 provenance 拒绝
- [ ] AT-M1-03 assumed_fields 派生正确
- [ ] AT-M1-04 mock 抽取确定性
- [ ] AT-M1-05 黄金集 spec 字段匹配率基线
- [ ] AT-M1-06 （见文档）
- [ ] AT-M1-07 CATEGORY_DEFAULTS 来源标记
- [ ] 黄金集交付 `tests/golden/launch_ideas.jsonl`

### M2 — Grounding
- [ ] AT-M2-01 品类映射准确率（mock）
- [ ] AT-M2-03 B2B 反例硬拒绝
- [ ] AT-M2-04 置信度闸门语义
- [ ] AT-M2-05 UEB 双源注册
- [ ] AT-M2-06 语料覆盖拉低置信度
- [ ] AT-M2-07 synonyms（见文档）
- [ ] AT-M2-02 品类映射准确率（live LLM）— **发版前补 / 手动**

### M3 — Scenario 生成
- [ ] AT-M3-01 编译产物直通 Scenario
- [ ] AT-M3-02 重编译 hash 幂等
- [ ] AT-M3-03 PATCH 升版后 id 行为
- [ ] AT-M3-04 合成 creative 走 make_creative
- [ ] AT-M3-05 channel（见文档）
- [ ] AT-M3-06 预算默认进 assumed_fields
- [ ] AT-M3-07 Hawkes 种子事件规模
- [ ] AT-M3-08 新字段三件套（流程+单测）

### M4 — 价格端到端（可与 M1–M3 并行）
- [ ] AT-M4-01 AOV 参数化后 predict 快照不变
- [ ] AT-M4-02 price=None 退化
- [ ] AT-M4-03 价格特征自然退化
- [ ] AT-M4-04 价格单调性
- [ ] AT-M4-05 价格×预算交换律
- [ ] AT-M4-06 price elif 用当前 context
- [ ] AT-M4-07 reference price
- [ ] AT-M4-08 决策权重冻结

### M5 — 人格 + 传播
- [ ] AT-M5-01 事件别名双处同步
- [ ] AT-M5-02 90 天 horizon
- [ ] AT-M5-03 Bass 饱和形状（核心保真度）
- [ ] AT-M5-04 拼接窗无硬接缝
- [ ] AT-M5-05 registry 注册
- [ ] AT-M5-06 市场潜量 m 的计算
- [ ] AT-M5-07 launch（见文档）
- [ ] AT-M5-08 voronoi（见文档）

### M6 — SCM + 干预弹药库
- [ ] AT-M6-01 图结构只增不改
- [ ] AT-M6-02 新图收敛
- [ ] AT-M6-03 七条命名干预各出 delta
- [ ] AT-M6-04 价格反事实是图级 do()
- [ ] AT-M6-05 substitute_pressure 接线
- [ ] AT-M6-06 competitor_response 分支口吻
- [ ] AT-M6-07 零改动模块未触碰（流程）

### M7 — API + 报告
- [ ] AT-M7-01 端到端主链路（最高优先级 e2e）
- [ ] AT-M7-02 诚实标记全覆盖（参数化全端点）
- [ ] AT-M7-03 idempotency（见文档）
- [ ] AT-M7-04 spec 存储 append-only
- [ ] AT-M7-05 硬拒绝端到端
- [ ] AT-M7-06 launch（见文档）
- [ ] AT-M7-07 lifecycle 永不静默落 legacy
- [ ] AT-M7-08 现有 8 路由契约不变
- [ ] AT-M7-09 （见文档）
- [ ] AT-M7-10 LLM souls 只跑 P50 主 seed
- [ ] AT-M7-11 成本上限显式拒绝
- [ ] AT-M7-12 报告文案红线
- [ ] AT-M7-13 引擎层依赖方向（流程+单测，REG-4）
- [ ] AT-M7-14 流式 keepalive

### M8 — 数据 v2 + 标定
- [ ] AT-M8-01 （见文档）
- [ ] AT-M8-02 新 getter 与新品类完整性
- [ ] AT-M8-03 标定可追溯
- [ ] AT-M8-04 黄金集准确率不回退（REG-5）
- [ ] AT-M2-02 live LLM 复跑 — **手动**
