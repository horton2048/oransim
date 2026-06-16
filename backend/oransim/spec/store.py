"""spec/store.py — append-only 版本化 spec 存储 (规范 §5.3, 方案 §6).

进程内 dict + data/world_events.py 同款文件缓存落盘:
    {spec_id: [ProductSpec v0, v1, ...]}
PATCH 即追加新版本 (append-only, 绝不原地改写)。部署假设单 worker (与
SandboxStore 一致)。多 worker / Redis 持久化显式为不做项。

spec_id 内容无关 (uuid hex); revision 从 0 递增。
"""

from __future__ import annotations

import contextlib
import json
import uuid
from pathlib import Path

from .schema import ProductSpec

_DEFAULT_CACHE = Path("/tmp/oransim_specs.json")

# spec_id → [ProductSpec, ...] (index = revision)
_STORE: dict[str, list[ProductSpec]] = {}
_LOCALE: dict[str, str] = {}  # spec_id → locale (报告市场环境标注用)
_CACHE_PATH: Path = _DEFAULT_CACHE


def reset(cache_path: str | Path | None = None) -> None:
    """清空进程内存 (不删磁盘缓存)。可重设缓存路径 (测试隔离)。"""
    global _STORE, _LOCALE, _CACHE_PATH
    _STORE = {}
    _LOCALE = {}
    if cache_path is not None:
        _CACHE_PATH = Path(cache_path)


def _new_spec_id() -> str:
    return uuid.uuid4().hex


def put(spec: ProductSpec, locale: str = "zh-CN") -> tuple[str, int]:
    """新建 spec (v0)。返回 (spec_id, revision=0)。"""
    spec_id = _new_spec_id()
    _STORE[spec_id] = [spec]
    _LOCALE[spec_id] = locale
    _flush()
    return spec_id, 0


def get_locale(spec_id: str) -> str:
    return _LOCALE.get(spec_id, "zh-CN")


def append(spec_id: str, spec: ProductSpec) -> int:
    """PATCH: 追加新版本 (append-only)。返回新 revision。"""
    if spec_id not in _STORE:
        raise KeyError(f"unknown spec_id: {spec_id!r}")
    _STORE[spec_id].append(spec)
    _flush()
    return len(_STORE[spec_id]) - 1


def get(spec_id: str, revision: int | None = None) -> ProductSpec:
    """读取指定版本 (默认最新)。"""
    if spec_id not in _STORE:
        raise KeyError(f"unknown spec_id: {spec_id!r}")
    chain = _STORE[spec_id]
    if revision is None:
        return chain[-1]
    return chain[revision]


def latest_revision(spec_id: str) -> int:
    if spec_id not in _STORE:
        raise KeyError(f"unknown spec_id: {spec_id!r}")
    return len(_STORE[spec_id]) - 1


def versions(spec_id: str) -> list[ProductSpec]:
    return list(_STORE.get(spec_id, []))


def exists(spec_id: str) -> bool:
    return spec_id in _STORE


# ---------------------------------------------------------------- file cache


def _flush() -> None:
    """落盘 (world_events 同款; 失败静默, 不阻塞 API)。"""
    with contextlib.suppress(Exception):
        payload = {
            "specs": {sid: [s.model_dump() for s in chain] for sid, chain in _STORE.items()},
            "locale": dict(_LOCALE),
        }
        _CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def load_from_cache(cache_path: str | Path | None = None) -> int:
    """从磁盘加载版本链 (模拟重启)。返回加载的 spec 数。"""
    global _CACHE_PATH
    path = Path(cache_path) if cache_path is not None else _CACHE_PATH
    _CACHE_PATH = path
    if not path.exists():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    specs = raw.get("specs", raw)  # 兼容旧格式 (无 locale 包裹)
    locales = raw.get("locale", {})
    for sid, chain in specs.items():
        _STORE[sid] = [ProductSpec(**d) for d in chain]
        _LOCALE[sid] = locales.get(sid, "zh-CN")
    return len(specs)
