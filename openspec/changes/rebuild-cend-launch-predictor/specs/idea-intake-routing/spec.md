## ADDED Requirements

### Requirement: 任意想法均被受理且分诊到一档

系统 SHALL 接收任意非空产品想法文本,并将其分诊到三档之一(A 校准模拟 / B 未校准结构化 / C LLM 情景),且 MUST NOT 对用户返回"无法预测 / 测不了"的硬拒绝。分诊判定 MUST 复用引擎的领域识别(`grounding`)结果作为依据。

#### Scenario: 已校准消费品 → A 档
- **WHEN** 用户输入一个落在已校准消费品类(具备 fan prior,如美妆 / 食品 / 健身 / 服饰 / 旅行)的想法
- **THEN** 系统判定 tier = A,并走全结构化引擎模拟路径

#### Scenario: 已识别但未校准品类 → B 档
- **WHEN** 用户输入一个 grounding 能识别、但引擎无 fan prior 的消费品类(如饮品 / 家居 / 宠物 / app_tool / 户外 / 收藏)的想法
- **THEN** 系统判定 tier = B,并走"同引擎管线但标未校准"路径

#### Scenario: 引擎域外想法 → C 档(不硬拒)
- **WHEN** 用户输入一个引擎演不了的想法(B2B/SaaS、线下服务、或 grounding 置信不足 / 非消费垂类)
- **THEN** 系统判定 tier = C,并走 LLM 情景推演路径,而非返回硬拒绝消息

#### Scenario: 空输入不算拒绝
- **WHEN** 用户提交空白或纯空格想法
- **THEN** 系统提示补全一句想法(引导,非拒绝),不进入任何预测档位

### Requirement: 分诊结果对同一输入可复现

系统 SHALL 对同一想法文本给出确定且可复现的档位判定(档位本身不依赖 LLM 的随机性)。

#### Scenario: 同一想法两次受理得同档
- **WHEN** 同一想法文本被连续受理两次
- **THEN** 两次返回的 tier 判定相同
