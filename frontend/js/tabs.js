"use strict";

// ─── Tab switching + "更多 ›" dropdown (A3) ────────────

function setTab(name) {
  document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("active", t.dataset.tab===name));
  ["kpi","life","chat","front","v1","society","dag","cate","schema","replay"].forEach(n=>{
    const el = document.getElementById("tab-"+n);
    if (el) el.style.display = (n===name) ? "" : "none";
  });
  if (name === "life" && SESSION_ID) refreshLifecycle();
  if (name === "v1") refreshUEB();
  if (name === "chat" && window.LAST_GROUPCHAT) renderGroupChat(window.LAST_GROUPCHAT);
  if (name === "society" && !window.SOCIETY_LOADED) renderSociety(30000);
  if (name === "schema" && window.LAST_SCHEMA) renderSchemaOutputs(window.LAST_SCHEMA);
  // 战况回放全宽（D11）：切入 replay 时主网格转单栏 + 隐左右栏；切出还原
  const mainEl = document.querySelector("main");
  if (mainEl) mainEl.classList.toggle("replay-full", name === "replay");
  // 战况回放：懒加载——首次切入设内置样本（不输入想法时的默认态）
  if (name === "replay") {
    const f = document.getElementById("replay-frame");
    if (f && !f.getAttribute("src")) f.setAttribute("src", "replay/v3-final.html?data=launch-replay.json");
  }
}

// 战况回放 · 自助态（D14）：输入上市想法 → 真后端 ingest 拿 spec_id → iframe 切到 ?session= 实时回放。
// campaign 主流程不产 launch spec_id，故回放 tab 自带入口（产品决策，标 ⚠待复核）。
async function replayFromIdea() {
  const inp = document.getElementById("replay-idea");
  const status = document.getElementById("replay-status");
  const f = document.getElementById("replay-frame");
  if (!inp || !f) return;
  const idea = (inp.value || "").trim();
  if (!idea) { if (status) status.textContent = "先输入一个上市想法（含品类/定价/渠道更准）。"; return; }
  const apiPort = (window.localStorage && localStorage.getItem("osim_api_port")) || "8001";
  const base = "http://localhost:" + apiPort;
  if (status) status.textContent = "抽取 + grounding 中…";
  try {
    const r = await fetch(base + "/api/launch/ingest", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idea_text: idea, locale: "zh-CN" })
    });
    const j = await r.json();
    if (!r.ok || j.rejected || !j.spec_id) {
      const why = (j.clarification_questions && j.clarification_questions[0]) || j.detail || "非消费垂类或置信度不足，无法模拟。";
      if (status) status.textContent = "✗ " + why;
      return;
    }
    if (status) status.textContent = "推演中…（首帧约数秒，跑完整 90 天 Bass 扩散 + 多 seed）";
    f.onload = function () { if (status) status.textContent = "✓ 本次回放已载入 — 点回放区「开始回放推演」播放五幕。"; };
    f.setAttribute("src", "replay/v3-final.html?session=" + encodeURIComponent(j.spec_id) + "&api=" + encodeURIComponent(apiPort));
  } catch (e) {
    if (status) status.textContent = "✗ 连不上后端（:" + apiPort + "）。确认上市后端在跑。";
  }
}

function toggleTabMore(ev) {
  if (ev) ev.stopPropagation();
  const m = document.getElementById("tab-more-menu");
  if (!m) return;
  m.style.display = (m.style.display === "none" || !m.style.display) ? "block" : "none";
  // click-outside 关闭
  if (m.style.display === "block" && !m._bound) {
    m._bound = true;
    setTimeout(() => {
      const close = (e) => {
        if (!m.contains(e.target) && e.target.id !== "tab-more-btn") {
          m.style.display = "none";
          document.removeEventListener("click", close);
          m._bound = false;
        }
      };
      document.addEventListener("click", close);
    }, 0);
  }
}
