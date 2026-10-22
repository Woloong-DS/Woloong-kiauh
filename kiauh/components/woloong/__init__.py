# Woloong 组件安装/卸载实现（方案 A：仓库自闭环 ✓）
from .catalog import (  # noqa: F401
    TIER_LABEL,
    TIER_ORDER,
    CatalogError,
    load,
    spec,
    tiers,
    validate,
)
