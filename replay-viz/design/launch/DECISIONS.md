# 上市回放前端 · DECISIONS（判断日志）

> 计划没覆盖的歧义，按四条铁律（字节级兼容 / 诚实原则 / 薄改原则 / 渐进纪律）自决后在此记一行。
> 产品级决策（合成口径 / KOL 取舍 / 阈值 / 方案级取舍）即使已决断也标「⚠待复核」，继续不停等。

---

| # | 日期 | 决策 | 理由 | 复核 |
|---|---|---|---|---|
| D1 | 2026-06-12 | **数据源 = 上市模拟 `/api/launch/simulate`**，非旧 campaign `/api/predict` | 它是产品本体（M0–M8 已建）；campaign 是更早遗留、原型当初的占位 | — |
| D2 | 2026-06-12 | **架构 A 为主 + 判决面板局部 B** | 多数缺口可由适配器确定性合成、v3 不动（薄改）；唯判决面板把 P35/P50/P65 塞进五级漏斗槽=伪造结构（违诚实），故该处改 v3 直读 metrics | — |
| D3 | 2026-06-12 | **kols 默认空数组**（引爆幕降级展示起势曲线） | launch 报告无 kols 块；合成具名 KOL 信息量低且易冒充真值。先不阻塞 | ⚠待复核（是否要用 spec KOL 名单合成开火点） |
| D4 | 2026-06-12 | **cities 从 `effective_city_dist` 合成**，坐标取 GAZETTEER | 层级占比是真值锚点，非凭空；坐标本就是映射（campaign 同口径） | ⚠待复核（目标城市数 N=25 是否够铺满五个 tier） |
| D5 | 2026-06-12 | **souls.text = objection 原话逐字**，persona = niche·tier 短标签 | objection 是真值且红线要求逐字；不杜撰具体人设 | — |
| D6 | 2026-06-12 | **souls.sentiment 由 purchase_intent_7d 分档**（≥0.5→1 / ≤0.05→-1 / else 0） | launch persona 无 sentiment 字段；需确定性派生供弹幕着色 | ⚠待复核（分档阈值） |
| D7 | 2026-06-12 | **funnel_percentiles 写最小占位**过 validReplay，判决面板改读 metrics | 守诚实（不真造漏斗）同时不放宽 v3 校验（最小改动面） | ⚠待复核（备选：放宽 validReplay，归 B） |
| D8 | 2026-06-12 | **M2 先 CLI 静态 replay.json 跑通，后端路由留 M4** | 渐进纪律：先把数据线/像素打通，再碰后端路由与 R5（session 是否持有完整报告） | — |
| D9 | 2026-06-12→13 | **失衡节拍 → 已落长尾快进**：launch 第 11 天饱和 90%、后 80 天平尾。**自决方案：累计过 90% 后 simT 6× 推进（v3 loop 2301 加 `_warp`）**——数据不变、全 90 天仍播、戏份留前期、无戏长尾飞过。campaign 不触发。实测早期 ~0.2 vs 长尾 ~1.1 天/秒（≈5.5×） | 非线性时间压缩比「裁掉长尾」诚实（不藏数据），比「线性全放」可看（不干拖 80 天）；6× 是自决系数 | ⚠待复核（6× 快进系数 / 要不要改成裁剪或线性；用户看过回放后定，可调常数） |
| D10 | 2026-06-12 | **v3 加 `?data=` 取数参数**（默认仍 `./replay.json`） | 薄改：M2 需指向 launch 文件做验收且不覆盖 campaign demo；同时是 M4 `?session=` 取数的前身 | — |

---

| D11 | 2026-06-12→13 | **回放窄列 → 已落全宽**：`main.replay-full` 类，replay tab 激活转单栏 + 隐左右栏（结果区 229px→985px 自验）。切出还原 | 影院式 diorama 需要画布；单栏特判最小侵入（不动其它 tab 布局），切换即时还原 | ⚠待复核（默认全宽是我自决；你若想保留三栏/给个全屏切换钮可改） |
| D12 | 2026-06-12 | **自托管 ✅ 完结**：**part-a 地球贴图** + **part-b three.js 核心+addons**（`scripts/vendor_three.py` 递归下 12 文件落 `vendor/three/`，importmap 改本地）。Playwright 自验零 unpkg、bloom 渲染正常 | 消除 unpkg 抖动导致的黑球/黑屏风险；递归下载器跟 import 树抓全 transitive 依赖，避免手猜漏文件 | 仅余 Google Fonts 外网依赖（css2）——挂则回退系统字体不黑屏，低优先；如需全离线可一并自托管字体 |
| D13 | 2026-06-12 | **静态资源无版本号**（M4 实测注意点）：改 tabs.js 后浏览器吃旧缓存（script src 无 `?v=`）；本仓库无脚本版本约定 | 非本线引入，属既有部署模式；返回用户拿到旧 JS 需强刷或加版本号 | ⚠待复核（部署时若要 returning user 即时拿到新 JS，给 js 引用加版本戳） |

| D14 | 2026-06-12 | **主 SPA 无 launch spec_id 源**（M4 e2e 发现）→ **已落「回放 tab 自带 idea 输入框」方案**：tab 内输入想法→`replayFromIdea()`→真后端 ingest 拿 spec_id→iframe 切 `?session=`。真后端 e2e 已验（输入新想法→渲染该想法回放）。不输入则默认内置样本 | campaign 与 launch 是两条后端流；自带入口最不侵入 campaign 主流程（不动 predict 链路） | ⚠待复核（这是三选项里我自决的一个；你若想要「SPA 主流程直接产 launch」或别的入口形态，可改） |
| D15 | 2026-06-12→13 | **适配器解析已健壮化**：replay 路由 import 改「`OSIM_REPLAY_VIZ_DIR` 配置 > monorepo 默认」，缺失显式 500（非裸 ImportError）。pytest 覆盖 env 覆盖/坏目录。**自决：不搬适配器进后端包**（会动 13 测试 + replay-viz 子项目自包含身份），保单一源 + 部署可配 | 搬包是更大重构、收益只在「后端独立打成 wheel 且不含 replay-viz」时才兑现，当前 monorepo 不需要；健壮化是低风险可验的中间态 | ⚠待复核（若将来后端要独立 wheel 分发，再把 replay_export+launch_replay_export 挪进 oransim.viz 包） |

| D16 | 2026-06-13 | **字体取扎实降级栈、不全量自托管**：v3 三套字体 var 补优秀系统 CJK 回退；Google Fonts 留渐进增强 | CJK 全量自托管 = 数 MB woff2（Google 按 unicode-range 切上百子集），为「挂了回退系统字体」的装饰项塞这么多不成比例；扎实降级栈即可保证挂了也好看 | ⚠待复核（若公网全离线必须零外网字体请求：用 pyftsubset 把静态标题字 subset 自托管 + 动态文本走系统字体） |

| D17 | 2026-06-15 | **宿主纠正（用户驳回 D1）**：产品前端 = 独立 `launch-console.html`（照 v4-console 视觉做 launch 版），**不是**把回放挂进旧 `frontend/` campaign 广告文案 SPA。M4 挂 tab 那步作废 | 用户明确："v4-console 才是我要的样子；挂进旧 SPA 完全不对"。复用真资产（适配器/后端路由/v3 回放）不变 | — |
| D18 | 2026-06-15 | **卡片映射（"都保留"遇无数据时的替换，FE-M5）**：五阶漏斗→指标分位带(P35/P50/P65)；KOL优选→命名干预叙事卡；分平台/宏观→降级(渠道占比/潜在盘/季节窗，标 stub/未校准)；KPI 6→触达/试用/采纳/采纳率/营收/回本；龙卷风→干预卡Δ采纳 | launch 后端无五阶漏斗/无KOL块；卡槽保留+填最贴近的 launch 等价物，既守"都保留"又不留空壳/不伪造 | ⚠待复核（你看 filled 截图后定这些替换是否合意） |
| D19 | 2026-06-15 | **采纳率显示精度**：现 pct() 1 位小数→微小率显 0.0%（如 27/1.67M）。本轮未改 | 信息量不足但非错（真值就这么小）；打磨项 | ⚠待复核（要不要改成 万分比/更多小数） |

| D20 | 2026-06-15 | **删 launch-console 的死 Smiley @font-face**：原 v4 的 得意黑 两个 jsdelivr CDN 均 404（v4 本就回退 Noto），删 @font-face + --disp 改纯 Noto → console 0 报错 | 消除外网噪声/404；与 v4 实际渲染一致（v4 也没真加载到 Smiley）；得意黑本体如需→自托管 woff2 到 vendor/ 再加回 | ⚠待复核（要不要自托管 得意黑 显示字体提升标题观感） |

| D21 | 2026-06-15 | **reveal overlay 最短 1.8s**：真后端可能 <1s 响应，纯绑后端会让揭幕动画一闪而过失去 v4 仪式感；故 overlay 至少跑 1.8s（数据更快也跑满，更慢则等数据）后揭幕 | 还原 v4 那个刻意 ~2s 的「唤醒十万人群」揭幕感；render 在 overlay 后揭幕（数据先填充背后） | — |

| D22 | 2026-06-15 | **修 bug：拒绝/错误消息被「待预演」遮罩盖住**（用户实测「划词解释工具/vibecoding」→「没反应」）。根因：#disclaimer 在 position:relative 容器内、#idle veil(absolute inset:0) 之下；拒绝路径不调 render() 故 idle 不隐藏→消息被盖。修：把 #disclaimer 移到遮罩外（容器上方，任何状态可见）+ 拒绝文案改为「无法模拟：只推演消费品上市…」明示原因 | 后端对非消费品类(开发者工具/SaaS)正确硬拒绝是设计行为；问题只在前端没把拒绝可见化 | 注：launch 模型只建模消费品采纳；dev-tool/SaaS 本就不在范围（非 bug，是 scope） |

| D23 | 2026-06-15 | **会火指数公式（FE-M6 启发式）**：score=40%意向+35%试用率+25%置信，0-100。mock 模式 persona 意向普遍低(~0.02)→多数想法落 24-40 分(★1-2)、显「存疑」 | C端要一个直观「会不会火」总分；当前 mock 数据意向低导致分数偏低且区间窄，真 LLM 模式会更有区分度 | ⚠待复核（公式权重/锚定；要不要拉高区分度、或换更乐观的口径；真 LLM 下重校） |
| D24 | 2026-06-15 | **分享=复制文案/截图（最小实现）**：点「分享这张卡」复制一句结果摘要到剪贴板 + 提示截图；无图片生成/短链/海报 | 先打通主流程，海报/分享图是独立增量 | ⚠待复核（要不要做分享海报图/短链） |

| D25 | 2026-06-15 | **结构化人群定向（FE-M6，用户要求「调模拟目标用户参数」）→ 后端增量已落**：SimulateOverrides 加 audience_age_buckets/gender/city_tiers；compile_spec 加 audience_override（按值 intern 保 hash 稳定/可复现）；_simulate_sync 构造 AudienceFilter 注入。前端 launch-c 加「细调目标人群」可展开区(性别单选/年龄+城市多选 chips)。复用世界模型 `_audience_score`（命中×2/其余÷2 软定向） | 用户选「结构化(需后端增量)」而非轻量文字版；人群本体已有 age/gender/city 维度、机制现成，增量小且真实生效 | 实测：面膜定向女 vs 男 → 采纳 51 vs 21（2.4×，方向合理）；pytest 4/4 + 回归 28/28；souls/会火指数对定向不敏感(souls 采样未按受众, 见 D23) ⚠待复核(要不要让 souls 也按受众采样) |

| D26 | 2026-06-16 | **修 bug：diorama 回放对无 fan-prior 品类失真**（用户切真 LLM 时发现）。根因：`fan_profile_summary` 只认 8 个 niche（beauty/fashion/finance/fitness/food/mom/tech/travel），**beverage/electronics/home/pet/parenting 早退、不产 `effective_city_dist`** → 回放适配器城市点阵空 → v3 形状校验不过 → 回退内嵌散粉 demo。**一直如此、非本次回归**（mock 下咖啡也命中 beverage，旧"咖啡回放"其实也是 demo，只是 demo 也像样没被发现）。修：`_simulate_sync` 在 fps 缺 `effective_city_dist` 时，由 `pop.city_idx` 统计**基础人口层级分布**注入（无 prior=均匀加权=基础人口分布，非编造，标 `city_dist_source=base_population`）。router 层、不动引擎。实测咖啡回放出 24 城（北京/上海/南宁…）。回放黄金未变（黄金 idea 属 in-prior 品类，跳过注入分支） | advisor 指方案：base-pop 比"硬编默认"诚实、比"niche 别名(pet→?)"语义可靠；pop 本就有该真值，只是被 fan_profile 早退丢了 | ⚠待复核（更优是给 beverage/home/pet 也配 fan prior；另 v3 unmapped 披露显示「[object Object]」是纯显示层小 bug 待修） |
| D27 | 2026-06-16 | **真 LLM 全量接入（用户："全量接这个模型，把 think 关掉"）→ Agnes AI**。先前 .env 配 MiniMax-Text-01 套餐不支持(2061)→ 静默回退 mock（即此前"真后端"其实一直 mock 抽取）。改用 **Agnes AI**（OpenAI 兼容免费网关，`apihub.agnes-ai.com/v1`，模型 `agnes-2.0-flash` 非推理无 `<think>`、~1.5s/次）。三处接通：① 抽取(extract 本就读 LLM_MODE) ② **souls 放开**：`launch.py` `use_llm=ov.use_llm`、C 端 launch-c 发 `use_llm:true` ③ **新增 launch 版 LLM soul**：`soul_infer_llm_launch`（产 will_try/would_pay/objection/intent，与 infer_one_launch 同形）+ `soul.py` LLM 路径按 mode 路由（含 fallback 走 launch mock）。另修 extract 把模型偶发的 `{value,provenance}` 字段解包。实测咖啡：抽取出目标用户/卖点、souls 意向 0.0–0.6 真实分布、objection 逐字 persona 化。新增单测 test_launch_soul_llm 3/3 + 回归 18/18 | 用户给的 agnes key（永久有效，见 reference_agnes_ai_api）+ 选 flash（快/免费/无 think）适合 soul 扇出；launch 版 soul 是必需（否则证词字段错位丢空，比 mock 退步） | ⚠待复核（**会火指数反而降**：souls 从通用人群抽样、且 D25 souls 不认受众→意向被非目标人群拉低；要真正体现"聪明"需让 souls 按受众采样。另：真 LLM 非确定→每跑结果浮动，与字节级黄金不冲突因测试跑 mock） |

## 待复核汇总（产品级，给人过目）
- **D27：真 LLM 已接通但「会火指数」反而降——根因 souls 未按受众采样(D25)，是当前最该补的一刀。**
- **D26：beverage/home/pet 等暂用基础人口城市分布；要不要给它们配真 fan prior。**
- D3：引爆幕要不要具名 KOL？
- D4：合成城市数 / GAZETTEER 覆盖度。
- D6：sentiment 分档阈值。
- D7：funnel 占位 vs 放宽 v3 校验。
