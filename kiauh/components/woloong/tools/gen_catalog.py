#!/usr/bin/env python3
# ======================================================================= #
#  生成 components.json —— 单一真源：Woloong-OS 的 stack.json + payload-map.json
#
#  背景（整合决议 v1.0）：
#   · 清单只允许有一份真源 = Woloong-OS 的 manifest/stack.json（软件事实）
#   · 打包细节（items/release/sha256）= pack/payload-map.json
#   · 本文件把它们合成 KIAUH 运行期需要的 components.json，**禁止手改产物**
#
#  用法：
#    python3 gen_catalog.py --stack <stack.json> --payload <payload-map.json> [--out components.json]
# ======================================================================= #
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]          # kiauh/components/woloong
DEFAULT_OUT = HERE / "data" / "components.json"

# 依赖级 / 固件级：不参与"软件"分类，但仍出现在清单里供 UI 只读展示
DEPENDENCY_IDS = {"can_stack", "mcu_toolchain"}
FIRMWARE_IDS = {"cartographer_firmware"}
# 自身组件：它由 pack 按 manifest.pin 打包，若在目录里再写自己的 pin，
# 每次“改目录→提交→pin 变旧”会形成自我引用死循环 ✗ → 不产出 pin ✓
SELF_ID = "kiauh"


def origin_of(cid: str, tier: str | None) -> str:
    if cid in DEPENDENCY_IDS:
        return "dependency"
    if cid in FIRMWARE_IDS:
        return "firmware"
    if cid == "kiauh":            # 本工具自身随镜像烘焙
        return "image"
    return "image" if tier == "mono_basic" else ("preinstall" if tier == "mono_advanced" else "optional")


def build(stack: dict, payload: dict) -> dict:
    comps = stack.get("components") or {}
    out = []
    for cid, spec in comps.items():
        method = spec.get("install_method")
        tier = spec.get("tier")
        pay = (payload.get(method) or {}).get(cid) or {}
        if not isinstance(pay, dict):
            pay = {}

        item = {
            "id": cid,
            "name": spec.get("display_name") or cid,
            "method": method,
            "kind": "firmware" if cid in FIRMWARE_IDS else ("dependency" if cid in DEPENDENCY_IDS else "software"),
            "origin": origin_of(cid, tier),
            "tiers": [tier] if tier else [],
            "repo": pay.get("repo") or spec.get("repo"),
            "pin": None if cid == SELF_ID else spec.get("pin"),
            "target_path": spec.get("target_path"),
            "update_channel": spec.get("update_channel") or "none",
            "web_visible": bool((spec.get("update_manager") or {}).get("section")),
        }
        # 运行期需要的可选字段（有则带、无则不写，保持产物最小 ✓）
        # ★ 2026-10-23：不要再把 managed_services 当 service ✗
        #   managed_services = “我依赖/重启的服务”，不等于“我拥有并安装的单元” ✗
        #   反例：afc/klipper_backup/timelapse 因此被当成要生成 klipper/moonraker 单元 ✗
        _svc = spec.get("service")
        if _svc:
            item["service"] = _svc
        for src, dst in (
            ("service", "service"),
            ("venv", "venv"),
            ("python_imports", "python_imports"),
            ("config_file", "config_file"),
            ("config_target", "config_target"),
            ("needs_klipper_replay", "needs_klipper_replay"),
            ("omitted", "omitted"),
            ("omitted_reason", "omitted_reason"),
            ("install_note", "install_note"),
        ):
            if spec.get(src) is not None:
                item[dst] = spec[src]
        for src, dst in (
            ("exec", "exec"),
            ("own_venv", "own_venv"),
            ("packages", "packages"),
            ("package_primary", "package_primary"),
        ):
            if spec.get(src) is not None:
                item[dst] = spec[src]
        for key in ("items", "release", "sha256", "web_path", "bundle"):
            if pay.get(key) is not None:
                item[key] = pay[key]
        # git_extras：源码目录 = ~/<repo 名>（软链目标，必须可见以便跟踪 ✓）
        if method == "git_extras" and item.get("repo"):
            _repo = item["repo"].rstrip("/").split("/")[-1]
            item["src_dir"] = "~/" + (_repo[:-4] if _repo.endswith(".git") else _repo)
        # 上游替换关系（Woloong 版替代同名上游软件）
        if cid in {"mainsail", "klipperscreen", "kiauh"}:
            item["replaces_upstream"] = True
        # web 静态包默认挂根路径
        if method == "web_static" and "web_path" not in item:
            item["web_path"] = "/"
        # 依赖级组件不允许运行期安装
        if cid in DEPENDENCY_IDS:
            item["blocked"] = True
            item["blocked_reason"] = spec.get("blocked_reason") or "镜像级依赖：由镜像构建安装，不进运行期装卸"
        if spec.get("blocked") is not None:
            item["blocked"] = spec["blocked"]
            item["blocked_reason"] = spec.get("blocked_reason")
        out.append(item)

    out.sort(key=lambda c: c["id"])
    return {
        "schema": 2,
        "generated_from": {
            "stack": stack.get("manifest_version"),
            "target": stack.get("target"),
            "note": "由 tools/gen_catalog.py 生成；禁止手改 ✓（真源 = Woloong-OS manifest/stack.json + pack/payload-map.json）",
        },
        "tiers": stack.get("tiers") or {},
        "components": out,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", required=True)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    stack = json.loads(Path(a.stack).read_text(encoding="utf-8"))
    payload = json.loads(Path(a.payload).read_text(encoding="utf-8"))
    data = build(stack, payload)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("生成 %d 个组件 -> %s" % (len(data["components"]), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
