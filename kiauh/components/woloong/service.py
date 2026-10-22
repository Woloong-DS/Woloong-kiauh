# ======================================================================= #
#  统一入口：kiauh 层只调这里 ✓
#
#  install_component(id) -> 事务包裹 -> 记录 installed.json -> 成功/回滚
#  remove_component(id)  -> 事务包裹 -> 从 installed.json 移除
#  update_component(id)  -> 事务包裹
# ======================================================================= #
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from . import catalog
from .methods import SUPPORTED, make
from .methods.base import ComponentError, STATE, Transaction

INSTALLED = STATE / "installed.json"


def _load_installed() -> Dict[str, dict]:
    if not INSTALLED.exists():
        return {}
    try:
        return json.loads(INSTALLED.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_installed(data: Dict[str, dict]) -> None:
    INSTALLED.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def supported_methods() -> List[str]:
    return sorted(SUPPORTED)


ALL_METHODS = [
    "git_service",
    "git_extras",
    "web_static",
    "config_pack",
    "script_install",
    "pip_install",
    "docs_pack",
    "image_level",
]


def check_catalog() -> List[str]:
    """目录自洽校验：方法名/档位/必填字段（**不**判断是否已迁移 ✓）。"""
    return catalog.validate(ALL_METHODS)


def coverage_gaps() -> List[str]:
    """尚未实现的 install_method（迁移进度 ✓，不算目录错误 ✗）。"""
    missing = [m for m in ALL_METHODS if m not in SUPPORTED]
    ids = sorted({c["id"] for c in catalog.load().values() if c.get("method") in missing})
    return ids


def _tx(tag: str) -> Transaction:
    return Transaction("%s-%s" % (tag, datetime.now().strftime("%Y%m%d-%H%M%S")))


def install_component(component_id: str) -> None:
    spec = catalog.spec(component_id)
    svc = make(spec)
    tx = _tx("install-%s" % component_id)
    try:
        svc.install(tx)
    except Exception:
        tx.rollback()
        raise
    tx.commit()
    data = _load_installed()
    data[component_id] = {
        "name": component_id,
        "method": spec.get("method"),
        "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_installed(data)


def remove_component(component_id: str) -> None:
    spec = catalog.spec(component_id)
    svc = make(spec)
    tx = _tx("remove-%s" % component_id)
    try:
        svc.remove(tx)
    except Exception:
        tx.rollback()
        raise
    tx.commit()
    data = _load_installed()
    data.pop(component_id, None)
    _save_installed(data)


def update_component(component_id: str) -> None:
    spec = catalog.spec(component_id)
    svc = make(spec)
    tx = _tx("update-%s" % component_id)
    try:
        svc.update(tx)
    except Exception:
        tx.rollback()
        raise
    tx.commit()


def component_status(component_id: str) -> dict:
    spec = catalog.spec(component_id)
    return make(spec).status()


def tier_components(tier: str) -> List[str]:
    return catalog.tiers().get(tier, [])


def install_tier(tier: str) -> None:
    comps = tier_components(tier)
    if not comps:
        raise ComponentError("未知或空档位：%s" % tier)
    for cid in comps:
        install_component(cid)
