"""spec/ground.py — niche / 人群 / 替代品三映射 + 置信度闸门.

将 ProductSpec 对齐到 niches.json 的 10 个 CN 社交消费垂类:
beauty / fashion / food / beverage / fitness / electronics / travel / home /
pet / parenting.

策略 (方案 §3.4 表 a):
  1. B2B/SaaS 强信号 → 硬拒绝 (诚实原则: 不静默映射到消费垂类).
  2. synonyms() + 富品类关键词表, 按**最早出现位置**命中 (中文文案先报产品名,
     首个产品词决定 niche, 天然压制 "健身人群" 这类受众附带词).
  3. 关键词未命中 → 嵌入余弦兜底 (BUS product_categories 源), 置信度较低.
  4. 语料覆盖检查 (category_notes): grounded niche 无覆盖 → 拉低置信度.
  5. grounding_confidence < 0.55 → 硬拒绝, 返回 clarification_questions (闸门非警告).

依赖方向: spec/ → engine (config/niches, runtime/embedding_bus). 引擎层不反向
import 本模块 (REG-4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from oransim.config import niches as _niches

from .schema import ProductSpec

# ── 阈值与置信度参数 (产品级标定, 见 DECISIONS.md) ──────────────────────────
CONFIDENCE_THRESHOLD = 0.55
_SYNONYM_BASE_CONF = 0.92
_EMBED_CONF_CAP = 0.70
_NO_COVERAGE_PENALTY = 0.5  # grounded niche 无语料覆盖 → 置信度 ×0.5
_COVERAGE_OK = 0.45  # category_notes 自匹配相似度高于此视为有覆盖

# ── B2B/SaaS 强信号: 命中即硬拒绝 (诚实原则, 方案明令禁止静默映射) ───────────
_B2B_SIGNALS = (
    "saas",
    "b2b",
    "b2b2c",
    "to b",
    "系统集成",
    "医疗器械",
    "预测性维护",
    "mes",
    "授权年费",
    "/席",
    " 席",
    "席/",
    "行业展会",
    "企业法务",
)

# ── 富品类关键词表: 产品名词 → niche key. 受众/渠道词不入表. ────────────────
# 与 niches.synonyms() 合并, 本表补 synonyms 未覆盖的具体产品名词 (洗发水/素颜霜
# /香氛机/卫衣/喂食器 等), 含英文条目 (出海 idea). 命中按文本最早出现位置取胜.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "beauty": [
        "洗发水",
        "护发",
        "精油",
        "素颜霜",
        "防晒",
        "spf",
        "面膜",
        "玻尿酸",
        "精华",
        "保湿",
        "lip balm",
        "lipstick",
        "skincare",
        "唇膏",
        "护肤",
        # 洁面类 (洗面奶/慕斯) 是高频美妆品类, 旧表漏收 → 误落 C 档 (像素验收发现)。
        # 用「洁面/洗面奶/洁面乳/洁面慕斯」精确词, 不收裸「慕斯」(慕斯蛋糕属 food, 防误判)。
        "洁面",
        "洗面奶",
        "洁面乳",
        "洁面慕斯",
        "卸妆",
        "面霜",
        "眼霜",
        "气垫",
        "粉底",
    ],
    "fashion": [
        "卫衣",
        "国潮",
        "帆布包",
        "折叠包",
        "手提包",
        "背包",
        "卫裤",
        "外套",
        "hoodie",
        "tote",
        "bag",
        "联名款",
    ],
    "food": [
        "燕麦奶",
        "植物奶",
        "燕麦",
        "代餐",
        "零食",
        "饱腹",
        "noodle",
        "instant noodle",
        "snack",
        "麦片",
        "坚果",
        "螺蛳粉",
    ],
    "beverage": [
        "气泡水",
        "苏打水",
        "无糖茶",
        "冷萃",
        "咖啡液",
        "茶包",
    ],
    "fitness": [
        "蛋白棒",
        "蛋白",
        "可穿戴",
        "深蹲",
        "瑜伽垫",
        "筋膜枪",
        "代餐粉",
        "protein",
        "增肌",
    ],
    "electronics": [
        "手机壳",
        "血压手环",
        "手环",
        "三脚架",
        "耳机",
        "充电",
        "数据线",
        "摄影",
        "tripod",
        "earbuds",
        "gadget",
        "智能硬件",
    ],
    "travel": [
        "行李箱",
        "旅行装",
        "颈枕",
        "护照夹",
        "登机箱",
        "luggage",
    ],
    "home": [
        "香氛机",
        "香薰",
        "浇水",
        "花园",
        "收纳盒",
        "台灯",
        "加湿器",
        "扫地",
        "diffuser",
        "花艺",
    ],
    "pet": [
        "猫零食",
        "冻干",
        "喂食器",
        "猫厕所",
        "猫砂",
        "宠物",
        "养宠",
        "养猫",
        "狗粮",
        "猫粮",
        "litter",
        "pet",
    ],
    "parenting": [
        "亲子",
        "育儿",
        "宝妈",
        "新手妈妈",
        "辅食",
        "童装",
        "婴儿",
        "孕",
    ],
}


@dataclass
class GroundingResult:
    """Grounding 输出: niche 映射 + 置信度 + 诚实标记."""

    niche_key: str | None  # 硬拒绝时为 None
    grounding_confidence: float
    matched_synonyms: list[str] = field(default_factory=list)
    corpus_coverage: float = 1.0
    clarification_questions: list[str] = field(default_factory=list)
    rejected: bool = False
    method: str = ""  # "synonyms" | "embedding" | "rejected"
    reject_reason: str | None = None  # "b2b" | "unsupported_vertical" | None


def _grounding_text(spec: ProductSpec) -> str:
    """拼接用于匹配的文本.

    one_liner (原始 idea 截断) 在前: 中文文案先报产品名, 最早位置匹配能锁定产品
    类目. category_raw 放最后兜底——它由 extract._detect_category 派生, 可能已被
    受众词污染 (如燕麦奶被 '健身人群' 带成 '健身'), 不可前置否则误导 grounding.
    """
    parts = [spec.one_liner or "", spec.product_name or "", spec.category_raw or ""]
    return " ".join(parts).lower()


def _is_b2b(text: str) -> bool:
    return any(sig in text for sig in _B2B_SIGNALS)


def _keyword_table() -> dict[str, list[str]]:
    """合并 niches.synonyms() 与本模块富品类表 (synonyms 在前, 同 niche 追加).

    include_v2=True: grounding 覆盖 M8 新增上市域品类 (app_tool/edu_service/... )，
    使新品类可被 grounded (AT-M8-04); 不影响 campaign KOL 库 (后者用默认 campaign 域)。
    """
    syn = _niches.synonyms(include_v2=True)
    table: dict[str, list[str]] = {}
    for niche in _niches.niche_keys(include_v2=True):
        kws = list(syn.get(niche, []))
        kws.extend(_CATEGORY_KEYWORDS.get(niche, []))
        table[niche] = kws
    # 兼容: 富品类表中可能有 niche 不在 niche_keys 时也并入
    for niche, kws in _CATEGORY_KEYWORDS.items():
        table.setdefault(niche, list(kws))
    return table


def _match_by_earliest(text: str) -> tuple[str | None, str | None]:
    """返回 (niche_key, matched_keyword): 全表中在 text 里**最早出现**的关键词所属 niche.

    中文产品文案通常先报产品名 → 首个产品词决定 niche, 受众/场景附带词 (如
    '健身人群' 出现在后) 不会压过真正的产品类目.
    """
    table = _keyword_table()
    best_pos = len(text) + 1
    best_niche: str | None = None
    best_kw: str | None = None
    for niche, kws in table.items():
        for kw in kws:
            if not kw:
                continue
            p = text.find(kw.lower())
            if p >= 0 and p < best_pos:
                best_pos = p
                best_niche = niche
                best_kw = kw
    return best_niche, best_kw


def _embed_fallback(spec: ProductSpec, bus) -> tuple[str | None, float]:
    """嵌入余弦兜底: 用 spec 文本检索 BUS product_categories 源, 取 top-1 niche.

    bus 为 None 或源不存在/空 → 返回 (None, 0.0). 仅在关键词全表未命中时调用,
    保证 AT-M2-07 '关键词命中不走嵌入' (确定性优先).
    """
    if bus is None:
        return None, 0.0
    src = "product_categories"
    try:
        vecs = bus.vectors(src)
    except Exception:
        return None, 0.0
    if vecs is None or len(vecs) == 0:
        return None, 0.0
    # category bias caption 作为各 niche 代表向量已被 index; 用 spec 文本查询.
    rec = None
    try:
        rec = bus._sources.get(src)
    except Exception:
        rec = None
    if rec is None:
        return None, 0.0
    query_text = _grounding_text(spec)
    qvec = rec.embedder.embed(query_text)
    hits = bus.search(qvec, src, top_k=1)
    if not hits:
        return None, 0.0
    item = hits[0]["item"]
    score = max(0.0, float(hits[0]["score"]))
    # item 形如 {"niche": key, "text": ...} 或 "niche::text"; 解析 niche.
    niche = None
    if isinstance(item, dict):
        niche = item.get("niche")
    elif isinstance(item, str) and "::" in item:
        niche = item.split("::", 1)[0]
    return niche, score


def _corpus_coverage(niche_key: str | None, bus) -> float:
    """category_notes 语料覆盖度: 用 niche 代表文本自检索, 取 top-1 相似度 ∈[0,1].

    bus 为 None 或 category_notes 源缺失/空 → 返回 1.0 (无法核验时不惩罚, 保
    AT-M2-01 无需 bootstrap). 命中自身文本时相似度≈1.0; 无覆盖伪品类相似度低.
    """
    if niche_key is None or bus is None:
        return 1.0
    src = "category_notes"
    try:
        vecs = bus.vectors(src)
        rec = bus._sources.get(src)
    except Exception:
        return 1.0
    if vecs is None or len(vecs) == 0 or rec is None:
        return 1.0
    caption = _niches.bias_captions(include_v2=True).get(niche_key, niche_key)
    qvec = rec.embedder.embed(f"{niche_key}::{caption}")
    hits = bus.search(qvec, src, top_k=1)
    if not hits:
        return 0.0
    return max(0.0, min(1.0, float(hits[0]["score"])))


def _clarification_questions(reason: str) -> list[str]:
    if reason == "b2b":
        return [
            "这是面向企业的 B2B 工具/SaaS，还是面向个人消费者的产品？",
            "目标用户是企业采购方还是 C 端消费者？",
        ]
    return [
        "这个产品最贴近哪个消费品类（美妆 / 服饰 / 食品 / 饮品 / 健身 / 数码 / 旅行 / 家居 / 宠物 / 母婴）？",
        "主要面向的消费人群与使用场景是什么？",
        "定价大概多少？走哪些销售渠道？",
    ]


def ground(spec: ProductSpec, *, bus=None) -> GroundingResult:
    """将 ProductSpec 对齐到 niche, 计算置信度并施加硬拒绝闸门.

    bus: 可选 EmbeddingBus, 提供 product_categories (嵌入兜底) 与 category_notes
    (语料覆盖) 两源. 缺省时跳过嵌入路径与覆盖惩罚.
    """
    text = _grounding_text(spec)

    # 1. B2B 硬拒绝
    if _is_b2b(text):
        return GroundingResult(
            niche_key=None,
            grounding_confidence=0.0,
            rejected=True,
            method="rejected",
            reject_reason="b2b",
            clarification_questions=_clarification_questions("b2b"),
        )

    # 2. 关键词最早位置命中 (确定性优先)
    niche, matched_kw = _match_by_earliest(text)
    if niche is not None:
        method = "synonyms"
        base_conf = _SYNONYM_BASE_CONF
        matched = [matched_kw] if matched_kw else []
    else:
        # 3. 嵌入兜底
        niche, score = _embed_fallback(spec, bus)
        method = "embedding"
        base_conf = min(_EMBED_CONF_CAP, score) if niche else 0.0
        matched = []

    # 4. 语料覆盖
    coverage = _corpus_coverage(niche, bus)
    coverage_factor = 1.0 if coverage >= _COVERAGE_OK else _NO_COVERAGE_PENALTY
    confidence = base_conf * coverage_factor if niche else 0.0

    # 5. 置信度闸门 (>= 阈值通过)
    if niche is None or confidence < CONFIDENCE_THRESHOLD:
        return GroundingResult(
            niche_key=None,
            grounding_confidence=round(confidence, 4),
            matched_synonyms=matched,
            corpus_coverage=round(coverage, 4),
            rejected=True,
            method="rejected" if niche is None else method,
            reject_reason="unsupported_vertical",
            clarification_questions=_clarification_questions("unsupported_vertical"),
        )

    return GroundingResult(
        niche_key=niche,
        grounding_confidence=round(confidence, 4),
        matched_synonyms=matched,
        corpus_coverage=round(coverage, 4),
        rejected=False,
        method=method,
    )
