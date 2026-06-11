# oransim「上市模拟」后端开发规范

> 版本:v1.0 · 日期:2026-06-11
> 上游文档:`docs/plans/2026-06-11-launch-sim-backend-plan.md`(v1.2,下称「方案」)
> 文档定位:方案回答「做什么、为什么」;本规范回答「怎么做、红线在哪、怎么验收」。两者冲突时以方案为准,并回写修订本规范。
> 适用范围:M0–M8 全部里程碑的后端开发。前端不在范围内。

---

## 0. 阅读方式

- 每节的 **【红线】** 是不可协商的硬性约束,违反即 PR 打回;**【约定】** 是默认做法,确有理由可在 PR 描述中说明后偏离。
- 所有 `file.py:NN` 行号引用以方案 v1.2 的代码核验为基准(2026-06-11 快照),实装时若行号漂移以符号名为准。
- 第 11 节是全部红线的汇总清单,可作为 PR 自查 / Review checklist 直接使用。

---

## 1. 总则:四条铁律

整个项目的工程决策都从这四条推导。遇到规范没覆盖的情况,按铁律自行判断。

### 铁律 1 — 字节级兼容

现有 `/api/predict`、`/api/sandbox/*`、`/ws/sandbox/{sid}` 等全部接口对现有前端**字节级不变**。

- 【红线】`PredictRequest` 不新增任何字段(连带默认值的可选字段都不加);campaign API 面完全不动。
- 【红线】任何 PR 合入前必须通过 M0 建立的 `/api/predict` 黄金快照测试(见 §8.2)。
- 【红线】所有新增 `Scenario` 字段必须是 `Optional`、默认 `None`,且 `None` 时所有引擎行为与现状完全一致(如 `price_cny=None` → AOV 回退 45.0;价格特征对 `log(1)=0` 不敏感)。
- 推论:**兼容靠「新路径旁路 + 旧路径冻结」实现,不靠「改旧路径再补偿」实现**。

### 铁律 2 — 诚实原则

输出是「带标注不确定性的情景推演(scenario fiction)」,不是预测。

- 【红线】每个输出数字必须可追溯到三类来源之一:用户原话 / LLM 推断 / 系统默认。落地机制为 `provenance` + `inferred` + `default_applied` 三元标记(§3.2)。
- 【红线】`assumed_fields` 与 `grounding_confidence` 必须出现在**每一个** launch API 响应顶层(ingest、simulate、whatif 全部),不允许只在 ingest 出现。
- 【红线】竞品响应类输出(`competitor_response` 干预)永远以「分支」(labeled branch)口吻呈现,卡片固定前缀「如果竞品跟进——这是分支不是预测」;禁止预测口吻。
- 【红线】grounding 置信度低于阈值(初始 0.55)**硬拒绝**——不出 Scenario、不出报告,只返回 `clarification_questions`。禁止降级为软警告。
- 【红线】未经标定的先验(Bass p/q、价格敏感系数、launch 模式 voronoi 校准)在报告中显式标注「未经真实数据验证」。

### 铁律 3 — 薄改原则

spec pipeline 的输出是标准 `Scenario`(`backend/oransim/causal/counterfactual.py:21`);引擎侧只做方案 §4 列明的薄改。

- 【红线】新包 `spec/` 单向依赖引擎(`data/`、`config/`、`agents/`、`diffusion/`);引擎代码**禁止** import `spec/` 下任何模块。检查方式:grep 即可验证,建议在 CI 加一条 import-linter 规则。
- 【红线】以下模块**零改动**:`data/population.py`、`causal/counterfactual.ScenarioRunner`、`causal/fixed_point.py`、`causal/cate.py`、`equilibrium_under_do()`。如果实装中发现必须改,先停下来回到方案层面讨论,不许就地修改。
- 【约定】优先复用既有模式:LLM 网关复用 `call_llm_json_with_retry()`、缓存照抄 `data/world_events.py` 的 `_read_cache/_write_cache`、getter 照抄 `config/niches.py ctr_priors()`、schema 写法照抄 `data/schema/canonical.py`。**发明新机制之前,先在方案里找有没有点名的既有模式。**

### 铁律 4 — 渐进纪律

- 【红线】M0 前置于一切:在任何功能代码合入前,hash 反射测试、`/api/predict` 黄金快照、`scale_kpi` 不变量注释三件套必须先入库且绿。
- 【红线】新增 `Scenario` 字段的流程是「测试先红后绿」:先让 M0 反射测试红(字段不在 hash 也不在白名单),再把字段加进 `hash_tuple()` 让它绿。禁止先写功能后补 hash。
- 【红线】不对 `api_routers/predict.py _predict_sync()` 做大爆炸式抽取。launch 路径自建薄编排;只把确实共享的小块(macro 组装、`schema_outputs` 调用)渐进下沉到 `api_helpers.py`,`_predict_sync` 本体不动。
- 【约定】里程碑依赖顺序 `M0→(M1‖M4)→M2→M3→M5→M6→M7→M8` 不许跳跃;M4 与 M1–M3 可由不同人并行。

---

## 2. 目录与模块规范

### 2.1 新增文件清单(唯一允许的新文件落点)

| 路径 | 职责 | 里程碑 |
|---|---|---|
| `backend/oransim/spec/schema.py` | `ProductSpec` Pydantic 模型 + 忠实度元数据 | M1 |
| `backend/oransim/spec/extract.py` | LLM 抽取(双模式)+ `CATEGORY_DEFAULTS` 默认表 | M1 |
| `backend/oransim/spec/normalize.py` | 纯 Python 规整,无 LLM | M1 |
| `backend/oransim/spec/ground.py` | niche / 人群 / 替代品三映射 + 置信度闸门 | M2 |
| `backend/oransim/spec/scenario_gen.py` | 编译为 Scenario + 合成 creative + 种子事件 | M3 |
| `backend/oransim/spec/pipeline.py` | 四阶段编排(launch 版 `build_scenario`)+ spec 存储 + AudienceFilter intern | M1 骨架,M3/M7 完善 |
| `backend/oransim/diffusion/bass_saturated_hawkes.py` | Bass 饱和包装器(~50–100 行) | M5 |
| `backend/oransim/causal/launch_interventions.py` | 命名干预弹药库(7 条 do() 补丁) | M6 |
| `backend/oransim/api_routers/launch.py` | 五个 launch 端点 | M7 |
| `backend/oransim/agents/launch_outputs.py` | LaunchReport 组装(与 `schema_outputs.py` 并排) | M7 |
| `tests/golden/launch_ideas.jsonl` | ~30 条黄金集 | M1 |

- 【红线】测试放仓库根 `tests/`(与 `test_smoke.py` 并排)。**`backend/tests/` 不存在,禁止创建**——避免分裂出第二个测试根。
- 【红线】不在上表之外新建后端模块文件。确需新文件时先更新本表(PR 内一并改本规范)。
- 【约定】对既有文件的修改严格限于方案 §4 点名的位置:`counterfactual.py`(Scenario 字段 + hash)、`statistical.py`(AOV 参数化 + 价格特征 + KPI 词表)、`soul_llm.py`/`soul.py`(launch 模式)、`hawkes.py`/`neural_hawkes.py`(事件别名)、`scm.py`(两节点)、`sandbox/engine.py`(price elif + mode 标记)、`api_state.py`(UEB 源注册)、`api_helpers.py`(voronoi 票源 + 渐进下沉)、`api_schemas.py`/`api.py`(launch 模型与注册)、`config/niches.py` + `data/niches.json`(v2)、`data/schema/canonical.py`(v2 模型并排)。

### 2.2 依赖方向

```
api_routers/launch.py ──► spec/pipeline.py ──► spec/{extract,normalize,ground,scenario_gen}
                                  │
                                  ▼ (单向)
              引擎层: data/ · config/ · agents/ · diffusion/ · causal/ · sandbox/ · runtime/
```

- 【红线】引擎层不感知 `spec/` 的存在。引擎对 launch 的全部感知只通过两个通道:`Scenario` 的可选新字段,与显式参数(`mode="launch"`、`DiffusionConfig(horizon_days=90)`)。

---

## 3. 代码规范

### 3.1 Pydantic / schema 约定

- 【红线】所有新 Pydantic 模型照抄 `backend/oransim/data/schema/canonical.py` 的写法:`extra="forbid"` + 独立 `schema_version` 字段。
- 【红线】canonical 层升级走「并排新增」:`CanonicalProductSpec`、`CanonicalLaunchScenario` 与既有 v1.1 模型并排,`SCHEMA_VERSION` 升 `"2.0"`,v1.1 模型一个字符不动。
- 【约定】API 请求/响应模型统一放 `api_schemas.py`,不散落在路由文件里(与现状一致)。

### 3.2 忠实度元数据(ProductSpec 字段三元标记)

每个 ProductSpec 字段携带:

| 标记 | 含义 | 赋值规则 |
|---|---|---|
| `provenance: list[Span]` | 字符偏移,指回用户原始文本 | 仅当 LLM 能引用原文支撑片段时填写 |
| `inferred: bool` | 用户没说、LLM 推断 | 无 provenance 支撑的抽取字段**必须**置 True |
| `default_applied: bool` | 系统默认值填充 | normalize/extract 填默认值时置 True |
| (PATCH 后) `user_confirmed` | 用户在 PATCH 中修正过 | PATCH 端点改写 provenance 类型 |

- 【红线】`assumed_fields` = 所有 `inferred=True ∨ default_applied=True` 字段的派生清单,是一等公民输出。禁止把推断伪装成事实(LLM prompt 中明文约束,代码中对无 provenance 字段强制 `inferred=True`)。
- 【约定】`category_raw`、`target_user_raw`、`substitutes_raw` 逐字保留用户原话,规整结果放新字段,不覆写 raw 字段。

### 3.3 Scenario 字段与 hash 纪律(全项目最高频踩雷点)

背景:sandbox 与 CCG 缓存均以 `Scenario.hash_tuple()`(`counterfactual.py:33`)为键,漏字段 = 静默吐陈旧反事实。

- 【红线】新增字段三件套缺一不可:① dataclass 字段(Optional、默认 None);② 同步进 `hash_tuple()`;③ M0 反射测试先红后绿。本项目新增的 3 个字段(`price_cny`、`pricing_model`、`substitute_pressure`)全部进 hash。
- 【红线】**冻结白名单只许减不许增**。白名单初始 = 既有 4 个遗漏字段:`macro_ctr_lift`、`macro_cvr_lift`、`cross_platform_overlap`、`llm_calibration`(`counterfactual.py:28–31` 有字段、hash 中没有)。本项目**不修复**这 4 个遗漏(修复会改变现有缓存命中行为,违反铁律 1);也禁止任何新字段进白名单。
- 【红线】`id(audience_filter)` 陷阱的处理位置在 **`spec/pipeline.py`,不在 `hash_tuple()`**:对 `(spec_id, 修正版本号)` 做 `AudienceFilter` 实例 intern,同一 spec 版本复用同一对象。禁止改 `hash_tuple()` 里的 `id()` 语义。验收:同一 spec 版本重编译两次,`hash_tuple()` 相等(M3 单测)。

### 3.4 注释规范

- 【约定】只写**约束性注释**——代码本身表达不了的不变量。方案点名的三处必须写:
  1. `sandbox/engine.py scale_kpi`(line 194):乘法缩放不变量(revenue 随 conversions 等比缩放、无 AOV 常量,对任意固定价格保持 `revenue = conversions × price` 一致)。M0 落地。
  2. `sandbox/engine.py`(或 session 定义处):跨期可变状态守护栏——未来任何复购/流失类状态必须像 `abducted_u` 一样按 session 存快照,禁止改写共享 `POP` 单例(§7.3)。
  3. `statistical.py aggregate_kpis`:KPI 词表扩展点注释(该方法当前没有此注释,实装时一并补)。
- 【约定】不写「这行干什么」式注释;遵循全局规范(注释只陈述代码无法自表达的约束)。

---

## 4. LLM 调用规范

- 【红线】所有 LLM 调用必须走既有网关:`call_llm_json_with_retry()`(`agents/soul_llm.py:265`)+ 多供应商注册表 `agents/llm_providers/registry.py`。禁止在 `spec/` 内直接 import anthropic/openai SDK 或手搓 HTTP。
- 【红线】**双模式强制**:每个 LLM 调用点必须有 `LLM_MODE=mock` 的确定性路径,且 mock 路径不联网、CI 可绿。约定与 `soul_llm` 既有双模式一致:
  - `spec/extract.py` mock = `config/niches.py synonyms()` 关键词匹配 + `CATEGORY_DEFAULTS` 品类默认表(来源标 `default_applied`)。
  - 发布 creative 合成 mock = `bias_captions()` 模板。
  - launch 人格 mock = 镜像 soul_llm 既有 mock 模板路径。
- 【红线】成本入账:spec pipeline 的全部 LLM 调用计入 `soul_llm.py COST_TABLE_CNY` 同一账本,单请求设成本上限(超限拒绝而非静默截断)。
- 【约定】抽取 prompt 的核心约束是「带引用的抽取」:每个字段必须引用原文 span,否则标 `inferred=True`。Prompt 文案变更视为行为变更,需跑黄金集回归(§8.3)。
- 【约定】长耗时 LLM 端点(ingest、simulate)复用 `api_routers/predict.py` 的 StreamingResponse 10s keepalive 模式。

---

## 5. 数据层规范

### 5.1 niches.json v2

- 【红线】对老字段**向后兼容**:v2 只增不改不删;经 `config/niches.py` 加载,`ORAN_NICHES_PATH` 覆盖机制不动。
- 【约定】每 niche 新增字段:`reference_price`、`purchase_cycle_days`、`adoption_rate_prior`、`bass_p_prior`、`bass_q_prior`、`aov_prior`;新增 ~5 个产品品类条目(app_tool、smart_hardware、edu_service 等)并补 synonyms。
- 【约定】getter 照抄 `ctr_priors()` 模式新增三个:`reference_prices()`、`adoption_priors()`、`bass_priors()`。调用方一律走 getter,不直接读 json。
- 【约定】M4 只需 `reference_price` 最小集(price 特征依赖);其余字段 M8 补全。缺字段时必须有合理默认且报告标注「未标定」。

### 5.2 语料与 UEB 索引

- 【红线】现有 ~21.8k 合成语料(`data/synthetic/`)**不重新生成**,定位是「产品上市进入的市场环境」。
- 【约定】两个新 UEB 源统一在 `api_state.py:117 _bootstrap_index()` 注册:
  - `product_categories`:各 niche 的 `bias_captions()` 索引(grounding 嵌入兜底)。
  - `category_notes`:按 niche 的 `CanonicalNote.text` 索引(语料覆盖验证 + substitute_pressure 标定)。直接读语料文件,不依赖 platform provider 加载路径(xhs 尚无 `providers/synthetic.py`)。
- 【约定】grounding 的语料覆盖检查是置信度的一部分:grounded 品类在 `category_notes` 中无覆盖 → 拉低 `grounding_confidence` → 可触发硬拒绝。

### 5.3 缓存与存储

- 【红线】spec 存储 = 进程内 dict + `data/world_events.py` 同款文件缓存落盘,**append-only 版本化**(`{spec_id: [v0, v1, ...]}`,PATCH 即追加新版本,不原地改写)。部署假设与 `SandboxStore` 一致:**单 worker**。Redis 等多 worker 持久化显式记为不做项,禁止在本项目内私自引入。
- 【约定】spec pipeline 阶段缓存照抄 `world_events.py` 的 `_read_cache/_write_cache` 模式;TTL 与清理策略随 M7 实装时定案并回写本规范。

---

## 6. API 规范

### 6.1 端点与注册

- 【约定】五个端点全部在 `api_routers/launch.py`,在 `api.py` 现有 8 路由注册块旁注册:
  `POST /api/launch/ingest` · `PATCH /api/launch/spec/{spec_id}` · `POST /api/launch/simulate` · `POST /api/launch/sandbox` · `GET /api/launch/whatif/{spec_id}`。
- 【约定】`ingest` 只做抽取 + grounding,**不烧仿真**——它是廉价预览闸。仿真只在 `simulate` 发生。

### 6.2 响应不变量

- 【红线】每个 launch 响应顶层携带 `assumed_fields` + `grounding_confidence`(铁律 2)。
- 【红线】硬拒绝语义:置信度不足时返回非空 `clarification_questions` 且**无可模拟的 spec_id**;不返回部分报告。
- 【红线】lifecycle 例外:`api_routers/sandbox.py` 的 lifecycle 端点走 legacy `HAWKES` 单例(14 天、无别名、无饱和),launch session 调它语义错误。M7 路由完成前,launch session 调 lifecycle 返回 **409 + 指引**;路由完成后转 `bass_saturated_hawkes` + `DiffusionConfig(horizon_days=90)`。**禁止静默回退 legacy 路径**——这是「静默错误 vs 显式拒绝」的原则案例,同类情况一律显式拒绝。
- 【约定】`simulate` 的 `overrides` 暴露 `n_seeds`(默认 5,允许 1 = 单点无分位带,报告中标注)。

### 6.3 SandboxSession

- 【约定】launch 建的 session 带 `mode="launch"` 标记;既有 PATCH/counterfactual/undo 与 `/ws/sandbox/{sid}` 原样可用,价格/预算/渠道滑杆 day one 工作。mode 标记的唯一用途是 lifecycle 路由分流,不得用它在共享路径里写 if-launch 分叉逻辑(防止 mode 标记扩散成第二套引擎)。

---

## 7. 仿真层修改规范(逐模块红线)

### 7.1 `agents/statistical.py`

- 【红线】AOV 参数化:`scenario.price_cny` 非空用产品定价,空则保持 45.0——`/api/predict` 字节级不变,配显式回归测试。
- 【约定】价格特征 = `price_sens × log(price_cny / reference_price(niche))`,接在既有 `price_sens`(line 115–116)之上;`W_CLICK/W_ENGAGE/W_CONVERT`(lines 42–47)不动,只新增价格项系数;price 为空时数学上自然退化(log(1)=0)。
- 【约定】KPI 词表 = `aggregate_kpis` 内别名字典(conversions→adopters 等),launch 路径输出**双键**,campaign 路径不变。

### 7.2 `diffusion/`

- 【红线】**不新建训练模型**。神经 Hawkes checkpoint 对 90 天属 OOD,只用于 day 0–14;长尾用 parametric Hawkes + Bass 饱和包装。
- 【约定】事件别名在 `hawkes.py _event_type_idx()`(lines 76–82)与 `neural_hawkes.py _etype_idx()`(~line 357)两处同步扩展:`trial→conversion`、`wom_referral→share` 等映射到六种基类型,手法同既有 `paid_*` 前缀归一。
- 【约定】拼接用 day 10–18 线性权重混合窗(参数化),禁止 day-14 硬切。
- 【约定】`bass_saturated_hawkes.py` 实现 `DiffusionModel` ABC、注册进 `diffusion/registry.py`(名 `bass_saturated_hawkes`);饱和因子 `(1 − N(t)/m)`,`m = fan_weight_vector(POP, niche) 加权质量 × adoption_rate_prior`。M5 验收:90 天曲线出现峰值且趋平,对照闭式 Bass 曲线验证。

### 7.3 `causal/` 与 `sandbox/`

- 【红线】SCM 改动仅限加点加边(`price_point`、`launch_channel_mix` 两个 L3 节点);`substitute_pressure` 喂给**既有** `competitor_action` 节点(scm.py:53,注意图中没有叫 `competition` 的节点)——只喂值,不写竞品策略逻辑。`equilibrium_under_do()` 与 `fixed_point.py` 零改动;M6 验收含谱半径收敛检查。
- 【红线】价格反事实必须是图级 do()(经 SCM 新节点 + `ScenarioRunner.counterfactual()` Pearl 三步),**禁止 KPI 乘子 hack**。
- 【红线】`sandbox/engine.py` price elif 分支重算 revenue 基于**当前** conversions × 新价,不是 baseline 隐含的 45 元;配「价格×预算两种叠加顺序最终 revenue 一致」联动回归测试(M4 验收)。
- 【红线】**POP 单例守护栏**:任何跨期可变状态必须像 `abducted_u` 一样按 session 存快照;直接改共享 `POP` 单例会让反事实悄悄对比两个不同世界,静默破坏 Pearl 确定性。本项目不含复购/流失(已知不做项),此红线为未来扩展立的桩。
- 【约定】`launch_interventions.py` 的 7 条命名干预全部骑现有 `ScenarioRunner.counterfactual()` 与 `SandboxStore.update()` 路径,零新机制;每条干预 = 一个 do() 字典 + 一个名字,不携带自己的执行逻辑。

### 7.4 `agents/soul*.py`

- 【约定】`LAUNCH_PROMPT_TEMPLATE` 返回 `{will_try, would_pay_cny, objection, purchase_intent_7d}`(最后一项已存在);`SoulAgentPool.infer_batch()` 加 `mode="launch"` 透传,默认值保持 campaign 行为。
- 【约定】voronoi 校准换票源不换机制:launch 模式用 `will_try` 票校准 trial_prob,机制仍是 `api_helpers.py voronoi_calibration`(~line 144)。报告标注「launch 模式校准未经真实数据验证」。

---

## 8. 测试规范

### 8.1 总则

- 【红线】测试在仓库根 `tests/`;黄金集在 `tests/golden/`。
- 【红线】CI 默认 `LLM_MODE=mock` 全绿;live LLM 测试单独标记(skip-by-default)。
- 【约定】每个里程碑的验收标准(方案 §8 表格)直接转化为该 M 的测试,合入即测试存在且绿。

### 8.2 M0 三件套(一切功能代码的前置)

1. **hash 反射回归测试**:遍历 `Scenario` 的每个 dataclass field,断言「在 `hash_tuple()` 中 ∨ 在冻结白名单中」;白名单硬编码为 4 个既有遗漏,测试同时断言白名单不增长(只许减)。
2. **`/api/predict` 黄金快照**:固定输入 → 字节级输出快照;**后续每个 M 跑一次**。快照若变,要么是 bug,要么需要明示的方案级决策——不存在「顺手更新快照」。
3. **`scale_kpi` 不变量注释**(§3.4 第 1 条)。

### 8.3 黄金集(`tests/golden/launch_ideas.jsonl`)

- 【约定】~30 条口喷 idea 文本 + 期望 ProductSpec + 期望 niche key,其中**至少 3 条 B2B/SaaS 反例**(期望 = 硬拒绝)。
- 【红线】M2 门槛:品类映射准确率 **≥ 85%**(≥ 26/30),mock 与 LLM 两模式分别统计;3 条 B2B 反例必须全部被硬拒绝。
- 【约定】黄金集是回归基线:改 prompt、改 synonyms、改 grounding 阈值,都必须重跑并报告准确率变化。

### 8.4 关键回归测试清单(按里程碑)

| 测试 | 断言 | 里程碑 |
|---|---|---|
| hash 反射 | 每字段 in hash ∨ in 白名单;白名单只减不增 | M0,新增字段时先红后绿 |
| predict 快照 | `/api/predict` 字节级不变 | M0 起每 M |
| spec 字段匹配率 | mock 抽取 vs 黄金集,有基线数字 | M1 |
| 品类映射准确率 | ≥85% + B2B 反例硬拒绝 | M2 |
| Scenario 直通 | 编译产物不加修改通过 `ScenarioRunner.run()` 全程 | M3 |
| hash 幂等 | 同一 spec 版本重编译两次 hash 相等(intern 生效) | M3 |
| 价格单调性 | price±30% 在 sandbox 中 KPI 变化单调合理 | M4 |
| 价格×预算交换律 | 两种补丁叠加顺序最终 revenue 一致 | M4 |
| Bass 饱和 | 90 天曲线有峰值且趋平,对照闭式 Bass | M5 |
| SCM 收敛 | `equilibrium_under_do` 谱半径检查通过;7 条干预各出 delta | M6 |
| 端到端 | idea → ingest → PATCH → simulate → 完整 LaunchReport(三档分位带,固定 seed 集可复现);launch session lifecycle 不落 legacy | M7 |
| 标定可追溯 | 标定前后分位带变化有记录;未标定项报告有标注 | M8 |

- 【约定】涉及随机性的测试一律固定 seed(沿用 `Scenario.seed` 字段);分位带复现性是 M7 验收项,不是可选项。

---

## 9. 性能与成本规范

- 【红线】Monte Carlo 分位带的 LLM 成本控制:**LLM souls 只跑 P50 主 seed 一次**(人格引语与校准不随 seed 重采),其余 seed 走纯统计路径出经验分位数。禁止把 5–9 倍 seed 倍率乘到 LLM 调用上。
- 【约定】分位带 = `ScenarioRunner` 多 seed(默认 5,上限 9)经验分位数,分位点复用 `world_model/base.py DEFAULT_QUANTILES`(0.35/0.5/0.65)的定义;**不用** campaign 域训练的 WM checkpoint 出 launch 分位带(OOD)。可选增强:并列展示 WM 输出并标注「campaign 域模型外推,仅供参照」。
- 【约定】延迟超预算时的降级顺序:① `n_seeds` 降到 1(单点,报告标注无分位带);② 关闭 soul LLM 模式走纯统计。降级必须反映在报告标注里,不许静默降级。
- 【约定】单请求 LLM 成本上限经 `COST_TABLE_CNY` 账本执行,超限返回显式错误。

---

## 10. 报告与文案规范(LaunchReport)

- 【约定】四区块结构固定:头部假设回显 → 指标(P35/P50/P65,P35 标「下行情形」)→ 90 天时间线(含 `saturation_date` = N(t) 达 0.9m 日期)→ 谁会买(CATE 分群 + persona 引语)→ 什么会出问题(干预叙事卡 + audit_risk + 季节窗口)。
- 【红线】报告第一句固定:「这是带标注不确定性的情景推演,不是预测」。
- 【红线】三色来源标注(用户原话 / LLM 推断 / 系统默认)覆盖 ProductSpec 全字段。
- 【红线】`objection` 原话直接列为风险信号,不做改写润色(改写会破坏 provenance)。
- 【约定】`locale != zh-CN` 时在 `assumed_fields` 标注「市场环境按中国社媒市场模拟」(CN 硬编码风险,方案 §9.7)。

---

## 11. 红线汇总清单(PR 自查 / Review checklist)

**兼容**
- [ ] `/api/predict` 黄金快照绿;`PredictRequest` 未动
- [ ] 新增 Scenario 字段:Optional + 默认 None + 进 hash + 反射测试先红后绿
- [ ] 冻结白名单未增长;`hash_tuple()` 的 `id(audience_filter)` 语义未改
- [ ] 零改动模块(POP/ScenarioRunner/fixed_point/cate/equilibrium_under_do)未被触碰

**架构**
- [ ] 引擎层无任何 `import oransim.spec`
- [ ] 新文件都在 §2.1 清单内;测试在根 `tests/`
- [ ] 未对 `_predict_sync` 做抽取;下沉仅限 macro 组装 / schema_outputs 小块

**LLM**
- [ ] 所有 LLM 调用走 `call_llm_json_with_retry` + registry;有 mock 路径;CI mock 模式绿
- [ ] 成本入 `COST_TABLE_CNY` 账本;单请求有上限
- [ ] LLM souls 不随 seed 重跑(只 P50 主 seed)

**诚实**
- [ ] 每个 launch 响应顶层有 `assumed_fields` + `grounding_confidence`
- [ ] 低置信硬拒绝(无 spec_id 可模拟),不是软警告
- [ ] 竞品类输出带「分支不是预测」前缀;未标定先验有显式标注
- [ ] 无 provenance 的字段 `inferred=True`;PATCH 后 provenance 记 `user_confirmed`

**正确性**
- [ ] 价格反事实走 SCM do(),非 KPI 乘子
- [ ] sandbox price 分支按当前 conversions × 新价;价格×预算交换律测试绿
- [ ] launch session 不静默落入 legacy HAWKES(409 或正确路由)
- [ ] 无任何代码写共享 `POP` 单例的跨期状态

**数据**
- [ ] niches.json v2 只增不改不删;访问走 getter
- [ ] spec 存储 append-only 版本化;未引入 Redis 等新基础设施

---

## 12. Git 工作流

- 【约定】工作分支:从 `mod/dev` 切出 `mod/launch-m<N>-<slug>`(如 `mod/launch-m0-regression-base`),每个里程碑至少一个独立可验证的 PR 合回 `mod/dev`。upstream(OranAi-Ltd)只读,不向其推送。
- 【约定】提交信息沿用仓库现有约定(`feat(spec): ...`、`feat(diffusion): ...`、`chore(...)`),范围词用模块名:`spec` / `diffusion` / `causal` / `sandbox` / `api` / `data`。
- 【约定】每个 PR 描述包含:对应里程碑、方案章节引用(如「实现方案 §4.4」)、本规范红线自查清单(§11)勾选结果、predict 快照测试结果。
- 【约定】方案或本规范的修订与代码同 PR 提交(文档漂移当 bug 处理)。

---

## 13. 里程碑 DoD 速查

| 阶段 | 一句话 DoD(完整验收见方案 §8) |
|---|---|
| M0 | 三件套入库即绿;白名单机制生效 |
| M1 | mock 模式 CI 绿;黄金集 spec 匹配率有基线数字 |
| M2 | 品类映射 ≥85%(双模式分别统计);3 条 B2B 反例硬拒绝 |
| M3 | 编译产物直通 `ScenarioRunner.run()`;重编译 hash 幂等 |
| M4 | predict 快照不变;price±30% 单调;价格×预算交换律一致 |
| M5 | mock 人格绿;90 天曲线现峰值并趋平(对照闭式 Bass) |
| M6 | 新图上 `equilibrium_under_do` 收敛;7 条干预各出 delta |
| M7 | 一句话 idea 端到端出完整 LaunchReport(固定 seed 可复现);8 路由契约不变;lifecycle 不落 legacy |
| M8 | 标定前后分位带变化有记录;未标定项有报告标注 |

---

## 附:开放问题登记(随实装决策后回写)

来自方案 §9,实装到对应里程碑时必须给出决策并更新本规范:

1. `assumed_fields` 超过 N 项是否强制 PATCH 确认后才允许 simulate(M7 前定)。
2. v2 新增 5 品类后 grounding 阈值是否按品类分设(M8 时评估)。
3. spec 文件缓存 TTL 与清理策略(M7 实装定)。
4. launch / campaign 两条编排路径长期是否合并(launch 稳定后再议,本项目内不做)。
