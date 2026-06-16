"""spec/pipeline.py — 四阶段编译管线 + AudienceFilter intern (launch 版 build_scenario).

阶段: extract → normalize → ground (M2) → scenario_gen (M3)
规范 §3.5、§3.3。

AudienceFilter intern (红线, 规范 §3.3): 对 (spec_id, 修正版本号) 做实例 intern,
同一 spec 版本复用同一 AudienceFilter 对象 → hash_tuple() 里的 id() 语义稳定。
禁止改 hash_tuple() 的 id() 语义; intern 的归属点在本文件, 不在 hash_tuple()。
部署假设单 worker (与 SandboxStore 一致), 进程内 dict 即可。
"""
from __future__ import annotations

from oransim.platforms.xhs.world_model_legacy import AudienceFilter

from .extract import extract_spec
from .normalize import normalize_spec
from .scenario_gen import CompiledScenario, compile_scenario, _make_audience_filter
from .schema import ProductSpec

# (spec_id, revision) → AudienceFilter 实例. 同版本重编译复用同一对象。
_AUDIENCE_INTERN: dict[tuple[str, int], AudienceFilter] = {}


def ingest(idea_text: str) -> ProductSpec:
    """Stage 1+2: extract + normalize (M1 deliverable)."""
    raw = extract_spec(idea_text)
    return normalize_spec(raw)


def _intern_audience_filter(spec: ProductSpec, spec_id: str, revision: int) -> AudienceFilter:
    """对 (spec_id, revision) intern AudienceFilter。同 key → 同实例 (hash 幂等)。"""
    key = (spec_id, int(revision))
    flt = _AUDIENCE_INTERN.get(key)
    if flt is None:
        flt = _make_audience_filter(spec)
        _AUDIENCE_INTERN[key] = flt
    return flt


def reset_intern() -> None:
    """清空 intern 缓存 (测试 / admin 热重载用)。"""
    _AUDIENCE_INTERN.clear()


def _aud_sig(flt: AudienceFilter) -> tuple:
    """AudienceFilter 的值签名 (用于按值 intern, 保证同定向→同实例→hash 稳定/可复现)。"""
    return (
        tuple(flt.age_buckets) if flt.age_buckets else None,
        flt.gender,
        tuple(flt.city_tiers) if flt.city_tiers else None,
        tuple(flt.interest_keywords) if flt.interest_keywords else None,
        flt.boost_strength,
    )


def compile_spec(
    spec: ProductSpec,
    *,
    spec_id: str,
    revision: int = 0,
    kols=None,
    budget_hint_cny: float | None = None,
    seed: int = 0,
    audience_override: AudienceFilter | None = None,
) -> CompiledScenario:
    """Stage 4: 编译为 Scenario (M3). AudienceFilter 经 (spec_id, revision) intern。

    同一 (spec_id, revision) 重编译 → 同 AudienceFilter 实例 → hash_tuple() 相等。
    revision 改变 → 新实例 → hash 改变 (旧缓存语义失效)。

    audience_override (结构化人群定向, launch C 端用): 给定则按 (spec_id, revision, 值签名) intern,
    替代 spec 文本派生的软定向；同定向值复用同实例 → hash 稳定 + 结果可复现。不给则维持原行为。
    """
    if audience_override is not None:
        key = (spec_id, int(revision), _aud_sig(audience_override))
        flt = _AUDIENCE_INTERN.get(key)
        if flt is None:
            flt = audience_override
            _AUDIENCE_INTERN[key] = flt
    else:
        flt = _intern_audience_filter(spec, spec_id, revision)
    return compile_scenario(
        spec,
        audience_filter=flt,
        kols=kols,
        budget_hint_cny=budget_hint_cny,
        seed=seed,
    )
