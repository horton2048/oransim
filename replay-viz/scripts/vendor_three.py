"""一次性: 递归下载 three@0.160 核心 + v3 用到的 addons 及其 transitive 依赖到 vendor/three/。

跟着每个 addon 文件的 import 说明符递归抓 (./ ../ 相对 + three/addons/ 绝对)，
'three' 裸说明符指向核心 (单独下 three.module.js)。落 frontend/replay/vendor/three/，
再由调用方 cp 到 replay-viz/app/vendor/three/。
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

VER = "0.160.0"
BASE = f"https://unpkg.com/three@{VER}"
JSM = "examples/jsm"
OUT = Path(__file__).resolve().parents[1] / "frontend_vendor_tmp"  # 先下到 tmp，调用方分发
# 实际落位由调用方决定；这里用仓库根算
REPO = Path(__file__).resolve().parents[2]
DEST = REPO / "frontend" / "replay" / "vendor" / "three"

ENTRY = [
    "controls/OrbitControls.js",
    "postprocessing/EffectComposer.js",
    "postprocessing/RenderPass.js",
    "postprocessing/UnrealBloomPass.js",
    "postprocessing/OutputPass.js",
]

_IMPORT_RE = re.compile(r"""(?:import|export)[^'"]*?from\s*['"]([^'"]+)['"]""")


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    # 1) 核心
    core = fetch(f"{BASE}/build/three.module.js")
    (DEST / "three.module.js").write_text(core, encoding="utf-8")
    print(f"core three.module.js  ({len(core)} bytes)")

    # 2) addons：BFS，rel 路径基于 examples/jsm
    seen: set[str] = set()
    queue = list(ENTRY)  # jsm 相对路径，如 'postprocessing/EffectComposer.js'
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        src = fetch(f"{BASE}/{JSM}/{rel}")
        out = DEST / "addons" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(src, encoding="utf-8")
        # 解析它的 import，找出 jsm 内的依赖
        here = Path(rel).parent
        for spec in _IMPORT_RE.findall(src):
            if spec == "three" or spec.startswith("three/build"):
                continue  # 核心，importmap 解析
            if spec.startswith("three/addons/"):
                dep = spec[len("three/addons/"):]
            elif spec.startswith("./") or spec.startswith("../"):
                dep = str((here / spec).as_posix())
                # 规整 ../
                parts: list[str] = []
                for p in dep.split("/"):
                    if p == "..":
                        parts.pop()
                    elif p in ("", "."):
                        continue
                    else:
                        parts.append(p)
                dep = "/".join(parts)
            else:
                continue  # 其它裸说明符（不应出现）
            if dep not in seen:
                queue.append(dep)
        print(f"  addon {rel}")

    files = sorted(p.relative_to(DEST).as_posix() for p in DEST.rglob("*.js"))
    print(f"\n下载 {len(files)} 个文件 -> {DEST}")
    for f in files:
        print("   ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
