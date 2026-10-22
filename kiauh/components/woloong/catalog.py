# ======================================================================= #
#  Woloong 组件目录（方案 A）：仓库**自闭环**的数据源
#
#  设计要点（P89）：
#   · 组件清单**只从 data/components.json 读** ✓（绝不手写清单 ✗）
#   · 每个组件必须能被某个 install_method 处理；无处理器 = 启动即报错 ✗
#   · tiers 与组件双向校验（悬空引用 = 报错 ✗）
#   · 与旧版 Woloong-OS 的 manifest/stack.json 保持同构（字段名一致 ✓）
# ======================================================================= #
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parent / "data" / "components.json"

TIER_ORDER: List[str] = [
    "mono_basic",
    "mono_advanced",
    "multicolor_basic",
    "multicolor_advanced",
]

TIER_LABEL: Dict[str, str] = {
    "mono_basic": "单色·基础",
    "mono_advanced": "单色·进阶",
    "multicolor_basic": "多色·基础",
    "multicolor_advanced": "多色·进阶",
}


class CatalogError(RuntimeError):
    pass


def load() -> Dict[str, dict]:
    """返回 id -> 组件规格。每次调用都重新读盘（便于运维热改 ✓）。"""
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    comps = raw.get("components") or {}
    if isinstance(comps, list):
        comps = {c["id"]: c for c in comps}
    if not comps:
        raise CatalogError("组件目录为空：%s" % DATA)
    return comps


def tiers() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {t: [] for t in TIER_ORDER}
    for cid, spec in load().items():
        for t in spec.get("tiers") or []:
            out.setdefault(t, []).append(cid)
    return {k: v for k, v in out.items() if v}


def spec(component_id: str) -> dict:
    comps = load()
    if component_id not in comps:
        raise CatalogError("未知组件：%s（可选：%s）" % (component_id, ", ".join(sorted(comps))))
    return comps[component_id]


def validate(supported_methods: List[str]) -> List[str]:
    """校验目录自洽；返回错误列表（空 = 通过 ✓）。"""
    errs: List[str] = []
    comps = load()
    for cid, spec_ in comps.items():
        m = spec_.get("method")
        if m not in supported_methods:
            errs.append("%s: 未知 install_method=%s" % (cid, m))
        for t in spec_.get("tiers") or []:
            if t not in TIER_ORDER:
                errs.append("%s: 未知档位=%s" % (cid, t))
        if spec_.get("method") in ("git_service", "git_extras", "web_static", "script_install", "pip_install"):
            if not spec_.get("repo"):
                errs.append("%s: method=%s 但缺 repo" % (cid, m))
    for t, items in tiers().items():
        for cid in items:
            if cid not in comps:
                errs.append("%s: 档位引用不存在的组件 %s" % (t, cid))
    return errs
