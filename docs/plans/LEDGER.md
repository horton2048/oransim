# 上市模拟后端 · 无人值守执行账本（LEDGER）

> 这是 `/loop` 自驱执行的**唯一事实来源**。每轮循环：①读本文件找下一个未完成项 → ②实现 → ③跑验收闸 → ④回写本文件 → ⑤决定下一步。
> 上下文被压缩后，仅凭本文件即可无缝接续，不会重头来。
> 主键来自 `2026-06-11-launch-acceptance-test-cases.md` §11 出口闸表。
> 状态值：`TODO` / `IN_PROGRESS` / `BLOCKED` / `DONE`。
> 里程碑依赖序：`M0 → (M1 ‖ M4) → M2 → M3 → M5 → M6 → M7 → M8`（不许跳跃；M4 可与 M1–M3 并行）。

## 当前指针

- **当前里程碑**：M7（进行中 9/14）
- **当前用例**：AT-M7-06（sandbox 滑杆）
- **上轮结束于**：M7 已绿 9 条（AT-M7-01/02/03/04/05/08/09/12/13），commits 70f89b0/d578fe4（2026-06-12）。spec/store.py append-only 版本化存储；api_routers/launch.py 五端点（ingest/PATCH/simulate/sandbox/whatif，流式 keepalive，顶层诚实标记）；agents/launch_outputs.py LaunchReport 四区块 + 文案红线。剩余 M7：AT-M7-06（launch sandbox 滑杆复用）/07（lifecycle 409 不落 legacy）/10（LLM souls 仅 P50 主 seed）/11（成本上限显式拒绝）/14（流式 keepalive 慢路径）。
- **全局阻塞**：无
- **观察项**：AT-M0-02 黄金快照本轮第 2 次出现非复现单次字节失配（4× 隔离复测全绿，launch 路由纯新增非诱因）；累计 2 次，仍疑 bootstrap 期全局 RNG/线程瞬时态，未阻塞但值得 M8 后专项查。

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
| M1 | AT-M1-01…07 + 黄金集交付 | REG-1/2/3 | DONE | commit 44cb082 2026-06-11 |
| M2 | AT-M2-01/03…07（02 发版前补） | REG-1…4 | DONE | commit c81891d 2026-06-12；AT-M2-02 live 手动 |
| M3 | AT-M3-01…08 | REG-1…4 | DONE | commit 681cc6d 2026-06-12 |
| M4 | AT-M4-01…08 | REG-1…4 | DONE | commit b0e4e2e 2026-06-11 |
| M5 | AT-M5-01…08 | REG-1…5 | DONE | commit 26e8b46 2026-06-12 |
| M6 | AT-M6-01…07 | REG-1…5 | DONE | commit 9043b3d 2026-06-12 |
| M7 | AT-M7-01…14 | REG-1…5 | TODO | 最高优先级 e2e=AT-M7-01 |
| M8 | AT-M8-01…04 + AT-M2-02 live 复跑 | REG-1…5 全量 | TODO | M2-02 需 live LLM，留给你手动复跑 |

---

## 逐用例清单（勾选粒度）

> 实现一个用例 = 测试先红 → 写功能 → 测试绿 → 在此打 `[x]` 并附测试函数名。

### M0 — 回归地基（DONE）
- [x] AT-M0-01 hash 反射回归（单测）→ `test_at_m0_01_hash_reflection` (e596eff)
- [x] AT-M0-02 `/api/predict` 黄金快照（e2e，3 组 payload）→ `test_at_m0_02_golden_snapshot` (e596eff)
- [x] AT-M0-03 scale_kpi 乘法不变量（单测）→ `test_at_m0_03_aov_invariant` (e596eff)

### M1 — Spec schema + 骨架（DONE）
- [x] AT-M1-01 ProductSpec schema 严格性 → `test_at_m1_01_product_spec_schema_strictness` (44cb082)
- [x] AT-M1-02 无 provenance 拒绝 → `test_at_m1_02_no_provenance_must_be_inferred` (44cb082)
- [x] AT-M1-03 assumed_fields 派生正确 → `test_at_m1_03_assumed_fields_derived` (44cb082)
- [x] AT-M1-04 mock 抽取确定性 → `test_at_m1_04_mock_extract_deterministic` (44cb082)
- [x] AT-M1-05 黄金集 spec 字段匹配率基线 → `test_at_m1_05_golden_set_baseline` (44cb082)
- [x] AT-M1-06 normalize 纯函数规整 → `test_at_m1_06_normalize_functions` (44cb082)
- [x] AT-M1-07 CATEGORY_DEFAULTS 来源标记 → `test_at_m1_07_category_defaults_tagging` (44cb082)
- [x] 黄金集交付 `tests/golden/launch_ideas.jsonl` (44cb082)

### M2 — Grounding（DONE，AT-M2-02 手动留存）
- [x] AT-M2-01 品类映射准确率（mock）90.9% ≥85% → `test_at_m2_01_category_mapping_accuracy_mock`
- [x] AT-M2-03 B2B 反例硬拒绝 4/4 → `test_at_m2_03_b2b_hard_reject`
- [x] AT-M2-04 置信度闸门语义（0.55 含入）→ `test_at_m2_04_confidence_gate_semantics`
- [x] AT-M2-05 UEB 双源注册 → `test_at_m2_05_ueb_dual_source_registered`
- [x] AT-M2-06 语料覆盖拉低置信度 → `test_at_m2_06_corpus_coverage_lowers_confidence`
- [x] AT-M2-07 synonyms 优先嵌入兜底 → `test_at_m2_07_synonyms_priority_over_embedding`
- [ ] AT-M2-02 品类映射准确率（live LLM）— **发版前补 / 手动**

### M3 — Scenario 生成（DONE）
- [x] AT-M3-01 编译产物直通 Scenario → `test_at_m3_01_compiled_scenario_runs`
- [x] AT-M3-02 重编译 hash 幂等（intern）→ `test_at_m3_02_recompile_hash_idempotent`
- [x] AT-M3-03 PATCH 升版后 intern 失效 → `test_at_m3_03_patch_bumps_intern`
- [x] AT-M3-04 合成 creative 走 make_creative → `test_at_m3_04_creatives_via_make_creative`
- [x] AT-M3-05 channels_hint 覆盖默认 alloc → `test_at_m3_05_channels_hint_overrides_alloc`
- [x] AT-M3-06 预算默认进 assumed_fields → `test_at_m3_06_budget_default_in_assumed` (+06b)
- [x] AT-M3-07 Hawkes 种子事件规模 → `test_at_m3_07_hawkes_seed_scale_deterministic`
- [x] AT-M3-08 新字段三件套 → `test_at_m3_08_new_fields_default_none_behavior_unchanged`

### M4 — 价格端到端（DONE）
- [x] AT-M4-01 AOV 参数化后 predict 快照不变 → `test_at_m4_01_aov_param_snapshot_unchanged` (b0e4e2e)
- [x] AT-M4-02 price=None 退化 → `test_at_m4_02_price_none_numeric_equiv` (b0e4e2e)
- [x] AT-M4-03 价格特征自然退化 → `test_at_m4_03_price_feature_natural_degradation` (b0e4e2e)
- [x] AT-M4-04 价格单调性 → `test_at_m4_04_price_monotonicity` (b0e4e2e)
- [x] AT-M4-05 价格×预算交换律 → `test_at_m4_05_price_budget_commutativity` (b0e4e2e)
- [x] AT-M4-06 price elif 用当前 context → `test_at_m4_06_price_elif_uses_current_conversions` (b0e4e2e)
- [x] AT-M4-07 reference price → `test_at_m4_07_reference_price_getter` (b0e4e2e)
- [x] AT-M4-08 决策权重冻结 → `test_at_m4_08_decision_weights_frozen` (b0e4e2e)
- [x] AT-M4-01b 新字段进 hash → `test_at_m4_01b_new_scenario_fields_in_hash` (b0e4e2e)

### M5 — 人格 + 传播（DONE）
- [x] AT-M5-01 事件别名双处同步 → `test_at_m5_01_event_alias_sync` (+01b)
- [x] AT-M5-02 90 天 horizon → `test_at_m5_02_90day_horizon`
- [x] AT-M5-03 Bass 饱和形状（核心保真度）→ `test_at_m5_03_bass_saturation_shape`
- [x] AT-M5-04 拼接窗无硬接缝 → `test_at_m5_04_splice_window_no_hard_seam`
- [x] AT-M5-05 registry 注册 → `test_at_m5_05_registry_registration`
- [x] AT-M5-06 市场潜量 m 的计算 → `test_at_m5_06_market_potential_m`
- [x] AT-M5-07 launch 人格模式 → `test_at_m5_07_launch_persona_mode`
- [x] AT-M5-08 voronoi 换票源 → `test_at_m5_08_voronoi_calibration_vote_source` (+08b)

### M6 — SCM + 干预弹药库（DONE）
- [x] AT-M6-01 图结构只增不改 → `test_at_m6_01_graph_additive_only`
- [x] AT-M6-02 新图收敛 → `test_at_m6_02_new_graph_converges`
- [x] AT-M6-03 八条命名干预各出 delta → `test_at_m6_03_named_interventions_deltas`
- [x] AT-M6-04 价格反事实是图级 do() → `test_at_m6_04_price_is_graph_level_do`
- [x] AT-M6-05 substitute_pressure 接线 → `test_at_m6_05_substitute_pressure_wiring`
- [x] AT-M6-06 competitor_response 分支口吻 → `test_at_m6_06_competitor_response_is_branch`
- [x] AT-M6-07 零改动模块未触碰 → `test_at_m6_07_protected_modules_untouched`

### M7 — API + 报告（进行中 9/14）
- [x] AT-M7-01 端到端主链路 → `test_at_m7_01_end_to_end_main_chain` (d578fe4)
- [x] AT-M7-02 诚实标记全覆盖 → `test_at_m7_02_honesty_markers_all_endpoints` (d578fe4)
- [x] AT-M7-03 ingest 不烧仿真 → `test_at_m7_03_ingest_no_simulation` (d578fe4)
- [x] AT-M7-04 spec 存储 append-only → `test_at_m7_04_spec_store_append_only` (70f89b0)
- [x] AT-M7-05 硬拒绝端到端 → `test_at_m7_05_hard_reject_e2e` (d578fe4)
- [ ] AT-M7-06 launch sandbox 滑杆可用
- [ ] AT-M7-07 lifecycle 永不静默落 legacy
- [x] AT-M7-08 现有 8 路由契约不变 → `test_at_m7_08_existing_routes_unchanged` (d578fe4)
- [x] AT-M7-09 n_seeds 降级显式化 → `test_at_m7_09_n_seeds_degradation` (d578fe4)
- [ ] AT-M7-10 LLM souls 只跑 P50 主 seed
- [ ] AT-M7-11 成本上限显式拒绝
- [x] AT-M7-12 报告文案红线 → `test_at_m7_12_report_copy_redlines` (d578fe4)
- [x] AT-M7-13 引擎层依赖方向（REG-4）→ `test_at_m7_13_engine_no_spec_import` (70f89b0)
- [ ] AT-M7-14 流式 keepalive

### M8 — 数据 v2 + 标定
- [ ] AT-M8-01 （见文档）
- [ ] AT-M8-02 新 getter 与新品类完整性
- [ ] AT-M8-03 标定可追溯
- [ ] AT-M8-04 黄金集准确率不回退（REG-5）
- [ ] AT-M2-02 live LLM 复跑 — **手动**
