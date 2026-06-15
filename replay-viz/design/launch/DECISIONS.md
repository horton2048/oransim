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

## 待复核汇总（产品级，给人过目）
- D3：引爆幕要不要具名 KOL？
- D4：合成城市数 / GAZETTEER 覆盖度。
- D6：sentiment 分档阈值。
- D7：funnel 占位 vs 放宽 v3 校验。
