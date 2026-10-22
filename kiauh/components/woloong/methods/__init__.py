# install_method -> 服务类注册表（方案 A）
#
# 已实现：git_extras（样板 ✓）
# 未实现：其余方法抛 NotImplemented 明确报错 ✗（不许静默跳过 ✗）
from __future__ import annotations

from typing import Dict, Type

from .base import ComponentError, ComponentService, Transaction, expand, run
from .git_extras import GitExtrasService

SUPPORTED: Dict[str, Type[ComponentService]] = {
    "git_extras": GitExtrasService,
}

PLANNED = [
    "git_service",
    "web_static",
    "config_pack",
    "script_install",
    "pip_install",
    "docs_pack",
    "image_level",
]


def make(spec: dict) -> ComponentService:
    m = spec.get("method")
    cls = SUPPORTED.get(m)
    if cls is None:
        raise ComponentError(
            "%s: install_method=%s 尚未实现（方案 A 迁移中；已实现：%s）"
            % (spec.get("id"), m, ", ".join(sorted(SUPPORTED)))
        )
    return cls(spec)
