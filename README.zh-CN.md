<div align="center">
<img src="assets/wordmark.svg" alt="Augur" width="640"/>

### 上线前，先看清这次发布会落成什么样。

<p>
  <a href="https://github.com/horton2048/augur/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/horton2048/augur?color=blue"></a>
  <a href="https://github.com/horton2048/augur/releases"><img alt="Release" src="https://img.shields.io/github/v/tag/horton2048/augur?label=release&color=blue"></a>
  <a href="#"><img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue"></a>
  <a href="https://github.com/horton2048/augur/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/horton2048/augur/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/horton2048/augur/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/horton2048/augur?style=social"></a>
</p>

<p>
  <a href="README.md">🇬🇧 English</a> · <strong>🇨🇳 中文</strong>
</p>

<p><em>给独立创造者的上市预测引擎。<br/>在一个虚拟消费者社会里预演你的产品或内容发布 —— 花一分钱之前，先拿到 ROI、14 天扩散曲线，和一个干脆的「放行 / 调优 / 暂缓」结论。</em></p>
</div>

---

<p align="center">
<img src="assets/screenshots/hero.png" alt="Augur · 60 秒完成带反事实回放的上市预演" width="100%"/>
</p>

**面向独立创造者、个人品牌主理人、小型创作团队。** 在你为一次上市砸下钱和时间之前，**Augur 先帮你跑一遍**。把你的素材 + 预算 + 平台 + KOL 短名单丢进去，它就在一个 **100 万+ 虚拟消费者社会**上预演整个发布过程，里面的 LLM 人格会真的去*读*你的素材。你拿到的是上市前的 **ROI 预测（带置信区间）**、**14 天扩散曲线**，和一句大白话结论 **放行 / 调优 / 暂缓** —— 外加一段电影式的**战况回放**，看这次发布怎么一圈圈扩散出去。它是一套透明的因果引擎、完全开源，所以每一个数字你都能追溯到产生它的那个决策，而不是去信一个黑盒。

*这个仓库就是引擎本身 —— 同一套因果栈，跑在内置的演示语料上。git clone、跑一次发布、端到端审一遍机制。拿到第一个预测不需要注册、不需要 key。*

---

## 它是干什么的

每一次上市，归根结底都是这三个问题 —— 而你平时只有在钱已经花出去*之后*才有机会回答：

### 1. 上线前
> *"我有 4 个创意剪辑 × 3 套 KOL 短名单 × 2 个预算档 —— 哪个组合真能落地？"*

平时的做法：凭感觉挑、砸钱、两周后才知道。**Augur**：60 秒、¥0 成本的仿真，把 24 种组合按 P35/P65 置信区间排序，让你拿最好的 3 个去发，而不是赌。

### 2. 发布途中
> *"第 3 天没达标。如果换掉两个 KOL、把预算挪给另外三个 —— 到底有没有用？"*

平时的做法：盯着 dashboard 干着急。**Augur**：`do(kol=swap_A_for_B, day=3)` 把接下来 14 天*带着这个改动*向前推演，30 秒给你看路径差。

### 3. 复盘
> *"这次翻车了。当时预算如果给到另一个平台，会不会更好？"*

平时的做法：含糊的复盘，没有真答案。**Augur**：load 实际数据 + `do(platform=...)`，在同一批受众上跑出反事实曲线 —— 笃定地知道"当时换了会怎样"。

同一个引擎，三个决策。下面讲它怎么搭的、凭什么信这些数字。

---

## 凭什么信这些数字

大多数"预测你的上市"工具只丢给你一个数字、没有任何推导 —— 一个让你凭信仰接受的黑盒。Augur 的搭法正相反：每个预测都能拆开，整个引擎就在这个仓库里。

### 🔬 自己审引擎

这是**完整的因果引擎**，不是营销 demo。git clone、在自己场景上跑、把任意一个预测追溯到 64 节点因果图里*哪个* agent 决策、*哪段*预算曲线算出来的。不是"信我们这是 ML"—— 你能跟着推理走一遍。

```bash
git clone https://github.com/horton2048/augur.git && cd augur
pip install -e '.[dev]' && python -m uvicorn oransim.api:app --port 8001 &
curl http://localhost:8001/api/graph/inspect   # 因果图的 JSON 表示
```

### 📊 它自带了跑起来需要的一切

仓库里带了一份小规模参考语料（2.1 万 notes / 2k 场景 / 100 事件流）和一个预训练 baseline 模型 —— 足够跑通每一条代码路径、拿到真实预测、开箱即用。准备好了，再通过 `DataProvider` 接口把它指向你*自己的*数据（CSV / JSONL / 一个 REST 接口 / 你的数据库）—— 见 [📦 数据 · 自接](#-数据--自接)。

### 📚 12 年研究撑底，不是拍脑袋

每一层都追溯到同行评议的工作，而不是一句 prompt：

<details>
<summary>架构 + 研究谱系（点开展开）</summary>

- **Per-arm 反事实头** —— TARNet (Shalit ICML 2017) · Dragonnet (Shi NeurIPS 2019)
- **表征平衡损失** —— HSIC (Gretton 2005) · adversarial-IPTW · BCAUSS · CaT (Melnychuk ICML 2022)
- **In-context 摊销** —— CInA (Arik & Pfister NeurIPS 2023)
- **因果神经 Hawkes 过程** —— Mei & Eisner NeurIPS 2017 + Zuo ICML 2020 + Geng NeurIPS 2022 counterfactual TPP
- **预算曲线** —— Hill 饱和 (Dubé & Manchanda 2005) + 频次疲劳 (Naik & Raman 2003)
- **SCM** —— Pearl 3 步（溯因 → 干预 → 预测），64 节点 / 117 边，含话语 + 级联 mediator (Sunstein 2017 · Bikhchandani 1992)
- **Agent 人口** —— IPF / Deming-Stephan 1940 baseline

详见 `backend/oransim/{world_model,diffusion,causal}/` —— 每个文件内嵌 citations。
</details>

---

## 🚀 一分钟上手

```bash
# 1. 克隆 + 安装
git clone https://github.com/horton2048/augur.git
cd augur
pip install -e '.[dev]'

# 2. 启动后端（mock 模式 —— 不需要 API key）
LLM_MODE=mock python -m uvicorn oransim.api:app --port 8001 &

# 3. 启动前端
python -m http.server 8090 --directory frontend

# 4. 浏览器打开 http://localhost:8090 → 点 "⚡ 极速" → "🚀 预测"
```

> 📦 **Python 包仍然按 `oransim` 导入** —— 只有产品改名叫 Augur。clone URL、`import oransim`、`oransim.api:app` 都没变，已有代码和工具照常工作。

> 📌 **你现在跑的是什么数据** —— 上手流程消费的是仓内 `data/synthetic/`（2k 场景 / 500 notes / 100 事件流）+ `data/models/world_model_demo.pkl`（合成语料上训练的 LightGBM）。这是 **按公开报告均值校准的演示数据集** —— 可复现、能跑通全链路，但**不是真实流量**。想把自己的数据（CSV / JSONL / OpenAPI / 自建 DB）接进来，跳到 [📦 数据 · 自接](#-数据--自接)。

Mock 模式走模板、没 LLM 调用 —— 能跑通但 soul persona / 群聊 / 评论区辩论 / LLM 校准全部退化。**切真 LLM：**

```bash
LLM_MODE=api \
LLM_API_KEY=sk-xxxxx \
LLM_MODEL=gpt-5.4 \
python -m uvicorn oransim.api:app --port 8001 &
```

`LLM_PROVIDER` 选原生格式，默认 `openai`（也覆盖 DeepSeek / vLLM / 任何 OpenAI-compat 网关）：

<details>
<summary>各 provider 推荐配置（点开展开）</summary>

| `LLM_PROVIDER` | `LLM_BASE_URL` | `LLM_MODEL` 示例 | 关键 env |
|---|---|---|---|
| `openai`（默认） | `https://api.openai.com/v1` | `gpt-5.4` · `gpt-4o-mini` | `OPENAI_API_KEY` 或 `LLM_API_KEY` |
| `openai`（DeepSeek） | `https://api.deepseek.com/v1` | `deepseek-chat` | `LLM_API_KEY` |
| `openai`（本地 vLLM） | `http://localhost:8000/v1` | 任意已挂载的模型 | `LLM_API_KEY=local` |
| `anthropic` | 默认官方 | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` 或 `LLM_API_KEY` |
| `gemini` | 默认官方 | `gemini-2.5-pro` · `gemini-2.5-flash` | `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `LLM_API_KEY` |
| `qwen` | `https://dashscope.aliyuncs.com/api/v1`（默认） | `qwen-plus` · `qwen-turbo` | `DASHSCOPE_API_KEY` / `QWEN_API_KEY` / `LLM_API_KEY` |

完整参考：[`.env.example`](.env.example)；重试 / 降级 fallback 细节见 [`docs/zh/quickstart.md`](docs/zh/quickstart.md)。

</details>

前端检测到后端还是 mock / 没 key 时，顶部会弹一条黄色 banner 贴启动命令 · 点 ✕ 本会话不再显示。

> **现在能跑到什么程度 · 真实 vs aspirational**
> - ✅ **今天就能跑** —— 完整后端（`POST /api/predict` · `/api/adapters` · `/api/sandbox/*`，拆成 `api_routers/` 多个子 router）· 完整前端（hero · 9 tab · 级联动画 · 战况回放）· 预训 LightGBM quantile baseline pkl · 5 个 platform adapter（XHS v1 + TikTok agent-level 带 FYP 冷启 RL + IG / YouTube Shorts / Douyin MVP）· learned amortized abduction（纯 numpy MLP）· 多 LLM provider（OpenAI-compat · Anthropic · Gemini · Qwen）
> - 🟡 **代码已 ship，权重待发** —— 因果 Transformer 世界模型 + 因果神经 Hawkes 扩散模型 —— 架构 + 训练 loop + 推理 + thinning 采样全部 ship；预训权重随 OrancBench v0.5 发布
> - 📋 **仅路线图** —— Twitter / Bilibili / LinkedIn adapter · 多模态 embedder（当前只 image/video/audio stub）· hosted demo

---

## 🎬 实际效果

<table>
<tr>
<td width="50%" valign="top">

**三栏工作界面** —— 左：素材 + 预算 + 反事实滑块 · 中：KPI / Agent 人口池 / AI 群聊 tab（「更多 ›」下拉藏着 Hawkes / SCM / CATE / Schema 等深度视图）· 右：逐 persona 的 LLM 反应。

<img src="assets/screenshots/main-three-col.png" alt="三栏预测界面" width="100%"/>

</td>
<td width="50%" valign="top">

**agent 网络中的意见传播** —— 粘入你的素材，观察四色意见波（绿=点击 / 紫=强购意 / 红=跳过 / 蓝=好奇）从 KOL 种子向外扩散，级联感染粉丝。

<img src="assets/screenshots/society-100m.png" alt="agent 网络中的意见传播" width="100%"/>

</td>
</tr>
</table>

---

## 📦 数据 · 自接

Augur 把**引擎**（世界模型、SCM、Hawkes、soul、平台）和**数据**（在里面流的内容）解耦。仓库自带一份小规模合成数据让全链路开箱即用；每一条数据路径都可以被你自己的真实数据源替换。

### 仓里默认带了什么

| 文件 | 是什么 | 用在哪 |
|---|---|---|
| `data/synthetic/notes_v3.json` | 500 条合成 notes · 10 个 niche | caption / tag / 粉丝 / 互动率先验 |
| `data/synthetic/scenarios_v0_1.jsonl` | 2k 合成场景 · 虚构投放 | 世界模型训练 + held-out 评估 |
| `data/synthetic/event_streams_v0_1.jsonl` | 100 条合成 Hawkes 事件流 | 扩散预测器拟合 |
| `data/synthetic/niche_priors_calibrated.json` | 按 niche 的 CTR / CVR 先验均值 | 世界模型无信号时的兜底先验 |
| `data/models/world_model_demo.pkl` | LightGBM quantile baseline（约 3 MB） | 预训权重 —— `backend/scripts/gen_synthetic_data.py` 可重训 |
| `data/niches.json` | **Niche 注册表**（10 个条目） | niche key / 中文名 / CTR 先验 / 同义词的单一数据源 |

> ⚠️ **这是演示数据，不是真相。** 合成数据生成器按公开行业报告的均值校准，但**不反映**任何特定平台的真实流量、也不反映你的具体受众。要拿 Augur 做真实的上市决策，请通过 `DataProvider` 接你自己的数据（见下）。

### 把你自己的数据接进来 · 三种路径

Augur 的 `DataProvider` 接口位于 `oransim/platforms/providers/`。按你数据所在的地方选：

| Provider | 适用场景 | 契约 | 参考 |
|---|---|---|---|
| `CSVProvider` | BI / 表格批量导出 | 每张表一个 CSV（`notes.csv` / `kols.csv`） | [`docs/zh/platforms/writing-a-provider.md`](docs/zh/platforms/writing-a-provider.md)（若无则看英文版） |
| `JSONLProvider` | 流式事件（Kafka 落地成文件） | 每行一个 JSON object | 同上 |
| `OpenAPIProvider` | 实时 REST / GraphQL | 实现 4 个读接口 | 同上 |
| *自己实现* | PostgreSQL / ClickHouse / Snowflake / BigQuery | 继承 `DataProvider` 接口 | 同上 |

**你的数据源至少要暴露这些字段**：

```yaml
notes:
  - note_id, caption, niche, platform, publish_time,
    author_fans_count, read_count, like_count, collection_count, comment_count
kols:
  - anchor_id, nick, niche, platform, fan_count,
    interaction_rate, ad_price_cny
```

字段名可以通过 `provider.field_map` 重命名；完整 schema 在 [`writing-a-provider.md`](docs/en/platforms/writing-a-provider.md) 里。

### 新增一个 niche

如果你的数据覆盖了 10 个默认 niche 之外的赛道（比如汽车、医疗、潮玩），**只需要编辑 `data/niches.json`**，每个 niche 加一个条目：

```json
{
  "key": "auto",
  "zh": "汽车",
  "en": "Automotive",
  "synonyms": ["新能源车", "试驾", "特斯拉", "SUV"],
  "ctr_prior": {"mu": 0.024, "sigma": 0.010, "n": 860},
  "bias_caption": "汽车 试驾 新能源车 改装",
  "female_ratio": 30
}
```

就这一处修改。注册表在 import 时由 `oransim.config.niches` 加载，所有 niche 相关组件（KOL 库、caption→category 检测、CTR 先验、结构化 schema 输出、soul prompt 渲染）都从注册表读 —— 没有散落在各处的硬编码表要去改。不想改仓内文件，用 `ORAN_NICHES_PATH=/srv/my_niches.json` 指向你自己的 JSON 即可。

### 怎么看现在跑的是 demo 还是真数据

前端会持续显示提示条，出现以下任一条件时闪黄：
- `LLM_MODE=mock`（没设 LLM key）—— LLM 回退到模板
- 没注册自定义 `DataProvider` —— 读 `data/synthetic/`

两边都解除后提示条消失。`GET /api/health` 的 `data_source` 字段也给 observability 用。

---

## 🏗️ 架构

<div align="center">
<img src="assets/architecture.svg" alt="Augur 架构图" width="100%"/>
</div>

一次典型预测链路：**素材 + 预算** → **PlatformAdapter**（经可插拔 **DataProvider** 取数据）→ **世界模型**（事实 + 反事实预测）+ **Agent 层**（POP_SIZE-scalable IPF + LLM 人格）→ **因果引擎**（64 节点因果图 + `do()` 反事实）→ **扩散**（14 天干预感知 rollout）→ **预测 JSON**（14-19 个 schema）。

**默认走哪条 / 研究栈怎么开：**

| 位置 | 开箱默认 | 研究栈（opt-in） |
|---|---|---|
| 世界模型 | LightGBM 量化 baseline（`data/models/world_model_demo.pkl`）+ 手写结构化公式 | `CausalTransformerWorldModel`（CaT / TARNet / Dragonnet / CInA）— 本地训或 `POST /api/v2/world_model/predict?model=causal_transformer` 切换 |
| 扩散 | 参数化指数核 Hawkes (Hawkes 1971) | `CausalNeuralHawkesProcess`（Mei & Eisner + Zuo et al. + Geng et al.）— 同样 opt-in：`POST /api/v2/diffusion/forecast?model=causal_neural_hawkes` |
| Agent | `StatisticalAgents`（向量化，CPU） | `SoulAgentPool` LLM 人格（`/api/predict` 勾 `use_llm=true`） |
| 沙盘 | 只改预算时用 Hill 饱和 + 频次疲劳闭式公式快算（response 里 `mode: "fast_approx"` 标出来），滑块响应快；改创意 / alloc / KOL 触发真实重跑（`mode: "counterfactual"` 或 `"full_rerun"`）。 | — |

*registry 是扩展点。默认 `/api/predict` 走 baseline 栈是因为它今天就带权重能跑；`/api/v2/*` 是训好权重后 A/B 切到研究栈的路径。两条路径共用同一套 SCM / agent / Hawkes 管道。*

两轴可扩展：
- **平台轴** —— XHS（v1 legacy 直接可跑）+ TikTok / Instagram / YouTube Shorts / Douyin（合成数据 MVP）；Twitter / Bilibili / LinkedIn 在路线图
- **数据轴** —— 每平台多数据源插件（Synthetic / CSV / JSON / OpenAPI / 自定义）

完整设计见 [`docs/zh/architecture.md`](docs/zh/architecture.md)。

---

## 🌐 平台 Adapter 矩阵

| 平台                 | 区域      | 状态    | 数据源                                | 世界模型              | 里程碑 |
|----------------------|-----------|---------|---------------------------------------|-----------------------|--------|
| 🔴 小红书 / XHS      | 大中华区  | ✅ v1   | Synthetic / CSV / JSON / OpenAPI    | 因果 Transformer + LightGBM baseline | — |
| ⚫ TikTok            | 全球      | 🟢 MVP  | Synthetic                            | LightGBM baseline     | v0.5（接真 panel） |
| 🟣 Instagram Reels   | 全球      | 🟢 MVP  | Synthetic                            | LightGBM baseline     | v0.5（接真 panel） |
| 🔴 YouTube Shorts    | 全球      | 🟢 MVP  | Synthetic                            | LightGBM baseline     | v0.5（接真 panel） |
| 🔵 抖音 / Douyin     | 大中华区  | 🟢 MVP  | Synthetic                            | LightGBM baseline     | v0.5（接真 panel） |
| ⚪ Twitter / X       | 全球      | 📋 规划 | —                                    | —                     | v0.5 |
| 📺 Bilibili          | 大中华区  | 📋 规划 | —                                    | —                     | v1.0 |
| ✒️ LinkedIn          | 全球      | 📋 规划 | —                                    | —                     | v1.0 |

**想要其他平台？** 提 [Adapter Request](https://github.com/horton2048/augur/issues/new?template=adapter_request.yml) —— 我们根据社区需求优先级排序。

---

## 📊 输出 Schema（14-19 个）

一次 `/api/predict` 调用返回下列 schema：

1. **total_kpis** —— 总曝光 / 点击 / 转化 / 成本 / 收入 / CTR / CVR / ROI（P35/P50/P65 区间）
2. **per_platform** —— 各平台 KPI 分解
3. **per_kol** —— KOL 层面归因
4. **diffusion_curve** —— 14 天日维度曝光/互动预测（因果神经 Hawkes 主预测器，参数化 Hawkes 作为 baseline）
5. **cate** —— 条件平均处理效应（按 agent 人口学切片）
6. **counterfactual** —— 反事实分支：换素材/加预算/换 KOL 的对比
7. **soul_feedback** —— 10 个 LLM 人格的自然语言反馈
8. **group_chat** —— 群聊动态模拟（Sunstein 2017 群体极化）
9. **discourse** —— 二次传播 mediator 影响估计
10. **final_report** —— LLM 生成的执行摘要
11. **verdict** —— 一句话决策建议（放行 / 调优 / 暂缓）
12. **kol_optimizer** —— 目标下的最优 KOL 组合
13. **kol_content_match** —— 素材 × KOL 匹配打分
14. **tag_lift** —— tag/定向选择的增量贡献
15. **mediator_impact** —— 从 discourse/group_chat 到漏斗的路径分析
16. **brand_memory** —— 纵向品牌偏好更新
17. **sandbox_snapshot** —— 会话快照，支持"撤销/重做"
18. **audit_trace** —— 可解释性 —— 哪些 agent、哪些路径、哪些权重
19. **benchmark** —— OrancBench 比对分数

JSON schema 定义见 [`docs/zh/schemas/`](docs/zh/schemas/)。

---

## 🧠 技术细节

<details id="causal-graph">
<summary><b>因果图</b> —— 64 节点 · 117 边</summary>

图是手工设计的，覆盖上市漏斗从 曝光 → 认知 → 考虑 → 转化 → 复购 → 品牌记忆，包含群体话语（Sunstein 2017）和信息级联（Bikhchandani et al. 1992）的 mediator。

图里含长周期反馈回路（例如 `repeat_purchase → brand_equity → ecpm_bid → 下一轮 impression_dist`）。这是**故意的**—— 反映真实上市物理，不是建模瑕疵。严格 Pearl 式 abduction 在 cycle 上没定义；我们的 `do()` 求值用 Bongers 等 2021 的 cyclic-SCM 推广（[Foundations of Structural Causal Models with Cycles and Latent Variables](https://arxiv.org/abs/1611.06221)），把 25 节点反馈 SCC 当作不动点求解，而不是拓扑前向传播。

代码里的 3 步走法：
1. **溯因** —— agent 层重用 baseline 的采样噪声；图层面每节点残差 frozen
2. **干预** —— 应用 `do()`（可干预节点集见 `/api/dag` 响应里的 `intervenable: true`）
3. **预测** —— 对无环 condensation 拓扑排序，每个 SCC 用数值迭代（shipped 图上实测 2–3 遍收敛）

时间展开的 DAG 投影也已 ship —— `oransim.causal.scm.dag_dict_unrolled(n_steps=K)`：原图每个节点变成 `N_t0, N_t1, ..., N_t{K-1}`，反馈边跨时间（`src_ti → dst_t{i+1}`），非反馈边在每个切片内复制。`n_steps=2` 时 shipped 图的 64 节点 + 117 边（cyclic）展开成 128 节点 + 220 边（严格 DAG · 14 条反馈边通过 DFS 回边分析自动检测）。需要严格无环的下游（真 DAG 上的 CausalDAG-Transformer attention、教科书 Pearl 三步 abduction）可以用这个展开视图。cyclic 原图 + SCC 凝缩仍是默认路径，因为节点数小、和 Transformer 7-token 输入对齐。
</details>

<details>
<summary><b>Agent 人口池</b> —— 可配置规模（`POP_SIZE` env，默认 100k）的 IPF 校准虚拟消费者</summary>

通过迭代比例拟合（IPF / Deming-Stephan 1940）对齐真实中国人口学分布（年龄 × 性别 × 地域 × 收入 × 平台）。每个 agent 带：
- 人口学 + 心理画像
- 平台专属互动先验
- 品类/niche 亲和向量
- 时段活跃曲线
- 社交图 embedding
</details>

<details>
<summary><b>灵魂 Agent</b> —— LLM 人格给定性反馈</summary>

每个场景取最显著的 top-K agent（`SOUL_POOL_N` 可配，默认 100 演示）升级为 LLM 驱动的人格，默认模型 `gpt-5.4`。每个人格：
- 从人口学向量生成 persona card
- 对素材给出反应 / 情绪 / 意图
- 可选加入群聊模拟（Sunstein 2017 群体极化）
- 二次传播信号反哺因果图

**两种模式，权衡讲清楚**：

- **模板模式**（`use_llm=False`，默认）—— 点击决策是统计层 `click_prob` 的 Bernoulli 抽样（垂类匹配时 +40%）；persona 配上与决策一致的模板 `reason` / `comment` / `feel`。零 LLM 成本，给定 seed 可复现，用于 CATE / ROI 数值可复现场景。
- **LLM 决策模式**（`use_llm=True`，Park et al. 2023 Generative Agents 风格）—— 真实 LLM 拿到完整 persona card + 素材 + KOL 上下文，返回结构化 JSON（`will_click` / `reason` / `comment` / `feel` / `purchase_intent_7d`）。**LLM 的 `will_click` 就是 agent 的决策**（不被 Bernoulli 覆盖）；统计层 `click_prob` 作为 prompt 里的先验供 LLM 参考。响应打 `source: "llm"` 标签。权衡：每个 persona 带非确定性；需要严格复现时留模板模式或设 `LLM_TEMPERATURE=0`。

成本控制：请求去重（leader/follower 合并同 key 请求）、persona card 缓存、可配 `SOUL_POOL_N`。
</details>

<details id="causal-transformer-world-model">
<summary><b>因果 Transformer 世界模型</b> —— 主模型（研究级）</summary>

一个 6 层 × 256-dim 的因果 Transformer，吃异构 campaign 特征，输出每个漏斗 KPI 的三个分位数（P35/P50/P65）。架构结合近年因果 Transformer 文献：

- **Token 类型分解**（CaT, Melnychuk et al. ICML 2022）—— 输入分为 *Covariate*（平台、人口学、时段）· *Treatment*（素材 embedding、预算、KOL）· *Outcome*（KPI）三类 token，各自带独立 type embedding
- **DAG-aware 注意力**（CausalDAG-Transformer）—— 注意力 mask 从 64 节点因果图派生，每个 token 只能 attend 到拓扑祖先；每个 head 学一个 bias 门控。图有长周期反馈回路，所以祖先关系定义在 **SCC 凝缩（condensation）** 之上（Bongers 2021 §3.2）。参考实现在 `CausalTransformerWorldModel.set_dag_from_edges()`，`dag_attention_bias=True` 可以切开。
- **Per-arm 反事实头**（TARNet, Shalit et al. ICML 2017 / Dragonnet, Shi et al. NeurIPS 2019）—— 每个离散 treatment arm 一个分位数 head，单次 forward 同时算 `predict_factual` 和 `predict_counterfactual(do(T=t'))`
- **表征平衡正则**（BCAUSS + CaT）—— HSIC（Gretton et al. 2005）或对抗 IPTW loss 把学到的表征和 treatment 分配解耦，降低反事实偏差
- **In-context 摊销**（CInA, Arik & Pfister NeurIPS 2023，可选）—— 模型可以条件于一组历史 campaign 做 amortized zero-shot 因果推断

核心类：`oransim.world_model.CausalTransformerWorldModel`。v0.2.0-alpha 已含完整训练 loop、反事实 rollout、save/load；预训权重随 OrancBench v0.5 发布。

```python
from oransim.world_model import get_world_model, CausalTransformerWMConfig

wm = get_world_model("causal_transformer", config=CausalTransformerWMConfig(
    dag_attention_bias=True,
    balancing_loss="hsic",
    use_counterfactual_head=True,
))
pred = wm.predict(features)                         # 事实预测
cf = wm.counterfactual(features, arm_idx=2)         # do(T = arm 2) 反事实
```

*需要* `pip install 'oransim[ml]'`（装 PyTorch）。torch 不可用时优雅降级到 LightGBM baseline。
</details>

<details>
<summary><b>通用 Embedding Bus (UEB)</b> —— 现在只做文本，v0.5 接多模态</summary>

所有数据源（素材文案、KOL 个签、用户评论、粉丝画像表格、平台事件流）都走统一的 `Embedder` ABC，输出固定维度向量。下游模块（世界模型 / agent / causal 层）从来见不到 modality 特定代码 —— registry 本身就是 modality-generic。

**v0.2 已 ship**：
- `RealTextEmbedder` —— OpenAI 兼容的 `text-embedding-3-small`，复用 soul_llm 的同一个网关。API 不可用时自动降级到确定性 hash embedder。
- `TabularEmbedder` · `CategoricalEmbedder` · `TimeSeriesEmbedder` · `GeoEmbedder` · `EventEmbedder` —— 非学习 baseline。

**v0.5 留的桩**（调用会 raise `NotImplementedError` 指向 ROADMAP.md#v05）：
- `ImageEmbedderStub` —— 计划 backend：CLIP / Qwen-VL / SigLIP / ImageBind
- `VideoEmbedderStub` —— 计划 backend：I-JEPA v2 / TimeSformer / VideoMAE v2 / Qwen-VL 视频模式
- `AudioEmbedderStub` —— 计划 backend：Whisper-v3 encoder / CLAP / AudioMAE

接入真实实现是一个 ~50 行的 `Embedder` 子类，下游零改动。详见 `backend/oransim/runtime/embedding_bus.py`。
</details>

<details>
<summary><b>LightGBM 分位数世界模型</b> —— 快速 baseline</summary>

每个 KPI 3 个分位数回归器（P35 / P50 / P65）。亚毫秒推理、无 GPU 需求。参考：Ke et al. 2017（LightGBM）、Koenker 2005（分位数回归）。

**shipped pkl**（`data/models/world_model_demo.pkl` · `feature_version: demo_v2` · ~3 MB）吃 **23 维特征**：7 标量 + 16 维 PCA 降维的 text embedding。2000 条合成场景里 200 条留出集 R²：impressions 0.88 · clicks 0.79 · conversions 0.71 · revenue 0.75。

```python
wm = get_world_model("lightgbm_quantile")
```
</details>

<details>
<summary><b>预算模型</b> —— Hill 饱和 + 频次疲劳</summary>

不是简单线性扩预算，而是：

$$\text{effective\_impr\_ratio}(x) = \frac{(1+K) \cdot x}{K + x}$$

Michaelis-Menten / Hill 饱和（Dubé & Manchanda 2005），叠加 CTR/CVR 上的频次疲劳（Naik & Raman 2003）：

$$\text{ctr\_decay}(r) = \max(0.5, 1.0 - 0.08 \cdot \max(0, \log_2 r))$$

捕捉到了：边际递减、最优预算点、真实上市曲线。
</details>

<details id="causal-neural-hawkes-process">
<summary><b>因果神经 Hawkes 过程</b> —— 主扩散预测器</summary>

Transformer 参数化的神经时序点过程，预测 14 天级联互动，第一等支持 `do()` 干预下的反事实 rollout。

架构参考：Mei & Eisner (NeurIPS 2017)、Zuo et al. (ICML 2020)、Shchur et al. (ICLR 2020)、Chen et al. (ICLR 2021)、Geng et al. (NeurIPS 2022)、Noorbakhsh & Rodriguez (2022)。

显式区分 treatment/control 事件类型（`organic` vs `paid_boost`）+ 干预感知的强度 decoder，支持「假如第 3 天停止加热会怎样」这类查询，走反事实 rollout loop。

核心类：`oransim.diffusion.CausalNeuralHawkesProcess`。v0.2.0-alpha 已含完整架构 + 训练 loop（NLL + MC compensator）+ 采样器（Ogata thinning）+ 反事实 rollout；预训权重随 OrancBench v0.5 发布。

```python
from oransim.diffusion import get_diffusion_model

nh = get_diffusion_model("causal_neural_hawkes")
factual = nh.forecast(seed_events=[(0, "impression"), (12, "like")])
cf = nh.counterfactual_forecast(
    seed_events,
    intervention={"mute_at_min": 4320}  # 3 天后停止加热
)
```

*需要* `pip install 'oransim[ml]'`。
</details>

<details>
<summary><b>参数化 Hawkes</b> —— 经典 baseline</summary>

指数核的多元 Hawkes 过程（Hawkes 1971）。闭式强度和对数似然；Ogata (1981) thinning 采样器。零依赖 fallback，也是 OrancBench 上因果神经 Hawkes 的对照。

```python
ph = get_diffusion_model("parametric_hawkes")
```
</details>

<details>
<summary><b>沙盘</b> —— 增量重算支持"如果换做法"</summary>

场景会话保留状态，可以迭代：「预算从 10 万改成 15 万，ROI 怎么变？」。只有预算变时不重跑全 agent 模拟；agent 池缓存复用；反事实评估用 union 语义在覆盖/未覆盖人群上做 CATE。
</details>

---

## 📈 性能

Phase 1 基线基于仓内合成语料（**2,000 场景 + 100 事件流 + 50 OrancBench 任务**，可从 [`data/synthetic/`](data/synthetic/) 复现）。详见 [`data/models/data_card.md`](data/models/data_card.md)。下面数字跑在那 2k 场景的 10% 留出集上。

| 指标 | R²（合成数据） | Baseline（线性） | 说明 |
|------|---------------|------------------|------|
| `second_wave_click`     | 0.30 | 0.18 | PRS quantile 中位数 |
| `first_wave_conversion` | 0.33 | 0.21 | PRS quantile 中位数 |
| `cascade_lift`          | 0.39 | 0.25 | 二次传播 mediator |
| `roi_point_estimate`    | 0.33 | 0.19 | 单发回归 |
| `retention_7d`          | 0.29 | 0.17 | 纵向 |

> ⚠️ **可复现性声明** —— 这是**闭环评估**：同一个合成数据生成器同时产出训练集和留出集，我们在自己的生成过程上评自己的模型。它衡量的是**"模型有没有拟合住我们的生成假设"**，不是外部有效性。真实上市准确度需要独立的真实面板 benchmark 或公开的分布外 benchmark —— OrancBench v0.5 计划（见 ROADMAP.md）就是冲后者去的。

完整评估协议见 [`docs/zh/benchmarks/`](docs/zh/benchmarks/)。

---

## 🗺️ 路线图精选

完整路线见 [ROADMAP.md](ROADMAP.md)，分三个时间 horizon × 八个主题。精选：

**v0.2（2026 Q3）—— 预训权重发布**
- 📦 因果 Transformer + 因果神经 Hawkes 在扩展合成语料（冲 ~100k 场景做 OrancBench v0.5）上训好的 checkpoint
- TikTok + Douyin adapter MVP
- Docker Compose · MkDocs · CI

**v0.5（2026 Q4 – 2027 Q1）**
- 🎯 **跨平台迁移学习** —— XHS 预训 → TikTok fine-tune
- ✅ **多 LLM 原生格式** —— Anthropic Messages / Gemini / Qwen DashScope 已在 v0.2 落地；Bedrock Converse + 原生流式留在路线图
- 🎯 **10k 灵魂 Agent 并行**
- ✅ Instagram / YouTube Shorts / Douyin adapter MVP

**v1.0+（2027）**
- 🎯 **因果基础模型 Causal Foundation Model** —— 千万级跨行业 campaign 预训练
- 🎯 **闭环上市优化** —— 带安全约束的实时调优
- 🎯 **差分隐私 + 联邦学习** —— 品牌数据不出私域前提下训练
- 15+ 平台 · 多模态素材理解 · 垂类 sub-benchmark

---

## 🤝 贡献

欢迎各种贡献 —— 平台 adapter、世界模型改进、文档、benchmark、翻译、bug fix。

- **先看**：[CONTRIBUTING.md](CONTRIBUTING.md)
- **Commit 签名** 按 [DCO](CONTRIBUTING.md#developer-certificate-of-origin-dco)：`git commit -s`
- **新手友好 issue**：[按标签筛选](https://github.com/horton2048/augur/issues?q=is%3Aissue+label%3A%22good+first+issue%22)
- **平台 adapter 请求**：[在这里提](https://github.com/horton2048/augur/issues/new?template=adapter_request.yml)

贡献意味着同意以 Apache-2.0 License 发布。不用签 CLA。

---

## 📚 引用

研究中使用请这样引：

```bibtex
@software{augur2026,
  title        = {Augur: Launch Foresight for Makers},
  version      = {0.2.0-alpha},
  date         = {2026-04-18},
  url          = {https://github.com/horton2048/augur},
}
```

`cffconvert` 兼容的元数据见 [CITATION.cff](CITATION.cff)。

---

## 📜 License

Apache License 2.0 —— 详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

第三方依赖保留各自 License。我们与小红书、字节跳动、Meta、Google 以及仓库中任何被提到的平台没有任何隶属关系。

---

<div align="center">
Augur 帮到你的下一次上市？点个 ⭐ 支持开源 —— 它是项目持续往前走的动力。
</div>
