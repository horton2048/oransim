# oransim「上市模拟」验收测试用例集

> 版本：v1.0 · 日期：2026-06-11
> 上游文档：`2026-06-11-launch-sim-backend-plan.md`（方案 v1.2）+ `2026-06-11-launch-sim-backend-dev-spec.md`（规范 v1.0），均在本目录。
> 文档定位：把方案 §8 的验收标准与规范 §8/§11 的红线展开成**逐条可执行的测试用例**。每个用例可直接转写为 pytest 测试；用例 ID 即测试函数名后缀（如 `AT-M0-01` → `test_at_m0_01_hash_reflection`）。
> 冲突时优先级：方案 > 规范 > 本文档（发现冲突回写修订本文档）。

---

## 0. 全局约定

| 约定 | 内容 |
|---|---|
| 测试位置 | 仓库根 `tests/`（与 `test_smoke.py` 并排）；黄金集在 `tests/golden/`。**禁止创建 `backend/tests/`** |
| CI 模式 | 默认 `LLM_MODE=mock` 全绿；live LLM 用例统一标 `@pytest.mark.live_llm`，skip-by-default |
| 随机性 | 一律固定 seed（沿用 `Scenario.seed`）；涉及分位带的用例固定 seed 集（如 `[42, 43, 44, 45, 46]`） |
| 数值容差 | 字节级断言用于 API 快照；浮点比较默认 `rel_tol=1e-9`，蒙特卡洛/曲线形状类放宽并在用例中写明 |
| 用例类型 | `单测` / `集成`（多模块内存内）/ `e2e`（TestClient 走 HTTP 面）/ `流程`（靠 PR 流程与 CI guard 保证，不是 pytest） |
| 建议文件落点 | 见 §10 映射表 |

### 0.1 每个里程碑必跑的回归集（缺一不可合入）

| 编号 | 内容 | 来源 |
|---|---|---|
| REG-1 | AT-M0-01 hash 反射测试绿 | 规范 §8.2 |
| REG-2 | AT-M0-02 `/api/predict` 黄金快照字节级不变 | 铁律 1 |
| REG-3 | `LLM_MODE=mock` 下全部已入库测试绿（无网络出站） | 规范 §4 |
| REG-4 | AT-M7-13 引擎层无 `import oransim.spec`（M1 起生效） | 规范 §2.2 |
| REG-5 | 黄金集准确率不回退（M2 起生效；改 prompt/synonyms/阈值时必须报告变化） | 规范 §8.3 |

---

## 1. M0 — 回归地基

### AT-M0-01 hash 反射回归 · 单测
- **验证**：`Scenario` 每个 dataclass field 要么影响 `hash_tuple()`，要么在冻结白名单中；白名单只许减不许增。
- **步骤**：
  1. `dataclasses.fields(Scenario)` 枚举全部字段；
  2. 对每个非白名单字段：构造两个仅该字段取值不同的 Scenario，断言 `hash_tuple()` 不同；
  3. 对白名单字段（`macro_ctr_lift`、`macro_cvr_lift`、`cross_platform_overlap`、`llm_calibration` 四个，硬编码在测试内）：同法构造，断言 hash **相同**（确认确实没进 hash——白名单是事实陈述不是许可）；
  4. 断言测试内白名单集合 ⊆ 上述 4 个（防止有人往白名单里加新字段）。
- **特例**：`audience_filter` 字段按 `id()` 语义单独断言——同一对象 hash 相同、不同对象（即使内容相等）hash 不同。该语义被 M3 的 intern 依赖，禁止改。
- **通过判据**：入库即绿；后续任何新增 Scenario 字段未进 hash 时必须先红。
- **依据**：方案 §4.1；规范 §3.3、§8.2-1。

### AT-M0-02 `/api/predict` 黄金快照 · e2e
- **验证**：campaign 路径字节级兼容。
- **步骤**：
  1. 固定 PredictRequest payload（固定 caption/budget/alloc/seed，`LLM_MODE=mock`）；
  2. TestClient 调 `/api/predict`，收齐完整响应体；
  3. 与入库快照文件做**字节级**比对（JSON 不重排序、不重格式化）。
- **通过判据**：完全一致。快照若变，要么是 bug 要么是方案级决策——PR 中**禁止**「顺手更新快照」，更新必须单独说明并引用方案修订。
- **覆盖输入**：至少 3 组 payload（单平台 / 多平台 / 带 competitors 字段），防止单一样本碰巧不过新代码路径。
- **依据**：铁律 1；规范 §8.2-2。

### AT-M0-03 scale_kpi 乘法不变量 · 单测 + 流程
- **验证**：`sandbox/engine.py scale_kpi`（line 194）保持「revenue 随 conversions 等比缩放」的乘法不变量，且不变量注释已落地。
- **步骤**：
  1. 行为断言：构造 KPI dict（含 revenue/conversions），跑预算 fast_approx 分支，断言 `revenue/conversions` 比值（= 隐含单价）缩放前后不变；
  2. 流程断言：注释存在（grep 关键字，CI 轻量检查或 review checklist 项）。
- **通过判据**：比值不变（`rel_tol=1e-9`）；注释入库。
- **依据**：方案 §4.7（v1.2 修正）；规范 §3.4-1。

---

## 2. M1 — Spec schema + 骨架

### AT-M1-01 ProductSpec schema 严格性 · 单测
- **验证**：`extra="forbid"` 生效、`schema_version` 存在。
- **步骤**：构造含未知字段的 payload → 断言 ValidationError；合法 payload → 断言 `schema_version` 非空。
- **依据**：规范 §3.1。

### AT-M1-02 无 provenance 必为 inferred · 单测
- **验证**：忠实度三元标记的强制逻辑——「禁止把推断伪装成事实」在代码层兜底。
- **步骤**：构造一个 `provenance=[]` 且 `inferred=False` 的字段赋值路径 → 断言被拒绝或被强制改为 `inferred=True`。
- **依据**：铁律 2；规范 §3.2。

### AT-M1-03 assumed_fields 派生正确 · 单测
- **验证**：`assumed_fields` = 全部 `inferred=True ∨ default_applied=True` 字段，不多不少。
- **步骤**：构造混合 spec（2 个用户原话字段 + 2 个 inferred + 1 个 default_applied）→ 断言 assumed_fields 恰为后 3 个。
- **依据**：方案 §3.1。

### AT-M1-04 mock 抽取确定性 · 单测
- **验证**：`LLM_MODE=mock` 下同一文本两次抽取产出完全相同的 ProductSpec（不联网）。
- **步骤**：同一 idea 文本调 `spec/extract.py` 两次 → 断言深度相等；测试环境封锁网络出站（socket guard fixture）。
- **依据**：规范 §4 双模式强制。

### AT-M1-05 黄金集 spec 字段匹配率基线 · 集成
- **验证**：mock 抽取 vs `tests/golden/launch_ideas.jsonl` 期望 spec，有可复现的基线数字。
- **步骤**：遍历黄金集 → 抽取 → 按字段比对（product_name/category_raw/price_point 等核心字段）→ 输出匹配率。
- **通过判据**：M1 不设阈值，但基线数字必须落盘（写入测试输出或基线文件），M2 起回归比较。
- **依据**：方案 §8 M1 验收。

### AT-M1-06 normalize 纯函数规整 · 单测
- **验证**：币种→CNY、价格夹紧、枚举强制、raw 字段逐字保留不覆写。
- **步骤**：输入 `price_point={amount: 9.9, currency: "USD"}` → 断言转 CNY 并标记；输入非法 pricing model 枚举 → 断言强制/拒绝；断言 `category_raw` 等 raw 字段与输入逐字一致。
- **依据**：方案 §3.3；规范 §3.2 约定。

### AT-M1-07 CATEGORY_DEFAULTS 来源标记 · 单测
- **验证**：默认表填充的字段 `default_applied=True` 且进 assumed_fields。
- **步骤**：输入不含预算/价格的 idea → mock 抽取 → 断言相应字段标记正确。
- **依据**：方案 §3.2。

### 黄金集本体要求（AT-M1 前置交付物）
`tests/golden/launch_ideas.jsonl` ~30 条，每条 `{idea_text, expected_spec, expected_niche_key}`；其中**至少 3 条 B2B/SaaS 反例**（`expected_niche_key: null, expect_reject: true`）。覆盖要求：≥8 个不同 niche、长短文本混合（50 字以内 / 500 字以上各 ≥3 条）、至少 2 条含明确价格、至少 2 条含替代品提及、至少 2 条 locale 非 zh-CN。

---

## 3. M2 — Grounding

### AT-M2-01 品类映射准确率（mock）· 集成
- **验证**：黄金集 niche key 映射准确率 **≥ 85%**（27 条正例中按比例折算 ≥ 23 条正确；若正例恰 27 条则 ≥ 23）。
- **步骤**：`LLM_MODE=mock` 遍历黄金集正例 → `spec/ground.py` → 比对 expected_niche_key → 准确率断言。
- **依据**：方案 §8 M2 验收；规范 §8.3。

### AT-M2-02 品类映射准确率（live LLM）· 集成 `@live_llm`
- 同 AT-M2-01，`LLM_MODE` 走真实供应商；skip-by-default，发版前手动跑，准确率分别记录。

### AT-M2-03 B2B 反例硬拒绝 · 集成
- **验证**：3 条 B2B/SaaS 反例**全部**被硬拒绝。
- **步骤**：逐条过 pipeline → 断言：无 Scenario 产出、无可模拟 spec_id、`clarification_questions` 非空。
- **通过判据**：3/3，一条漏过即失败（这是方案明令禁止的失败模式：B2B 被静默映射到消费垂类）。
- **依据**：方案 §3.4；规范 §6.2。

### AT-M2-04 置信度闸门语义 · 单测
- **验证**：`grounding_confidence < 0.55` → 硬拒绝，不是软警告。
- **步骤**：构造（或 monkeypatch）一个置信度 0.54 的 grounding 结果 → 断言 pipeline 不产出 Scenario；0.56 → 正常产出。边界值 0.55 本身的行为写明（建议 `>=` 通过）并固定为回归。
- **依据**：铁律 2。

### AT-M2-05 UEB 双源注册 · 集成
- **验证**：`_bootstrap_index()` 后 BUS 中存在 `product_categories` 与 `category_notes` 两个源，且可检索。
- **步骤**：启动 api_state 引导 → 对两源各发一次检索 → 断言返回非空且来源标记正确。
- **依据**：规范 §5.2。

### AT-M2-06 语料覆盖拉低置信度 · 单测
- **验证**：grounded 品类在 `category_notes` 无覆盖 → `grounding_confidence` 下降，可触发硬拒绝。
- **步骤**：构造一个 synonyms 能命中、但语料零覆盖的伪品类 → 断言置信度低于有覆盖品类，且低到阈下时拒绝。
- **依据**：方案 §5.2；规范 §5.2。

### AT-M2-07 synonyms 优先于嵌入兜底 · 单测
- **验证**：关键词命中时不走嵌入路径（确定性优先）。
- **步骤**：用含明确 synonyms 关键词的文本 → mock 下断言走关键词分支（嵌入检索调用计数为 0，spy/monkeypatch）。
- **依据**：方案 §3.4 表 (a)。

---

## 4. M3 — Scenario 生成

### AT-M3-01 编译产物直通 ScenarioRunner · 集成
- **验证**：spec pipeline 产出的 Scenario **不加任何修改**通过 `ScenarioRunner.run()` 全程。
- **步骤**：黄金集取 3 条不同 niche 的正例 → 编译 → `ScenarioRunner.run()` → 断言无异常、产出 `ScenarioResult` 且 `abducted_u` 非空。
- **依据**：方案 §2 数据流不变量；§8 M3 验收。

### AT-M3-02 重编译 hash 幂等（intern 生效）· 单测
- **验证**：同一 `(spec_id, 修正版本号)` 重编译两次，`hash_tuple()` 相等。
- **步骤**：同一 spec 编译两次 → 断言两个 Scenario 的 `hash_tuple()` 相等（隐含 AudienceFilter 是同一实例：`assert s1.audience_filter is s2.audience_filter`）。
- **依据**：方案 §4.1；规范 §3.3。

### AT-M3-03 PATCH 升版后 intern 失效 · 单测
- **验证**：spec 修正版本号 +1 后重编译产生**新** AudienceFilter 实例，hash 改变（旧缓存不再命中——语义正确性，不是性能）。
- **步骤**：编译 v0 → PATCH 改 target_user → 编译 v1 → 断言 filter 实例不同、hash 不同。
- **依据**：规范 §3.3。

### AT-M3-04 合成 creative 走 make_creative · 单测
- **验证**：每平台 1–3 条发布 creative，全部经 `make_creative()`——含 64 维 `content_emb`、`audit_risk`、category_hint。
- **步骤**：编译一条含 2 平台 channels_hint 的 spec → 断言每平台 creative 数 ∈ [1,3]、`content_emb` 维度 = 64、audit_risk 字段存在。
- **依据**：方案 §3.5。

### AT-M3-05 channels_hint 覆盖默认 alloc · 单测
- **验证**：用户给了渠道 hint 时优先；没给时按 niche `audience_skew` 先验。
- **步骤**：两条 spec（有/无 hint）分别编译 → 断言 alloc 来源不同且 hint 版与 hint 一致；无 hint 版 alloc 进 assumed_fields。
- **依据**：方案 §3.5。

### AT-M3-06 预算默认进 assumed_fields · 单测
- **验证**：无 budget_hint 时由价格点 + ctr_priors 推导，且标 `default_applied`。
- **依据**：方案 §3.5。

### AT-M3-07 Hawkes 种子事件规模 · 单测
- **验证**：上市日种子脉冲规模 = `budget_to_impressions()` 折算（同预算同平台 → 同规模，确定性）。
- **依据**：方案 §3.5。

### AT-M3-08 新字段三件套 · 流程 + 单测
- **验证**：`price_cny`、`pricing_model`、`substitute_pressure` 三字段 Optional、默认 None、已进 hash（AT-M0-01 自动覆盖）；全 None 时编译出的 Scenario 经 `ScenarioRunner.run()` 与改造前行为一致。
- **流程项**：PR 历史可见「反射测试先红后绿」（红 commit 与绿 commit 分开或在 PR 描述中说明）。
- **依据**：铁律 1/4；规范 §3.3。

---

## 5. M4 — 价格端到端

### AT-M4-01 AOV 参数化后 predict 快照不变 · e2e
- **验证**：`statistical.py` 改造后 REG-2 仍字节级绿（`price_cny=None` 路径 = 旧行为）。
- **依据**：铁律 1；规范 §7.1。

### AT-M4-02 price=None 数值等价 · 单测
- **验证**：`aggregate_kpis(price_cny=None)` 与旧实现（45.0 硬编码）输出**数值完全相等**（不只快照层，函数层也断言）。
- **步骤**：固定 events 输入 → 新旧逻辑（旧逻辑以期望值固化在测试内）比对 revenue/roi 全部键。
- **依据**：规范 §7.1 红线。

### AT-M4-03 价格特征自然退化 · 单测
- **验证**：`price_cny=None` 或 `price_cny == reference_price(niche)` 时价格特征为 0（log(1)=0），convert logit 与现状一致。
- **步骤**：三组对照（None / 等于参考价 / 2 倍参考价）跑 `simulate()` 固定 seed → 前两组 conversion 概率逐 agent 相等；第三组不等。
- **依据**：规范 §7.1。

### AT-M4-04 价格单调性 · 集成
- **验证**：sandbox 中 price +30% → adopters/conversions 单调下降；−30% → 单调上升；方向与幅度合理（下降幅度 > 0 且 < 100%）。
- **步骤**：建 session → PATCH `price_cny` ±30% → 比对 KPI。固定 abducted noise（沿用 price elif 的廉价重算路径）。
- **依据**：方案 §8 M4 验收。

### AT-M4-05 价格×预算交换律 · 集成
- **验证**：「先价格补丁后预算补丁」与「先预算后价格」最终 revenue 一致。
- **步骤**：同一 session 两份副本 → 路径 A：patch(price=+30%) → patch(budget=2x)；路径 B：patch(budget=2x) → patch(price=+30%) → 断言最终 `total_kpis.revenue` 相等（`rel_tol=1e-6`，fast_approx 与 price 重算均为确定性）。
- **依据**：方案 §4.7（v1.2 修正）；规范 §7.3 红线。

### AT-M4-06 price elif 用当前 conversions · 单测
- **验证**：price 补丁重算 revenue = **当前** session conversions × 新价，而非 baseline 隐含 45 元。
- **步骤**：先 budget 补丁改变 conversions → 再 price 补丁 → 断言 revenue == 补丁后 conversions × 新价。
- **依据**：规范 §7.3。

### AT-M4-07 reference_price getter 与缺省 · 单测
- **验证**：`config/niches.py reference_prices()` getter 可用；niche 缺 `reference_price` 字段时有合理默认且结果带「未标定」标注。
- **依据**：规范 §5.1。

### AT-M4-08 决策权重冻结 · 单测
- **验证**：`W_CLICK/W_ENGAGE/W_CONVERT`（statistical.py:42–47）数值与改造前一致（常量快照断言），只允许新增价格项系数。
- **依据**：方案 §4.2。

---

## 6. M5 — 人格 + 传播

### AT-M5-01 事件别名双处同步 · 单测（参数化）
- **验证**：`trial→conversion`、`adoption→conversion`、`wom_referral→share` 在 `hawkes.py _event_type_idx()` 与 `neural_hawkes.py _etype_idx()` **两处映射一致**。
- **步骤**：参数化遍历全部别名 × 两个函数 → 断言索引相等；再断言两函数对六种基类型 + `paid_*` 前缀的既有行为不回归。
- **依据**：方案 §4.4；规范 §7.2。

### AT-M5-02 90 天 horizon · 单测
- **验证**：`DiffusionConfig(horizon_days=90)` 下 forecast `daily_buckets` 长度 = 90；默认 config 仍为 14（campaign 不变）。
- **依据**：方案 §4.4。

### AT-M5-03 Bass 饱和形状 · 集成（核心保真度用例）
- **验证**：`bass_saturated_hawkes` 的 90 天曲线出现峰值且趋平。
- **步骤**（固定 seed、固定 p/q/m）：
  1. 累计采纳 N(t) 单调不减且 **N(90) ≤ m**；
  2. 日新增曲线存在峰值日 `t_peak ∈ (0, 90)`，且 `t_peak` 后 7 日均值 < 峰值的 80%（趋平判据）；
  3. 对照同参数闭式 Bass 曲线：累计曲线逐日相对误差在容差带内（建议 ±15%，Hawkes 随机性所致，容差写死在测试里作回归基线）；
  4. 饱和因子边界：构造 N(t) 接近 m 的状态 → 断言强度趋零。
- **依据**：方案 §4.4、§8 M5 验收；规范 §7.2。

### AT-M5-04 拼接窗无硬接缝 · 单测
- **验证**：day 10–18 线性混合后，强度/日新增序列在 day 14 附近无跳变。
- **步骤**：固定 seed 生成完整 90 天序列 → 断言 day 9–19 区间的一阶差分绝对值 ≤ 区间外（day 2–9 与 day 19–30）一阶差分最大值 ×1.5（无突变判据，系数固化为回归基线）。
- **依据**：方案 §4.4。

### AT-M5-05 registry 注册 · 单测
- **验证**：`get_diffusion_model("bass_saturated_hawkes")` 返回实现 `DiffusionModel` ABC 的实例；既有 `parametric_hawkes`/`causal_neural_hawkes` 注册不受影响。
- **依据**：规范 §7.2。

### AT-M5-06 市场潜量 m 的计算 · 单测
- **验证**：`m = fan_weight_vector(POP, niche) 加权质量 × adoption_rate_prior(niche)`；不同 niche 产出不同 m；POP 单例未被写入。
- **步骤**：两个 niche 各算一次 m → 断言公式成立、互不相等；前后对 POP 关键数组做 checksum 断言未变。
- **依据**：方案 §4.4；规范 §7.3 POP 守护栏。

### AT-M5-07 launch 人格模式 · 单测
- **验证**：`infer_batch(mode="launch")` mock 路径返回 `{will_try, would_pay_cny, objection, purchase_intent_7d}` 四键齐全且类型正确；**默认 mode（不传参）行为与改造前完全一致**（campaign 回归）。
- **依据**：方案 §4.3；规范 §7.4。

### AT-M5-08 voronoi 校准换票源 · 单测
- **验证**：launch 模式 `voronoi_calibration` 用 `will_try` 票校准 trial_prob；campaign 模式仍用点击票（行为不变，spy 断言票源字段）。
- **依据**：方案 §4.3；规范 §7.4。

---

## 7. M6 — SCM + 干预弹药库

### AT-M6-01 图结构只增不改 · 单测
- **验证**：新图 = 旧图 + `price_point`、`launch_channel_mix` 两节点及其边；旧图全部节点与边原样存在（图 diff 断言）。
- **步骤**：改造前节点/边清单固化为测试内期望集合 → 断言新图 ⊇ 旧图、新增恰为两节点。
- **依据**：方案 §4.5；规范 §7.3。

### AT-M6-02 新图收敛 · 单测
- **验证**：`equilibrium_under_do()` 在新图上收敛，`fixed_point.py` 谱半径检查通过（< 1）。
- **步骤**：对 baseline 与每条命名干预各跑一次 equilibrium → 断言收敛标志、无超迭代上限。
- **依据**：方案 §8 M6 验收。

### AT-M6-03 七条命名干预各出 delta · 集成（参数化）
- **验证**：`launch_interventions.py` 全部 7 条（organic_only / price_up_30 / price_down_30 / channel_concentration / no_kol_launch / bad_market / compliance_block / competitor_response——注意 price 上下行算 2 条时共 8 个 do() 字典，按方案 §4.6 表为准）逐条跑通并产出非空 KPI delta。
- **方向性断言**（语义合理性，固定 seed）：`price_up_30` → adopters 下降；`price_down_30` → 上升；`no_kol_launch` → reach 下降；`organic_only` → paid 事件为 0。
- **依据**：方案 §4.6、§8 M6 验收。

### AT-M6-04 价格反事实是图级 do() · 单测
- **验证**：价格干预走 `ScenarioRunner.counterfactual()` Pearl 三步（abduction 保留）：同 seed 下 baseline 与 do(price) 两个世界共享 abducted U（spy 断言 `abducted_u` 复用，且无任何代码路径对 KPI 直接乘系数）。
- **依据**：规范 §7.3 红线「禁止 KPI 乘子 hack」。

### AT-M6-05 substitute_pressure 接线 · 单测
- **验证**：`substitute_pressure` 喂给**既有** `competitor_action` 节点（scm.py:53）；值为 None 时该节点行为与现状一致。
- **依据**：方案 §4.5（v1.2 修正：图中无 `competition` 节点）。

### AT-M6-06 competitor_response 分支标注 · 单测
- **验证**：该干预的输出对象带「分支」标记，渲染文案含固定前缀「如果竞品跟进——这是分支不是预测」。
- **依据**：铁律 2；方案 §4.6。

### AT-M6-07 零改动模块未触碰 · 流程
- **验证**：`data/population.py`、`ScenarioRunner.counterfactual()`、`causal/fixed_point.py`、`causal/cate.py`、`equilibrium_under_do()` 的 git diff 为空（CI guard：对这些路径 diff 非空时要求 PR 带方案修订说明）。
- **依据**：规范 §1 铁律 3。

---

## 8. M7 — API + 报告

### AT-M7-01 端到端主链路 · e2e（最高优先级用例）
- **验证**：一句话 idea → `POST /ingest` → `PATCH /spec/{id}` → `POST /simulate` → 完整 LaunchReport。
- **步骤**（`LLM_MODE=mock`，固定 seed 集 `[42..46]`）：
  1. ingest 黄金集一条正例 → 拿到 spec_id、assumed_fields、grounding ≥ 阈值；
  2. PATCH 修正一个字段 → 断言 provenance 变 `user_confirmed`、grounding 重算、版本 +1；
  3. simulate → 断言 LaunchReport 四区块齐全：头部假设回显（三色来源标注覆盖全字段）/ 指标（P35/P50/P65 三档，P35 标「下行情形」）/ 90 天时间线（90 个点 + peak_day + half_life + saturation_date）/ 谁会买（CATE 分群 + persona 引语）/ 什么会出问题（干预叙事卡 + audit_risk + 季节窗口）；
  4. **复现性**：同一请求再跑一次 → 报告数值字节级一致（固定 seed 集）。
- **依据**：方案 §7、§8 M7 验收。

### AT-M7-02 诚实标记全覆盖 · e2e（参数化全端点）
- **验证**：ingest / PATCH / simulate / sandbox / whatif **五个端点**响应顶层均有 `assumed_fields` + `grounding_confidence`。
- **依据**：铁律 2；规范 §6.2。

### AT-M7-03 ingest 不烧仿真 · 单测
- **验证**：ingest 全程零 `ScenarioRunner.run()` 调用（spy 计数 = 0）。
- **依据**：规范 §6.1。

### AT-M7-04 spec 存储 append-only · 单测
- **验证**：PATCH 追加新版本而非原地改写：`{spec_id: [v0, v1]}`，v0 可回读且与 PATCH 前逐字相等；文件缓存落盘走 `_read_cache/_write_cache` 模式；重启进程（重新加载缓存）后版本链完整。
- **依据**：规范 §5.3。

### AT-M7-05 硬拒绝端到端 · e2e
- **验证**：低置信 idea（B2B 反例）ingest → 响应含非空 `clarification_questions`、**无 spec_id**；用伪造 spec_id 调 simulate → 显式 4xx，不产出部分报告。
- **依据**：规范 §6.2。

### AT-M7-06 launch sandbox 滑杆可用 · e2e
- **验证**：`POST /api/launch/sandbox` 建 session（`mode="launch"`）后，既有 `/api/sandbox/*` 的 price/budget/alloc PATCH、counterfactual、undo 与 `/ws/sandbox/{sid}` 全部可用。
- **步骤**：建 session → 依次 PATCH 三种滑杆断言 KPI 变化 → undo 断言回退 → WebSocket 连接收到更新帧。
- **依据**：方案 §6；规范 §6.3。

### AT-M7-07 lifecycle 永不静默落 legacy · e2e（双向）
- **验证**：
  1. launch session 调 lifecycle 端点 → **409 + 指引**（路由完成前）或 90 天 Bass 路径结果（路由完成后），二者必居其一，**任何情况下不返回 legacy HAWKES 14 天结果**（断言响应 horizon=90 或状态码 409）；
  2. campaign session 调 lifecycle → 行为与改造前完全一致（快照比对）。
- **依据**：方案 §4.7；规范 §6.2 红线。

### AT-M7-08 现有 8 路由契约不变 · e2e
- **验证**：OpenAPI schema 中既有 8 路由（adapters/analysis/health/predict/sandbox/ueb/v2/ws）的路径、方法、请求/响应模型与改造前快照一致；launch 路由为纯新增。
- **依据**：铁律 1。

### AT-M7-09 n_seeds 降级显式化 · e2e
- **验证**：`overrides.n_seeds=1` → 报告无分位带且带「单点、无分位带」标注；默认 n_seeds=5 → 三档分位带齐全；n_seeds>9 → 显式拒绝或夹紧（行为写死并回归）。
- **依据**：方案 §9 风险 8；规范 §6.2、§9。

### AT-M7-10 LLM souls 只跑 P50 主 seed · 单测
- **验证**：n_seeds=5 时 soul LLM 调用次数 = 1 个 seed 的量（spy 计数）；其余 seed 走纯统计路径。
- **依据**：规范 §9 红线。

### AT-M7-11 成本上限显式拒绝 · 单测
- **验证**：把单请求成本上限 monkeypatch 到极低 → 请求返回显式错误（非静默截断、非部分结果）；成本计入 `COST_TABLE_CNY` 同一账本（账本条目存在断言）。
- **依据**：规范 §4。

### AT-M7-12 报告文案红线 · 单测（参数化）
- **验证**：① 报告第一句逐字 ==「这是带标注不确定性的情景推演，不是预测」；② P35 行带「下行情形」；③ 竞品卡前缀逐字匹配；④ `objection` 原话与 persona 输出逐字一致（未润色）；⑤ `locale != zh-CN` 时 assumed_fields 含「市场环境按中国社媒市场模拟」。
- **依据**：规范 §10。

### AT-M7-13 引擎层依赖方向 · 流程 + 单测
- **验证**：grep/import-linter 断言引擎层（data/ config/ agents/ diffusion/ causal/ sandbox/ runtime/）无任何 `import oransim.spec` 或 `from oransim.spec`；CI 常驻。
- **依据**：规范 §2.2。

### AT-M7-14 流式 keepalive · e2e
- **验证**：ingest 与 simulate 走 StreamingResponse，慢路径下（monkeypatch 注入延迟）客户端按 ~10s 间隔收到 keepalive 帧，连接不超时。
- **依据**：规范 §4。

---

## 9. M8 — 数据 v2 + 标定

### AT-M8-01 niches.json v2 向后兼容 · 单测
- **验证**：v2 对老字段只增不改不删——老字段逐键值与 v1 相等（JSON diff）；`ctr_priors()` 等既有 getter 输出不变；REG-2 predict 快照仍绿。
- **依据**：规范 §5.1 红线。

### AT-M8-02 新 getter 与新品类完整性 · 单测
- **验证**：`reference_prices()` / `adoption_priors()` / `bass_priors()` 对**全部** niche（含新增 ~5 品类）返回完整值；新增品类各有非空 synonyms；任何缺字段走默认 + 「未标定」标注。
- **依据**：规范 §5.1。

### AT-M8-03 标定可追溯 · 集成
- **验证**：标定前后同一固定输入的分位带变化有落盘记录（before/after 对照文件或测试基线）；未标定项在报告中有显式标注；标定来源标注「合成数据自标定，非真实校准」。
- **依据**：方案 §5-6、§9 风险 3；规范 §8.4。

### AT-M8-04 黄金集准确率不回退 · 集成
- **验证**：新增品类与 synonyms 后重跑 AT-M2-01 → 准确率仍 ≥ 85%；3 条 B2B 反例仍全部硬拒绝；若黄金集为覆盖新品类而扩充，新条目计入分母。
- **依据**：规范 §8.3。

---

## 10. 用例 → 测试文件落点建议

| 测试文件（仓库根 `tests/`） | 覆盖用例 |
|---|---|
| `test_launch_m0_regression.py` | AT-M0-01/02/03 |
| `test_launch_spec_schema.py` | AT-M1-01…07 |
| `test_launch_grounding.py` | AT-M2-01…07（live 用例同文件标 marker） |
| `test_launch_scenario_gen.py` | AT-M3-01…08 |
| `test_launch_pricing.py` | AT-M4-01…08 |
| `test_launch_diffusion.py` | AT-M5-01…06 |
| `test_launch_souls.py` | AT-M5-07/08 |
| `test_launch_interventions.py` | AT-M6-01…06 |
| `test_launch_api_e2e.py` | AT-M7-01…09/14 |
| `test_launch_report.py` | AT-M7-12 |
| `test_launch_guards.py` | AT-M7-10/11/13、AT-M6-07（CI guard 类） |
| `test_launch_niches_v2.py` | AT-M8-01…04 |
| `tests/golden/launch_ideas.jsonl` | 黄金集本体（§2 末交付物要求） |

---

## 11. 验收签收表（里程碑合入时逐项勾选）

| 里程碑 | 必绿用例 | 必跑回归 | 签收人 |
|---|---|---|---|
| M0 | AT-M0-01…03 | — | |
| M1 | AT-M1-01…07 + 黄金集交付 | REG-1/2/3 | |
| M2 | AT-M2-01/03…07（02 发版前补） | REG-1…4 | |
| M3 | AT-M3-01…08 | REG-1…4 | |
| M4 | AT-M4-01…08 | REG-1…4 | |
| M5 | AT-M5-01…08 | REG-1…5 | |
| M6 | AT-M6-01…07 | REG-1…5 | |
| M7 | AT-M7-01…14 | REG-1…5 | |
| M8 | AT-M8-01…04 + AT-M2-02 live 复跑 | REG-1…5 全量 | |
