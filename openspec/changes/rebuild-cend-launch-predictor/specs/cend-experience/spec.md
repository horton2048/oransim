## ADDED Requirements

### Requirement: 单一 C 端主线流程

系统 SHALL 提供唯一一个 C 端入口,主线为:落地页(一句话输入 + 可选受众细调)→ 一键揭幕动画(最短仪式时长)→ 结果卡。pro 操作台 `launch-console.html` MUST NOT 再作为产品入口提供。

#### Scenario: 提交想法走完主线
- **WHEN** 用户在落地页输入想法并点击「开始预演」
- **THEN** 先播揭幕动画(至少最短仪式时长),随后展示结果卡

#### Scenario: pro 操作台不再是入口
- **WHEN** 产品对外暴露入口
- **THEN** 仅 C 端一个入口;不提供 pro 操作台作为独立产品入口

### Requirement: 结果卡随档位变形

结果卡 SHALL 根据 `tier` 呈现不同形态:A/B 档显示结构化 KPI(触达/采纳/营收)、会火指数、最大阻力、关键变量;C 档显示定性情景(盘子区间/买家/渠道/采纳形状/风险),且 MUST NOT 显示 A 档式精确 KPI 数字块。

#### Scenario: A 档结果卡
- **WHEN** 结果为 A 档
- **THEN** 卡片显示触达/采纳/营收 + 会火指数 + 最大阻力(objection) + 关键变量 + 回放入口

#### Scenario: C 档结果卡
- **WHEN** 结果为 C 档
- **THEN** 卡片显示定性情景与区间,无精确 KPI 数字块,并以"未校准 LLM 推演"形态呈现

### Requirement: diorama 回放入口随档位可用

A/B 档 SHALL 在结果卡提供「看电影回放」拉起 diorama,且回放 MUST 展示**该想法本身**的城市与战况(非内嵌 demo)。C 档无可信微缩沙盘时 SHALL 隐藏或降级回放入口,MUST NOT 播放与该想法无关的 demo。

#### Scenario: A/B 档回放出真城市
- **WHEN** 用户在 A/B 档结果卡点击「看电影回放」
- **THEN** diorama 加载该想法的真实城市点阵与战况(非散粉等内嵌 demo)

#### Scenario: C 档不放无关 demo
- **WHEN** 结果为 C 档
- **THEN** 回放入口隐藏或降级,不出现无关 demo 回放

### Requirement: 后端连通与错误可见

C 端 SHALL 在后端不可达 / 返回错误时给出明确提示,MUST NOT 空转无反馈。

#### Scenario: 后端连不上
- **WHEN** C 端无法连到后端或后端返回错误
- **THEN** 界面显示明确错误提示(指明连不上 / 出错原因),而非一直转圈无反馈
