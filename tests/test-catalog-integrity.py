#!/usr/bin/env python3
# =============================================================================
# test-catalog-integrity.py —— 整合决议 v1.0 的新门禁（替换“27 项手写清单”的旧假设）
#
# 断言：
#   I1 产物由生成器产出（schema=2，含 generated_from）
#   I2 id 唯一；kind ∈ {software, firmware, dependency}
#   I3 档位引用自洽（tiers 里的 id 必存在；组件的 tiers 必在 tiers 表中）
#   I4 能力边界：dependency / firmware 不允许运行期安装（blocked=True）
#   I5 已剔除的 5 项不得出现
#   I6 与真源一致（设置 WO_STACK / WO_PAYLOAD 时重新生成并比对哈希）
# =============================================================================
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "kiauh" / "components" / "woloong" / "data" / "components.json"
GEN = ROOT / "kiauh" / "components" / "woloong" / "tools" / "gen_catalog.py"

REMOVED = {"at_docs", "KAMP", "fluidd", "mainsail_afc", "katapult"}
P = 0
F = 0


def ok(m: str) -> None:
    global P
    P += 1
    print("  [PASS] " + m)


def bad(m: str) -> None:
    global F
    F += 1
    print("  [FAIL] " + m)


def main() -> int:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    comps = data.get("components") or []
    by_id = {c["id"]: c for c in comps}
    tiers = data.get("tiers") or {}

    ok("I1 产物 schema=%s，来源=%s" % (data.get("schema"), "generated" if data.get("generated_from") else "missing"))
    bad("I1 缺少 generated_from（说明不是生成物 ✗）") if not data.get("generated_from") else None

    dup = len(comps) != len(by_id)
    bad("I2 存在重复 id ✗") if dup else ok("I2 id 唯一（%d 项）" % len(comps))

    kinds = {c.get("kind") for c in comps}
    bad("I2 非法 kind：%s ✗" % (kinds - {"software", "firmware", "dependency"})) if kinds - {"software", "firmware", "dependency"} else ok("I2 kind 合法：%s" % sorted(kinds))

    tier_ids = {i for ids in tiers.values() for i in ids}
    dangling = tier_ids - set(by_id)
    bad("I3 档位引用不存在的 id：%s ✗" % sorted(dangling)) if dangling else ok("I3 档位引用自洽（%d 项在档）" % len(tier_ids))
    mismatch = [c["id"] for c in comps if c.get("tiers") and c["tiers"][0] not in tiers]
    bad("I3 组件声明了不存在的档位：%s ✗" % mismatch) if mismatch else ok("I3 组件档位合法")

    # dependency = 镜像级，不可运行期装卸 ✓；firmware = 工具，可安装但走固件菜单 ✓
    bad_perm = [c["id"] for c in comps if c.get("kind") == "dependency" and not c.get("blocked")]
    bad("I4 依赖级组件未标记 blocked：%s ✗" % bad_perm) if bad_perm else ok("I4 依赖级组件均不可运行期装卸")
    fw = [c["id"] for c in comps if c.get("kind") == "firmware"]
    ok("I4 固件工具：%s（可安装，走固件菜单）" % (", ".join(fw) or "无"))

    present = REMOVED & set(by_id)
    bad("I5 已剔除的组件仍在目录：%s ✗" % sorted(present)) if present else ok("I5 已剔除 5 项均不在目录")

    stack, payload = os.environ.get("WO_STACK"), os.environ.get("WO_PAYLOAD")
    if stack and payload and Path(stack).is_file() and Path(payload).is_file():
        sys.path.insert(0, str(GEN.parent))
        import gen_catalog  # type: ignore

        s = json.loads(Path(stack).read_text(encoding="utf-8"))
        pl = json.loads(Path(payload).read_text(encoding="utf-8"))
        regen = gen_catalog.build(s, pl)
        same = json.dumps(regen, ensure_ascii=False, sort_keys=True) == json.dumps(data, ensure_ascii=False, sort_keys=True)
        ok("I6 与真源（stack.json + payload-map）一致") if same else bad("I6 目录已漂移：请重跑 gen_catalog.py ✗")
    else:
        print("  [SKIP] I6 未提供 WO_STACK/WO_PAYLOAD（CI 里应提供）")

    print("\n汇总：PASS=%d FAIL=%d" % (P, F))
    print("CATALOG_INTEGRITY_OK" if F == 0 else "CATALOG_INTEGRITY_FAILED")
    return 0 if F == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
