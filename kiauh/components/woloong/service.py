# ======================================================================= #
#  统一入口：kiauh 层只调这里 ✓
#
#  install_component(id) -> 事务包裹 -> 记录 installed.json -> 成功/回滚
#  remove_component(id)  -> 事务包裹 -> 从 installed.json 移除
#  update_component(id)  -> 事务包裹
# ======================================================================= #
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from . import catalog
from .methods import SUPPORTED, make
from .methods.base import ComponentError, STATE, Transaction

INSTALLED = STATE / "installed.json"


def _reload_moonraker() -> None:
    """★ OI-017：卸载/安装后 Moonraker 不会热加载配置 ✗
    -> 已删的更新条目仍留在内存里（网页/接口还能看到 ✗）
    用完即走的自重启接口清掉缓存 ✓（失败不阻断 ✓）
    """
    try:
        req = urllib.request.Request(
            "http://localhost:7125/machine/services/restart?service=moonraker",
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass

def _moonraker_conf() -> Path:
    pd = os.environ.get("WO_PRINTER_DATA")
    base = Path(pd) if pd else Path.home() / "printer_data"
    return base / "config" / "moonraker.conf"


def _um_section(component_id: str) -> str:
    """段名取自 manifest（section 可能与组件 id 不同，如 mainsail -> Woloong-mainsail）。"""
    mf = Path(os.environ.get("WO_ROOT", "/opt/woloong")) / "manifest" / "stack.json"
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
        spec = (data.get("components") or {}).get(component_id) or {}
        return ((spec.get("update_manager") or {}).get("section")) or component_id
    except Exception:
        return component_id


def _strip_um(text: str, section: str) -> str:
    lines = text.splitlines(True)
    out: List[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "[update_manager %s]" % section:
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("["):
                j += 1
            if out and out[-1].lstrip().startswith("# >>> woloong 管理的更新项"):
                out.pop()
            if j < len(lines) and lines[j].strip() == "# <<< woloong 管理结束":
                j += 1
            i = j
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def _remove_um_section(component_id: str, tx: Transaction) -> None:
    """★ OI-009：卸载后必须删掉 [update_manager X] 段，否则留下指向不存在目录的段 ✗"""
    cf = _moonraker_conf()
    if not cf.exists():
        return
    text = cf.read_text(encoding="utf-8")
    new = text
    for sec in {_um_section(component_id), component_id}:
        new = _strip_um(new, sec)
    if new != text:
        tx.modify(cf)
        cf.write_text(new, encoding="utf-8")



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
    _reload_moonraker()
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
        _remove_um_section(component_id, tx)
    except Exception:
        tx.rollback()
        raise
    tx.commit()
    data = _load_installed()
    data.pop(component_id, None)
    _save_installed(data)
    _remove_um_section_done = True
    _reload_moonraker()


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
