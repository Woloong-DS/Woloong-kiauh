# install_method -> 服务类注册表（方案 A，逐步迁移 ✓）
#
#  已实现：
#    git_extras   —— 直接实现（拷模块进 klippy/extras ✓）
#    git_service  —— 分流：上游有实现 -> delegate ✓；纯 clone -> GitService ✓
#  未实现（必须显式登记在 MIGRATING 白名单 ✗）：
#    web_static / config_pack / script_install / pip_install / docs_pack / image_level
from __future__ import annotations

from typing import Dict, Type

from .base import ComponentError, ComponentService, Transaction, expand, rmtree, run
from .delegate import DELEGATES, DelegateService, is_delegated
from .git_extras import GitExtrasService
from .git_service import GitService

SUPPORTED: Dict[str, Type[ComponentService]] = {
    "git_extras": GitExtrasService,
    "git_service": GitService,
}

PLANNED = [
    "web_static",
    "config_pack",
    "script_install",
    "pip_install",
    "docs_pack",
    "image_level",
]


def make(spec: dict) -> ComponentService:
    cid = spec.get("id")
    m = spec.get("method")
    # ① 上游已有实现 -> 委托 ✓（klipper/moonraker/klipperscreen/crowsnest）
    if is_delegated(cid):
        return DelegateService(spec)
    # ② spoolman 等「需 systemd 单元」的 git_service 暂不支持 ✗
    if m == "git_service" and spec.get("service") and not is_delegated(cid):
        raise ComponentError(
            "%s: 需要 venv/systemd 单元（尚未迁移；已实现：%s）" % (cid, ", ".join(sorted(SUPPORTED)))
        )
    cls = SUPPORTED.get(m)
    if cls is None:
        raise ComponentError(
            "%s: install_method=%s 尚未实现（已实现：%s）" % (cid, m, ", ".join(sorted(SUPPORTED)))
        )
    return cls(spec)


def capability(component_id: str) -> str:
    """返回能力标签：delegate / native / unsupported（供门禁与 UI 展示 ✓）。"""
    if is_delegated(component_id):
        return "delegate"
    from .. import catalog   # 上级包（components.woloong）✓

    spec = catalog.spec(component_id)
    m = spec.get("method")
    if m == "git_service" and spec.get("service"):
        return "unsupported"
    return "native" if m in SUPPORTED else "unsupported"
