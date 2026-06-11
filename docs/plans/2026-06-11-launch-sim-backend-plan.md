# oransim 后端改造方案：从「营销活动 ROI 模拟」到「梦想产品上市模拟」

> 版本：v1.2 · 日期：2026-06-11 · 范围：仅后端实现逻辑（前端暂不改动，现有 `/api/predict`、`/api/sandbox/*` 等全部接口保持字节级兼容）
>
> v1.2 变更：对照代码逐条核验（~45 处引用）后修正 4 处事实偏差——① `sandbox/engine.py scale_kpi` 并无 45.0 AOV 常量，相关"修复"重写为联动测试（§4.7/M0/M4）；② SCM 节点名统一为实际存在的 `competitor_action`（§4.5/§4.6/M6）；③ `_CATEGORY_KW` 实际位于 `data/creatives.py:47` 而非 macro.py（§3.4）；④ `aggregate_kpis` 并无"已注明的扩展点"注释（§4.2）。并补两个缺口：spec 存储决策（§6）、多 seed Monte Carlo 成本（§9 风险 8）。
>
> 核心思路：**新增一条「自由文本 → ProductSpec → Scenario」的编译管线（spec pipeline），把用户的口喷想法编译成现有引擎已经认识的 `Scenario` 对象**，让 agent 社会、do() 因果引擎、Hawkes 传播、LLM 人格几乎原封不动地继续工作；仿真层只做「薄改」（价格、人格 prompt、事件别名、饱和长尾、两个 SCM 节点）。
>
> 产出过程：6 个子系统并行精读 → 3 份独立设计（minimal-delta / spec-pipeline / market-dynamics）→ 3 位评审打分（70:69:61，spec-pipeline 胜出）→ 综合 + 完整性复核（5 个缺口已在本版修复）。

---

## 1. 产品愿景与新旧对照

**旧产品**：输入一条广告创意 + 预算 + 平台分配 → 模拟营销活动的 ROI 与反事实。
**新产品**：输入一句话/一段口喷的梦想产品 idea → 模拟「这个产品做出来推向市场后会发生什么」：90 天采纳曲线、收入轨迹、谁会买、什么会出问题。

| 现有概念（campaign 域） | 新概念（product launch 域） | 实现层落点 |
|---|---|---|
| `PredictRequest`（结构化广告请求） | 自由文本 idea → `ProductSpec`（LLM 抽取 + grounding） | 新包 `backend/oransim/spec/` |
| `CreativeInput.caption`（广告文案） | 合成「发布笔记」creative（产品在 feed 中的样子），1–3 条/平台 | `spec/scenario_gen.py` → 复用 `data/creatives.make_creative()` |
| `kol_niche`（达人垂类） | 产品品类（grounding 到 niche 注册表） | `backend/oransim/config/niches.py` + `data/niches.json` v2 |
| `total_budget`（投放预算） | 上市营销预算（用户给 hint 或按品类默认表推断，进 `assumed_fields`） | `Scenario.total_budget` 原字段 |
| `platform_alloc`（平台分配） | 上市渠道组合（go-to-market channel mix） | `Scenario.platform_alloc` 原字段 |
| KOL（投放达人） | 上市种子合作方/早期布道者 | `data/kols.pick_kol_by_spec()` 原逻辑 |
| `conversion`（广告转化） | `adoption`（采纳/购买），事件别名 `trial`/`adoption`/`wom_referral` | `diffusion/hawkes.py _event_type_idx()` 别名扩展 |
| revenue = conversions × 固定 AOV 45 元 | revenue = adopters × **产品定价** `price_cny` | `agents/statistical.py:147,166` 参数化 |
| 隐式 price_sens 项（`statistical.py:116`） | 一等公民价格敏感特征：`log(price / 品类参考价)` | `agents/statistical.py` convert logit |
| persona「会不会点这条广告」 | persona「会不会试用/愿付多少钱/有什么顾虑」 | `agents/soul_llm.py` 新增 launch prompt 模板 |
| 14 天 engagement 级联 | 90 天采纳曲线，**带 Bass 饱和上限**（不再无限增长） | `diffusion/` 新增饱和包装模型 |
| 100k 消费者 panel（受众） | 同一 panel = **可触达市场**（addressable market），加权质量 = Bass 市场潜量 m | `data/population.py` 不改 |
| 反事实滑杆（预算/分配/创意） | 上市滑杆：价格 / 渠道 / 预算 / 不请 KOL / 延期 | `sandbox/engine.py` 加一个 elif |
| 输出：campaign ROI 报告 | 输出：`LaunchReport`（指标 + 时间线 + 谁买 + 风险叙事，全部带来源标注） | 新 `agents/launch_outputs.py` |

**诚实原则（贯穿全文档）**：输出是「带标注不确定性的情景推演（scenario fiction）」，不是预测。每个数字必须可追溯到「用户原话 / LLM 推断 / 系统默认」三类来源之一。

---

## 2. 总体架构：新增 pipeline 全景图

```
用户口喷 idea（1~5000 字自由文本）
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  新包 backend/oransim/spec/  （4 阶段编译管线）                    │
│                                                                  │
│  extract.py ──► normalize.py ──► ground.py ──► scenario_gen.py    │
│  LLM 结构化抽取    纯Python规整     对齐现有分类体系    编译成 Scenario  │
│  (带出处span/      (币种/枚举/      (niche注册表 +     (合成发布creative │
│   inferred标记)    默认值标记)      人群桶 + UEB嵌入)    +渠道+KOL+种子事件)│
│                                                                  │
│  置信度不足 ──► 硬拒绝，返回 clarification_questions（不出报告）      │
└────────────────────────────┬────────────────────────────────────┘
                             │  标准 Scenario（+price_cny 等可选新字段）
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  现有引擎（基本不动）                                              │
│                                                                  │
│  data/creatives.make_creative() ── 64维内容嵌入/audit_risk 原样复用  │
│  platforms/xhs world_model_legacy ─ 曝光分发原样复用（现行 live 路径）│
│  agents/statistical.py ─────────── [薄改] 价格进 convert logit      │
│  agents/soul.py + soul_llm.py ──── [薄改] launch 人格 prompt 模式    │
│  causal/counterfactual.ScenarioRunner ── Pearl 三步反事实，零改动     │
│  causal/scm.py ─────────────────── [薄改] +price_point 等 2 个节点   │
│  diffusion/ ────────────────────── [薄改] 事件别名 + Bass 饱和长尾    │
│  sandbox/engine.py ─────────────── [薄改] price 补丁 elif 分支       │
│  causal/cate.py ────────────────── 买家分群，零改动复用              │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  新路由 api_routers/launch.py                                     │
│  /ingest → /spec PATCH(人工确认) → /simulate → /sandbox → /whatif  │
│                                                                  │
│  新 agents/launch_outputs.py → LaunchReport                       │
│  (指标带分位带 │ 90天时间线 │ 谁买 │ 风险叙事，全字段带 provenance)     │
└─────────────────────────────────────────────────────────────────┘
```

数据流关键不变量：**spec pipeline 的输出是一个标准 `Scenario`（`backend/oransim/causal/counterfactual.py:21`）**。任何拿 `Scenario` 工作的现有代码（ScenarioRunner、sandbox、CCG、SCM mediator）天然兼容上市场景。

---

## 3. Idea 摄入层：自由文本 → ProductSpec

新包 `backend/oransim/spec/`，五个模块，从左到右编排。每一阶段输出 JSON，**每个字段带 confidence 与 provenance**，保证忠实度可审计。

### 3.1 `spec/schema.py` — ProductSpec 模型

Pydantic 模型，模式照抄 `backend/oransim/data/schema/canonical.py` 的写法（`extra="forbid"`、独立 `schema_version`）：

```
ProductSpec:
  product_name: str
  one_liner: str
  category_raw: str            # 用户原话，逐字保留
  target_user_raw: str
  price_point: {amount, currency, model: one_time|subscription|freemium}
  differentiation: list[str]
  substitutes_raw: list[str]   # 用户提到的替代品/竞品
  channels_hint: list[str]
  value_props: list[str]
  # —— 忠实度元数据（每个字段一份）——
  confidence: float
  provenance: list[Span]       # 字符偏移，指回原始文本
  inferred: bool               # 用户没说、LLM 推断的字段必须置 True
  default_applied: bool        # 系统默认值填充的字段
```

派生属性 `assumed_fields` → 所有 `inferred=True` 或 `default_applied=True` 的字段清单。**该清单是一等公民输出，出现在每一个 API 响应和报告头部**（「以下是模拟器替你猜的所有内容」）。

### 3.2 `spec/extract.py` — LLM 抽取

- 一次结构化 JSON 调用，**完全复用现有 LLM 网关**：`call_llm_json_with_retry()`（已验证位于 `backend/oransim/agents/soul_llm.py:265`，自带重试与 JSON 解析）+ 多供应商注册表 `backend/oransim/agents/llm_providers/registry.py`（anthropic / openai_compat / gemini / qwen_dashscope 已就绪）。
- Prompt 约束为「带引用的抽取」：每个抽出的字段必须引用原文支撑片段（产出 provenance span），否则标 `inferred=True`。禁止把推断伪装成事实。
- **确定性 mock 路径**：`LLM_MODE=mock` 时走关键词匹配（`config/niches.py synonyms()`）+ **按品类的默认预算/价格表**（新增于 `spec/extract.py` 内的 `CATEGORY_DEFAULTS` 字典，来源标 `default_applied`），与 soul_llm 既有的双模式约定一致，保 CI 绿。
- 成本核算复用 `soul_llm.py` 的 `COST_TABLE_CNY`，抽取调用计入同一账本。

### 3.3 `spec/normalize.py` — 纯 Python 规整（无 LLM）

币种→CNY、价格夹紧、枚举强制、中英标签统一（复用 `backend/oransim/config/niches.py` 的 `en_to_zh()/zh_to_en()`）、替代品去重、默认值填充并打 `default_applied` 标记。

### 3.4 `spec/ground.py` — 对齐现有语料分类体系

三个映射，全部 ground 到**已存在**的分类资产上：

| 映射 | 目标体系 | 方法 |
|---|---|---|
| (a) category → niche key | `data/niches.json`（经 `config/niches.py` 加载，repo 根目录 `data/` 下，可由 `ORAN_NICHES_PATH` 覆盖） | 先 `synonyms()` 关键词命中；未命中则嵌入余弦兜底：用 `backend/oransim/runtime/embedding_bus.py` 的 BUS，把各 niche 的 `bias_captions()` 索引为新 BUS 源 `product_categories`（注册点：`backend/oransim/api_state.py:117 _bootstrap_index()`）。交叉验证：用 `agents/kol_content_match.detect_niche_from_caption`（即 `api_helpers.build_scenario` 第 48–77 行已有的 caption 嗅探逻辑）二次核对 LLM 的品类抽取 |
| (b) target_user → AudienceFilter | `backend/oransim/data/population.py` 的 `AGE_BUCKETS`/`CITY_TIER`/`OCCUPATION` 桶 + `data/fan_profile.py NICHE_PRIORS` 软加权 | 桶映射 + `fan_weight_vector()` 复权（与今天 KOL 垂类定向同一机制） |
| (c) substitutes → 竞争上下文 | `api_schemas.py:50-52` 已有的 `own_brand`/`category`/`competitors` 字段 + category_hint（`_CATEGORY_KW` 位于 `data/creatives.py:47`，是 `niches.synonyms()` 的派生字典外加 apparel_warm/delivery 两条目，经 `make_creative()` 生效——与 (a) 的 synonyms 命中高度重复，(c) 不再单独做关键词匹配；季节性由 `data/macro.py` 的 `_HOLIDAYS`/`season_factor()` 经 category_hint 生效） | 名称匹配 + 嵌入检索语料（见 §5） |

输出 `grounding_confidence ∈ [0,1]`。**低于阈值（建议 0.55）硬拒绝**：不出 Scenario，返回 `clarification_questions`（如「这是 B2B 工具还是消费品？」「定价大概多少？」）。这是闸门不是警告——B2B SaaS 被静默映射到美妆 niche 是本方案明令禁止的失败模式。

### 3.5 `spec/scenario_gen.py` + `spec/pipeline.py` — 编译为 Scenario

- **合成发布 creative**：每平台 1–3 条「发布笔记」文案（LLM 按 grounded niche 的语气写；mock 模式用 `bias_captions()` 模板），全部走 `backend/oransim/data/creatives.make_creative()`——64 维内容嵌入、audit_risk 合规检测、category_hint 逻辑原封不动生效。
- **渠道分配**：按 grounded niche 从 `data/platforms.py` 的 `audience_skew` 先验取默认 `platform_alloc`；用户 `channels_hint` 优先。
- **KOL 种子**：`data/kols.pick_kol_by_spec()` 按品类选上市合作达人。
- **预算默认**：由价格点 + 品类 CTR 先验（`ctr_priors()`）推导，进 `assumed_fields`。
- **Hawkes 种子事件**：上市日曝光脉冲，规模由 `data/platforms.budget_to_impressions()` 折算。
- 最终输出五元组：`(ProductSpec, Scenario, launch_creatives, seed_events, clarification_questions)`。
- 阶段缓存照抄 `data/world_events.py` 的 `_read_cache/_write_cache` 文件缓存模式。
- `pipeline.py` 在 launch 路径上扮演 `api_helpers.build_scenario()` 在 campaign 路径上的角色。

### 3.6 黄金测试集

`tests/golden/launch_ideas.jsonl`（新增；测试在仓库根 `tests/` 下，与 `test_smoke.py` 等并排——**不是** `backend/tests/`，该目录不存在）：~30 条口喷 idea 文本 + 期望 ProductSpec + 期望 niche key。M1 起作为回归基线，M2 用它量化品类映射准确率。

---

## 4. 仿真层修改：逐模块改动

原则：**编译产物就是引擎认识的对象，仿真侧只做薄改**。每条改动列真实文件。

### 4.1 `backend/oransim/causal/counterfactual.py` — Scenario 扩展

- `Scenario`（line 21）新增**可选**字段：`price_cny: float | None`、`pricing_model: str | None`、`substitute_pressure: float | None`（由 grounded 替代品 + 语料注意力基线标定，见 §5）。默认 `None`，campaign 路径零影响。
- **`hash_tuple()`（line 33）必须同步纳入全部新字段**。sandbox 与 CCG 缓存均以此为键，漏一个字段就静默吐陈旧反事实。
- **既有哈希债务（完整性复核发现，必须在 M0 处理）**：当前 `hash_tuple()` 已经遗漏 4 个既有字段——`macro_ctr_lift`、`macro_cvr_lift`、`cross_platform_overlap`、`llm_calibration`（counterfactual.py:28–31 有字段、33–41 的 hash 中没有）。本方案**不修复**这 4 个遗漏（修复会改变现有 CCG/sandbox 缓存命中行为，违反字节级兼容承诺），而是把它们固化为**显式冻结白名单**：M0 的反射回归测试 = 「`Scenario` 的每个 dataclass field 要么在 hash 中、要么在冻结白名单中；白名单只许减不许增」。任何新增字段（含本节 3 个）必须进 hash，测试先红后绿。
- **`id(audience_filter)` 陷阱（同上发现）**：hash 用 `id(self.audience_filter)`（line 38），对象身份而非内容。campaign 路径中 filter 对象在 session 内复用所以可行；但 spec pipeline 每次重编译都会生成新的 `AudienceFilter` 对象，**launch 场景将永远 hash 不命中**（缓存全失效，性能劣化但不出错）。M3 处理：launch 路径在 `spec/pipeline.py` 内对 `(spec_id, 修正版本号)` 做 AudienceFilter 实例 intern（同一 spec 版本复用同一对象），不改 `hash_tuple()` 本身。

### 4.2 `backend/oransim/agents/statistical.py` — 价格机制 + KPI 词表

- `aggregate_kpis()` 当前硬编码 `conv_value_cny: float = 45.0`（line 147）、`revenue = conversions * conv_value_cny`（line 166）。改为：`scenario.price_cny` 非空时用产品定价，否则保持 45.0 默认——**`/api/predict` 行为字节级不变，配显式回归测试**。
- **价格敏感一等公民化**：`simulate()` 第 115–116 行已有 `price_sens = 1.0 - income` 并以 0.3 权重进特征栈（line 120）。把它升级为由 `log(price_cny / reference_price)` 驱动的真实特征：`price_feature = price_sens * log(price / niches.reference_price(niche))`，price 为空时退化为现状（系数对 log(1)=0 不敏感即可保兼容）。`reference_price` 来自 niches.json v2（§5）。`W_CLICK/W_ENGAGE/W_CONVERT`（lines 42–47）不动，只新增价格项系数。
- KPI 词表映射：在 `aggregate_kpis` 中新增一个 `kpi_schema` 别名字典（conversions→adopters，conversion_rate→adoption_rate），launch 路径输出双键，campaign 路径不变。（注：该方法当前**没有**词表扩展点注释，实装时一并补注释。）

### 4.3 `backend/oransim/agents/soul_llm.py` + `agents/soul.py` — 上市人格模式

- `soul_llm.py` 新增 `LAUNCH_PROMPT_TEMPLATE`：persona 看到的是「合成发布笔记 + 定价」，返回 `{will_try, would_pay_cny, objection, purchase_intent_7d}`（最后一个字段已存在）。mock 模板路径镜像现有实现。
- `agents/soul.py SoulAgentPool.infer_batch()` 增加 `mode="launch"` 参数透传。
- **校准闭环（嫁接自 market-dynamics 设计）**：`api_helpers.py` 的 `voronoi_calibration`（~line 144）今天用 LLM 点击票校准统计 click_prob；launch 模式下改用 `will_try` 票校准 trial_prob——同一 Voronoi 加权机制，换票源即可。M5 落地，并在报告中标注「launch 模式校准未经真实数据验证」。

### 4.4 `backend/oransim/diffusion/` — 事件别名 + 90 天 + Bass 饱和

- **不新建训练模型**。事件别名：扩展 `diffusion/hawkes.py _event_type_idx()`（lines 76–82 的 `paid_*` 前缀归一逻辑）与 `neural_hawkes.py _etype_idx()`（~line 357），把 `trial`/`adoption`/`wom_referral` 映射到六种基类型（trial→conversion、wom_referral→share 等）。
- launch 路径构造 `DiffusionConfig(horizon_days=90, event_types=...)`——`diffusion/base.py:32` 已参数化，无需改基类。
- **拼接策略**：神经 Hawkes checkpoint 训练于 14 天 engagement 流，90 天属 OOD。day 0–14 用 `causal_neural_hawkes` 预测；长尾用 `diffusion/registry.py` 的 `parametric_hawkes`。为消除 day-14 硬接缝：day 10–18 用线性权重混合两条强度曲线（参数化拼接窗），而非硬切。
- **新文件 `backend/oransim/diffusion/bass_saturated_hawkes.py`（嫁接自 market-dynamics 设计，~50–100 行）**：实现 `DiffusionModel` ABC 的薄包装器，注册进 `diffusion/registry.py`（名 `bass_saturated_hawkes`）。内部持有 parametric Hawkes，对其强度乘以饱和因子 `(1 − N(t)/m)`，其中 `N(t)` = 累计 adoption 事件数、`m` = 市场潜量 = `fan_weight_vector(POP, niche)` 加权质量 × niches.json v2 的 `adoption_rate_prior`。**这是整个方案性价比最高的保真度修复**：90 天采纳曲线不再永远增长，会出现峰值与饱和拐点。Bass p/q 先验来自 niches.json v2 字段（§5），未标定前在报告中显式标注。
- 收入时间线 = 每日 `conversion` 桶 × `price_cny`。

### 4.5 `backend/oransim/causal/scm.py` — 两个新节点

- 新增两个 L3 可干预节点：`price_point`、`launch_channel_mix`；`substitute_pressure` 接入既有 L1 外生 `competitor_action` 节点（scm.py line 53 已存在；注意图中**没有**名为 `competition` 的节点，实际节点名就是 `competitor_action`，本方案只给它喂值，不写策略逻辑）。
- `equilibrium_under_do()` 与不动点求解器（`causal/fixed_point.py`）**零改动**——新节点只是图上加点加边。
- 命名上市干预（price_cut / no_kol_launch / delay_launch）就是 `do()` 字典，走现有 `ScenarioRunner.counterfactual()` 与 `/api/predict_v1/intervene` 同款路径。价格反事实因此是**图级 do()**，不是 KPI 乘子 hack。

### 4.6 新文件 `backend/oransim/causal/launch_interventions.py` — 命名干预弹药库（嫁接自 minimal-delta 设计）

固化一组命名 do() 补丁，全部骑现有 `ScenarioRunner.counterfactual()`（保留 abducted U 的 Pearl 三步）与 `SandboxStore.update()` 路径，零新机制：

| 名称 | do() 内容 | 回答的问题 |
|---|---|---|
| `organic_only` | neural_hawkes `counterfactual_forecast(intervention={'treatment_boost_factor': 0})` | 一分钱不投，它自己传得开吗？（白送的能力） |
| `price_up_30` / `price_down_30` | `do(price_point = ±30%)` 经 SCM 新节点 | 价格弹性 |
| `channel_concentration` | 把某平台 alloc 归零/全压 | 渠道依赖度 |
| `no_kol_launch` | `kol_per_platform = None` | 不请达人会怎样 |
| `bad_market` | `data/macro.py sentiment_factor` 取负面 | 市场情绪逆风 |
| `compliance_block` | creative `audit_risk` 触发路径（`make_creative()` 已有） | 合规被卡 |
| `competitor_response` | `competitor_action` 节点干预 + `equilibrium_under_do()` | **标注为分支**：「如果有竞品快速跟进…」 |

**产品诚实规则（逐字执行）**：竞品响应类输出永远以「分支」（labeled branch）呈现，禁止以预测口吻呈现。

### 4.7 `backend/oransim/sandbox/engine.py` — 价格滑杆

- `SandboxStore.update()`（line 97 起，分发树位于 ~139–232）新增一个 `elif`：补丁键含 `price_cny` → 廉价重算路径（固定 abducted noise 重跑 convert logit + 按新价重算 revenue，手法同既有预算 Hill 饱和分支）。
- **scale_kpi 澄清（v1.2 代码核验修正）**：评审两次点名的「scale_kpi 固定 AOV」经核验为**误报**——`scale_kpi`（engine.py:194）是纯乘法缩放（`effective_rev_ratio = effective_conv_ratio`，注释「AOV 不变」），**文件中并无 45.0 常量**，且乘法缩放对任意固定价格天然保持 `revenue = conversions × price` 一致，预算分支**无需改动**。真正要做的是：① price elif 分支重算 revenue 时基于**当前** conversions × 新价（而非 baseline 的隐含 45 元）；② 一个「价格补丁与预算补丁两种先后顺序叠加，最终 revenue 一致」的联动回归测试。
- 其余补丁（alloc→counterfactual、creative→full_rerun）已天然覆盖上市滑杆。
- **lifecycle 端点不通用（完整性复核发现）**：`/api/sandbox/*` 的 PATCH/counterfactual/undo 与 `/ws/sandbox/{sid}` 对 launch session 原样可用，但 **lifecycle 路径例外**——`api_routers/sandbox.py` 的 lifecycle 端点经 `api_state.py` 调用 legacy `HAWKES` 单例（14 天 campaign 级联，无事件别名、无 Bass 饱和），launch session 调它会静默返回与 LaunchReport 90 天 Bass 曲线语义不一致的结果。M7 处理：sandbox session 增加 `mode` 标记，launch session 的 lifecycle 请求路由到 `bass_saturated_hawkes` + `DiffusionConfig(horizon_days=90)`；路由完成前对 launch session 返回 409 + 指引，**禁止静默回退到 legacy 路径**。
- **守护栏备忘（写进代码注释与本方案）**：未来任何跨期可变状态（如复购/流失）若要加入，必须像 `ScenarioResult.abducted_u` 一样在 session 内按期存快照；直接改共享 `POP` 单例会破坏反事实确定性，使反事实悄悄对比两个不同世界。

---

## 5. 数据层：现有 21k 语料 / 达人 / 消费者 panel 的复用

定位：**现有语料是产品「上市进入的市场环境」，不重新生成。**（`data/synthetic/` 共 ~21.8k 行：notes_v3.json 8.5k、synthetic_notes.json 8.5k、synthetic_kols.json 2.2k、scenarios_v0_1.jsonl 2k、event_streams 等）

1. **`data/niches.json` → v2**（经 `backend/oransim/config/niches.py` 加载，`ORAN_NICHES_PATH` 可覆盖，对老字段向后兼容）：
   - 每 niche 新增字段：`reference_price`（价格特征归一锚）、`purchase_cycle_days`、`adoption_rate_prior`（Bass m 折算）、`bass_p_prior`、`bass_q_prior`、`aov_prior`。
   - 新增 ~5 个产品品类条目（如 app_tool、smart_hardware、edu_service…），补关键词 synonyms。
   - `config/niches.py` 按既有 `ctr_priors()` getter 模式新增 `reference_prices()`、`adoption_priors()`、`bass_priors()` 三个 getter。
2. **合成笔记语料**（`data/synthetic/synthetic_notes.json` / `notes_v3.json`，由 `backend/scripts/gen_synthetic_data.py` 生成、经 `platforms/*/providers/synthetic.py` 加载——注：xhs 尚无 `providers/synthetic.py`（Phase 1 skeleton），不影响本节：UEB 索引直接读语料文件，不依赖 provider 加载路径）→ **替代品/注意力基线**：在 `api_state.py _bootstrap_index()`（line 117）把按 niche 的 `CanonicalNote.text` 索引为新 UEB 源 `category_notes`；`spec/ground.py` 对其做嵌入检索，(a) 验证 grounded 品类在语料中确有覆盖（不覆盖 → 拉低 grounding_confidence → 触发硬拒绝），(b) 估算品类基线注意力，标定 `substitute_pressure`。
3. **100k 消费者 panel**（`backend/oransim/data/population.py`，IPF 校准人口 + 兴趣嵌入 + 大五人格）→ **零改动**复用为可触达市场。目标用户 grounding 只产出 `AudienceFilter` + `fan_profile.fan_weight_vector()` 软复权——与今天 KOL 垂类定向完全同一机制；加权质量同时充当 Bass 市场潜量 m 的估计。
4. **KOL 库**（`backend/oransim/data/kols.py` + `data/synthetic/synthetic_kols.json`）→ 上市合作方候选池，`pick_kol_by_spec()` 原样用。
5. **Schema 版本**：`backend/oransim/data/schema/canonical.py` 并排新增 `CanonicalProductSpec` 与 `CanonicalLaunchScenario`（CanonicalScenario + spec 引用），`SCHEMA_VERSION` 升 "2.0"；既有 v1.1 模型保留不动。
6. **可选（M8）**：扩展 `backend/scripts/gen_synthetic_data.py` 产出品类级 launch-outcome JSONL（golden set），用于标定价格敏感系数与 parametric Hawkes / Bass 长尾先验。明确标注：这是合成数据自标定，不等于真实校准（§9 风险 3）。

---

## 6. API 层：新增 endpoint（现有前端零破坏）

新路由文件 `backend/oransim/api_routers/launch.py`，在 `backend/oransim/api.py` 现有 8 路由注册块旁注册；请求/响应模型加进 `backend/oransim/api_schemas.py`。**`PredictRequest` 不改动**（除一个带默认值的可选字段都不加），campaign API 面完全不动，现有前端零感知。

| Endpoint | 请求 | 响应 | 说明 |
|---|---|---|---|
| `POST /api/launch/ingest` | `IdeaIngestRequest {idea_text: str(1..5000), locale?, budget_hint_cny?, launch_date?}` | `{spec_id, spec: ProductSpec, assumed_fields: [...], grounding: {niche_key, grounding_confidence, matched_synonyms, corpus_coverage}, clarification_questions: [...]}` | 只做抽取+grounding，**不烧仿真**——廉价预览闸。LLM 调用走 `api_routers/predict.py` 同款 StreamingResponse 10s keepalive 模式。置信度不足时 `clarification_questions` 非空且无 spec_id 可模拟 |
| `PATCH /api/launch/spec/{spec_id}` | 字段级修正 | 更新后的 spec + 重算的 grounding | 人在回路确认闸（忠实度闸门）。修正过的字段 provenance 改记 `user_confirmed` |
| `POST /api/launch/simulate` | `{spec_id \| spec, overrides?: {budget, platform_alloc, n_souls, horizon_days, use_llm}}` | `LaunchReport`（§7），流式 | 内部经 `spec/pipeline.py` 编译 → `ScenarioRunner.run()` → `souls.infer_batch(mode="launch")` → diffusion 预测。**编排复用策略**：不对 `api_routers/predict.py _predict_sync()` 做大爆炸式抽取；launch 路径先自建薄编排（只用到的 4–5 个 extras），仅把确实共享的小块（macro 组装、schema_outputs 调用）渐进下沉到 `api_helpers.py`，`_predict_sync` 本体不动 |
| `POST /api/launch/sandbox` | `{spec_id}` | `{sid}` | 用编译出的 Scenario 建 `SandboxSession`（带 `mode="launch"` 标记）；既有 `/api/sandbox/*` 的 PATCH/counterfactual/undo 与 `/ws/sandbox/{sid}` WebSocket 原样可用，价格/预算/渠道滑杆 day one 工作。**例外：lifecycle 端点须按 §4.7 路由到 90 天 Bass 路径，路由完成前对 launch session 返回 409** |
| `GET /api/launch/whatif/{spec_id}` | — | 命名反事实包 | 跑 `causal/launch_interventions.py` 全弹药库（§4.6），经 `ScenarioRunner.counterfactual()` + `equilibrium_under_do()` |

每个响应（包括 simulate 与 whatif）都在顶层携带 `assumed_fields` 与 `grounding_confidence`——诚实标记不允许只出现在 ingest。

**Spec 存储（v1.2 补缺口，M7 前必须决策）**：`PATCH /spec/{spec_id}` 与 §4.1 的 `(spec_id, 修正版本号)` AudienceFilter intern 都依赖一个**带版本号的 spec 存储**，本方案此前未交代。决策：M7 用进程内 dict + `data/world_events.py` 同款文件缓存落盘（`{spec_id: [ProductSpec v0, v1, ...]}`，append-only，PATCH 即追加新版本），与现有 `SandboxStore`（同为进程内单例）的部署假设保持一致——**单 worker 部署**。多 worker / 持久化升级（Redis 等）显式记为不做项，与 sandbox session 的同一限制一并解决，不在本方案内单独引入新基础设施。spec 文件缓存的 TTL 与清理策略随 M7 实装定。

---

## 7. 输出设计：LaunchReport（「上市之后会发生什么」）

由新文件 `backend/oransim/agents/launch_outputs.py`（与 `agents/schema_outputs.py` 并排）组装，四个区块全部派生自现有机器：

**头部 — 假设回显**：ProductSpec 全字段 + 三色来源标注（用户原话 / LLM 推断 / 系统默认）+ `grounding_confidence`。报告开头第一句即「这是带标注不确定性的情景推演，不是预测」。

**区块 1 — 指标**：KPI 重映射为上市词表——unique reach、trials、adopters、adoption_rate、revenue（price × adopters）、相对 budget_hint 的 payback；每项带 P35/P50/P65 分位带，P35 行显式标注为「下行情形」。**分位带来源（完整性复核后明确）**：launch 路径的分位带来自 **`ScenarioRunner` 多 seed Monte Carlo 重跑的经验分位数**（M7 默认 5–9 个 seed，沿用 `Scenario.seed` 字段；成本倍率与降级旋钮见 §9 风险 8——LLM souls 只跑 P50 主 seed，其余 seed 走纯统计路径），**不是**已训练的 world model checkpoint（lightgbm_quantile / causal_transformer 训练于 campaign 场景 `scenarios_v0_1.jsonl`，对 launch 场景属 OOD）。`world_model/base.py DEFAULT_QUANTILES` 仅复用其分位点定义（0.35/0.5/0.65）。可选增强：并列展示 WM checkpoint 输出并标注「campaign 域模型外推，仅供参照」。

**区块 2 — 时间线**：90 天逐日采纳与收入曲线，来自 `DiffusionForecast.daily_buckets`（神经 Hawkes 0–14 天 + Bass 饱和 parametric 长尾，10–18 天混合窗拼接）；用既有 `agents/schema_outputs.fit_diffusion_curve()` 提取 peak_day 与 half_life，**新增 saturation_date（N(t) 达 0.9m 的日期）**——这是 Bass 饱和带来的、campaign 报告给不出的新答案；organic vs paid 拆分来自 treatment 标记事件。

**区块 3 — 谁会买**：`causal/cate.py compute_cate()` **零改动复用**于 baseline vs organic_only 的概率差，输出年龄×性别×城市线×收入分段排名（「你的前 1000 个用户长这样」）+ `fan_profile_summary()` 式有效人群画像；soul persona 引语（`will_try / would_pay_cny / objection`）作为早期采纳者/怀疑者的定性声音，**objection 原话直接列为风险信号**，would_pay_cny 分布与定价对照。

**区块 4 — 什么会出问题**：每条 `launch_interventions` 干预一张叙事卡（名称 + 相对基线的 KPI delta + 模板化叙事，如「定价 +30% 时采纳者下降 41%，payback 永不过 1.0」）；外加 `make_creative()` 的 audit_risk 合规旗标、`data/macro.py` 假日/季节因子给出的最佳/最差上市窗口。竞品类卡片固定前缀「如果竞品跟进——这是分支不是预测」。

---

## 8. 实施里程碑（每阶段可独立验证）

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **M0 — 回归地基**（半天，前置于一切） | ① `Scenario.hash_tuple()` 反射回归测试（每个 dataclass field 必须在 hash 中**或在冻结白名单中**；白名单初始 = `macro_ctr_lift`/`macro_cvr_lift`/`cross_platform_overlap`/`llm_calibration` 四个既有遗漏，只许减不许增，见 §4.1）；② `/api/predict` 黄金快照测试（后续每个 M 跑一次，保证字节级不变）；③ `sandbox/engine.py scale_kpi`（line 194）加注释固化乘法缩放不变量（revenue 随 conversions 等比缩放、无 AOV 常量，对任意固定价格保持一致——见 §4.7）。测试放仓库根 `tests/`（与 `test_smoke.py` 并排） | 测试入库即绿（白名单机制保证） |
| **M1 — Spec schema + 骨架** | `backend/oransim/spec/{schema.py, extract.py, normalize.py, pipeline.py}`；mock 抽取（niche synonyms 关键词 + 品类默认表）；黄金集 `tests/golden/launch_ideas.jsonl`（~30 条） | `LLM_MODE=mock` 下 CI 绿；黄金集 spec 字段匹配率有基线数字 |
| **M2 — Grounding** | `spec/ground.py`（niches + population 桶 + macro `_CATEGORY_KW`）；`api_state._bootstrap_index()` 注册 `product_categories` 与 `category_notes` 两个 UEB 源；grounding_confidence + 硬拒绝 + clarification_questions | 黄金集品类映射准确率 **≥ 85%**（30 条中 ≥ 26 条 niche key 正确；mock 与 LLM 两模式分别统计）；3 条 B2B/SaaS 反例必须被硬拒绝 |
| **M3 — Scenario 生成** | `spec/scenario_gen.py`：合成 creative 走 `make_creative()`、alloc/KOL/预算默认、Hawkes 种子事件；AudienceFilter 按 `(spec_id, 修正版本号)` intern（§4.1） | 单测：产出的 Scenario 不加修改通过 `ScenarioRunner.run()` 全程；同一 spec 版本重编译两次 hash_tuple 相等 |
| **M4 — 价格端到端**（提前于 API，渐进纪律） | `Scenario.price_cny` + hash；`statistical.py` AOV 参数化 + `log(price/reference_price)` 特征；`sandbox/engine.py` price elif（按当前 conversions × 新价重算 revenue，§4.7）；niches.json v2 的 `reference_price` 最小集 | M0 快照测试证明 `/api/predict` 不变；price±30% 在 sandbox 中产生单调合理的 KPI 变化；**价格×预算双滑杆两种叠加顺序最终 revenue 一致**（联动回归测试） |
| **M5 — 人格 + 传播** | `soul_llm.py LAUNCH_PROMPT_TEMPLATE` + `soul.py mode="launch"`；事件别名（hawkes.py/_etype_idx）；`DiffusionConfig(horizon_days=90)`；**`diffusion/bass_saturated_hawkes.py`** + registry 注册 + 混合窗拼接；voronoi_calibration 改接 will_try | mock 人格路径绿；90 天曲线出现峰值且趋平（对照闭式 Bass 曲线验证饱和行为） |
| **M6 — SCM + 干预弹药库** | `scm.py` 新增 `price_point`/`launch_channel_mix` 节点 + `substitute_pressure→competitor_action` 接线；`causal/launch_interventions.py` 全弹药库 | `equilibrium_under_do` 在新图上收敛（fixed_point.py 谱半径检查）；7 条命名干预各产出 delta |
| **M7 — API + 报告** | `api_routers/launch.py` 五个端点 + `api_schemas.py` 模型 + `api.py` 注册；`agents/launch_outputs.py` LaunchReport 组装（分位带 = 多 seed Monte Carlo，§7）；sandbox `mode="launch"` 标记 + lifecycle 路由/409（§4.7） | 端到端：一句话 idea → ingest → PATCH → simulate → LaunchReport JSON 完整（含三档分位带，可由固定 seed 集复现）；现有 8 路由契约不变；`/api/launch/sandbox` 建的 session 可被既有 `/ws/sandbox/{sid}` 驱动；launch session 调 lifecycle 不再落入 legacy HAWKES 路径 |
| **M8 — 数据 v2 + 标定** | niches.json v2 全字段（bass_p/q_prior、purchase_cycle_days、adoption_rate_prior、aov_prior）+ 新品类条目 + `config/niches.py` getters；可选 `gen_synthetic_data.py` launch-outcome 黄金集标定价格敏感系数与 Bass 长尾 | 标定前后报告分位带变化有记录；未标定项在报告中有显式标注 |

依赖关系：M0→(M1‖M4)→M2→M3→M5→M6→M7→M8。M4 与 M1–M3 可并行（不同人）。

---

## 9. 风险与开放问题

1. **抽取忠实度**：口喷文本诱发幻觉字段。缓解：provenance span、inferred 标记、PATCH 确认闸、低置信 clarification——但跳过审核直奔 simulate 的用户仍可能模拟一个他没描述的产品。开放问题：是否对 `assumed_fields` 超过 N 项的 spec 强制 PATCH 确认后才允许 simulate。
2. **分类体系覆盖**：niches.json 是 10 个 CN 社交消费垂类；B2B/SaaS/硬件没有诚实的 grounding。对策已定为**硬拒绝**而非软警告（M2 验收项）。开放问题：v2 新增 5 品类后阈值是否需要按品类分别设。
3. **合成先验冒充预测**：KOL 库、CPM 表、IPF panel 均为 demo 级，收入轨迹会显得权威。缓解：报告头部诚实声明 + 全字段来源标注；M8 的「标定」是合成数据自标定，必须在报告中如实标注。声誉风险无法完全消除。
4. **传播 OOD**：神经 Hawkes 训练于 14 天 engagement 流；90 天长尾靠 Bass 饱和 parametric 模型，其 mu/alpha/beta 与 bass_p/q 先验未经采纳数据拟合。已用混合窗消除接缝拐点，但长尾形状是先验驱动的情景推演。
5. **决策权重迁移**：`W_CLICK/W_CONVERT` 编码的是广告点击行为而非任意新产品的购买；价格敏感项在 M8 之前没有真实标定数据。voronoi_calibration 接 will_try 票同样未经验证。
6. **缓存/哈希陈腐**：sandbox 与 CCG 记忆化键于 Scenario hash；M0 的「hash 或白名单」反射测试是强制不变量，**新增任何 Scenario 字段时该测试必须先红后绿**。既有 4 字段遗漏与 `id(audience_filter)` 语义按 §4.1 处理（白名单冻结 + launch 路径 intern），不在本方案内修复 hash 本身。
7. **CN 市场硬编码**：CNY、抖音/小红书先验、618/双11 假日、中文合规关键词烤死在 `data/platforms.py` 与 `data/macro.py`；非 CN 产品会得到误导性季节与渠道组合。短期对策：`locale != zh-CN` 时在 assumed_fields 标注「市场环境按中国社媒市场模拟」。
8. **LLM 成本/延迟 + Monte Carlo 倍率（v1.2 补缺口）**：ingest 抽取 + 发布文案合成 + 可选 soul LLM 模式叠加调用量。keepalive 流处理延迟；成本守卫复用 `soul_llm.py COST_TABLE_CNY` 账本并扩展到 spec pipeline，单请求设上限。**另：§7 分位带 = 5–9 个 seed 全量重跑 `ScenarioRunner`，一次 `/api/launch/simulate` 即 5–9 倍仿真成本；soul LLM 模式下该倍率乘在 LLM 调用上不可接受**——对策：LLM souls 只跑 P50 主 seed 一次（人格引语与校准不随 seed 重采），其余 seed 走纯统计路径出分位带；`overrides` 暴露 `n_seeds`（默认 5，允许降为 1 = 单点无分位带，报告中标注）。延迟超预算时这是第一个降级旋钮。
9. **保真度天花板（已知接受的不做项）**：本方案不含复购/流失/留存机制，也不含动态竞品策略——竞品仅以「标注分支」呈现。若未来引入跨期状态，**必须**按 §4.7 守护栏：状态快照随 session 存（如 `abducted_u`），禁止改写共享 `POP` 单例，否则 Pearl 反事实确定性静默破坏。
10. **`_predict_sync` 重构风险（评审点名）**：已通过「launch 路径自建薄编排 + 渐进下沉」策略规避大爆炸重构；开放问题：长期是否合并两条编排路径，待 launch 路径稳定后再议。
