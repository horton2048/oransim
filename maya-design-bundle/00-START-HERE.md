# Maya — Claude Design 输入包 · 从这里开始

这是一份喂给 **Claude Design**（claude.ai/design）的输入 bundle，用来从零重做 **Maya** 的前端。
闭环：**claude.ai/design 出设计 → 导出 → 把产物丢回 Claude Code（我）→ 接真后端跑通**。

> 产品名：**Maya**（原项目代号 oransim 已弃用，界面上任何地方都不要出现 oransim）。
> 后端 API 路径 `/api/*` 属于后端实现，**保持不变**，不是品牌名。

---

## 包里有什么

| 文件 | 给谁 | 怎么用 |
|------|------|--------|
| `00-START-HERE.md` | 你 | 本说明 |
| `01-DESIGN-BRIEF.md` | **Claude Design** | 主 brief。**整段粘进 claude.ai/design 的输入框**（或转 DOCX 上传） |
| `02-SCREENS-IA.md` | **Claude Design** | 逐屏/逐区信息架构 + 保留/砍清单。随 brief 一起给 |
| `03-API-CONTRACT.md` | 你 + 回传后的我 | 后端数据契约。设计阶段让它知道字段；回传后我据此接线 |
| `sample-data.json` | **Claude Design** | **真实** `/api/predict` 响应（精简版，29KB）。**上传给它做数据绑定**，别让它编数字 |
| `sample-data-full.json` | 需要时 | 完整响应（112KB，全部 60 条语录 / 64 DAG 节点 / 17 schema 块） |
| `05-WIRE-BACK.md` | 回传后的我 | 你拿到设计产物后丢给我，我照这份接后端 + 起服务 |

---

## 操作步骤（你来做）

### 第 1 步 · 在 claude.ai/design 生成设计
1. 打开 **claude.ai/design**（需 Pro/Max/Team/Enterprise）
2. 新建项目，**把 `01-DESIGN-BRIEF.md` 全文粘进输入框**
3. **上传 `sample-data.json`**（让它绑定真实字段和量级）
4. 可选：把 `02-SCREENS-IA.md` 也粘进去，或第二轮再给
5. ⚠️ **不要**让它去读旧代码库建设计系统——我们是要**推翻**旧视觉，不是继承。给全新 brief。
6. 按 brief 里的节奏：先出**主仪表盘**整体视觉，满意后逐个区块往下做
7. 满意后**导出**：standalone HTML，或 Claude Design 的「handoff bundle for Claude Code」

### 第 2 步 · 丢回给我跑通
把导出的产物（HTML/React 文件夹，或 handoff bundle）放进这个仓库，连同 `05-WIRE-BACK.md` 一起告诉我「按 WIRE-BACK 接后端」。我会：
- 把静态设计接到真 `/api/predict` 等端点（契约见 `03-API-CONTRACT.md`）
- 处理那 3 块 Claude Design 做不了的重型可视化（WebGL 星图 / 因果 DAG / 级联动画）——用现有调好的模块挂进去
- 改 `run-oransim.ps1` 的服务目录，本地 + 局域网起服务，验证 health 通

---

## 一句话提醒
Claude Design 只做**前端可视产物**，没有后端/数据库/API。所以它产出的是「带 mock 数据的漂亮壳」，**真后端由我（Claude Code）在回传后接上**。这正是这个 bundle 的设计目的。
