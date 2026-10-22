#!/usr/bin/env python3
# =============================================================================
# test-woloong-catalog.py —— 方案 A：仓库自闭环门禁
#
# 四类断言：
#   1) 目录可读/自洽（27 项，方法/档位/必填字段）
#   2) 能力分类覆盖全 27：native / delegate / unsupported
#      unsupported 必须**逐组件显式登记**（MIGRATING）✗ 不许静默缺 ✗
#   3) native 组件必须**真能装能卸**（假 HOME + 本地 git 仓库，不联网 ✓）
#   4) 卸载后必须**完全复原**（extras 无残留 / printer.cfg 逐字节相同 ✓）
#   5) delegate 组件只验「上游入口存在」✓（不在本门禁内真装 ✗，真装在设备上做）
# =============================================================================
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kiauh"))   # KIAUH 的包根是 kiauh/ ✓

# 尚未迁移能力：**逐组件**登记（迁移完就删掉，门禁自动变严 ✓）
MIGRATING = {
    "spoolman": "git_service + venv + systemd 单元（下一阶段）",
    "mainsail": "web_static（release 资产 + nginx location）",
    "fluidd": "web_static",
    "mainsail_afc": "web_static",
    "mainsail-config": "config_pack（但上游已有 config 服务 ✓ 可改委托）",
    "KAMP": "config_pack",
    "klipper_backup": "script_install",
    "cartographer_firmware": "script_install",
    "telegram_bot": "script_install",
    "kiauh": "script_install（kiauh 自身重装/自更新）",
    "timelapse": "script_install",
    "afc": "script_install",
    "afc_klipperscreen": "script_install",
    "cartographer_plugin": "pip_install",
    "at_docs": "docs_pack",
    "can_stack": "image_level（镜像级，运行期不可装 ✓）",
    "mcu_toolchain": "image_level（镜像级 ✓）",
}

P = 0
F = 0


def ok(msg: str) -> None:
    global P
    P += 1
    print("  [PASS] " + msg)


def bad(msg: str) -> None:
    global F
    F += 1
    print("  [FAIL] " + msg)


def git_init(repo: Path, files: dict) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=g@g", "-c", "user.name=g", "commit", "-qm", "i"], check=True)


def main() -> int:
    from components.woloong import catalog, service
    from components.woloong.methods import capability, make

    print("=" * 78)
    print("Woloong 组件目录 / 装-卸闭环门禁（方案 A）")
    print("=" * 78)

    comps = catalog.load()
    ok("目录可读：%d 个组件" % len(comps))
    errs = service.check_catalog()
    ok("目录自洽") if not errs else bad("目录错误：%s" % errs[:3])

    # ---- 分类 ----
    caps = {cid: capability(cid) for cid in comps}
    n_native = sum(1 for v in caps.values() if v == "native")
    n_del = sum(1 for v in caps.values() if v == "delegate")
    n_uns = sum(1 for v in caps.values() if v == "unsupported")
    print("\n[分类] native=%d  delegate=%d  unsupported=%d" % (n_native, n_del, n_uns))
    ok("27 个组件全部归类（无遗漏 ✓）") if n_native + n_del + n_uns == len(comps) else bad("有组件未归类")

    miss = sorted(c for c, v in caps.items() if v == "unsupported" and c not in MIGRATING)
    if miss:
        bad("未实现且未登记：%s" % ", ".join(miss))
    else:
        ok("所有未实现组件都已逐条登记（%d 个）" % n_uns)
    stale = sorted(c for c in MIGRATING if caps.get(c) != "unsupported")
    if stale:
        bad("登记已过期（现已实现，请从 MIGRATING 删除）：%s" % ", ".join(stale))
    else:
        ok("MIGRATING 无过期条目 ✓")

    # ---- delegate：只验上游入口存在 ----
    print("\n[delegate：上游入口存在性]")
    from components.woloong.methods.delegate import DELEGATES

    for cid in sorted(c for c, v in caps.items() if v == "delegate"):
        t = DELEGATES.get(cid) or {}
        have = [a for a in ("install", "remove", "update") if t.get(a)]
        if len(have) == 3:
            ok("%s: 委托上游 install/remove/update ✓" % cid)
        else:
            bad("%s: 委托不全（%s）" % (cid, have))

    # ---- native：假 HOME 真装真卸 ----
    print("\n[native：装 → 卸 → 复原]")
    tmp = Path(tempfile.mkdtemp(prefix="woloong-gate-"))
    home = tmp / "home"
    (home / "klipper" / "klippy" / "extras").mkdir(parents=True)
    cfgdir = home / "printer_data" / "config"
    cfgdir.mkdir(parents=True)
    baseline = "[mcu]\nserial: /dev/ttyS0\n"
    (cfgdir / "printer.cfg").write_text(baseline, encoding="utf-8")

    natives = sorted(c for c, v in caps.items() if v == "native")
    files = {}
    for cid in natives:
        for it in comps[cid].get("items") or []:
            files[it["src"]] = "X = 1\n"
    files.setdefault("README.md", "x\n")
    repo = tmp / "up"
    git_init(repo, files)

    os.environ["WO_HOME"] = str(home)
    os.environ["WO_STATE_DIR"] = str(tmp / "state")
    import components.woloong.methods.base as base

    base.HOME = home
    import components.woloong.methods.git_extras as ge

    ge.HOME = home
    import components.woloong.methods.git_service as gs

    gs.HOME = home

    for cid in natives:
        spec = dict(comps[cid])
        spec["repo"] = str(repo)
        spec["target_path"] = str(tmp / ("clone-" + cid))
        svc = make(spec)
        tx = base.Transaction("gate-i-" + cid)
        try:
            svc.install(tx)
            tx.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: install 失败 %s" % (cid, exc))
            continue
        st = svc.status()
        if spec["method"] == "git_extras":
            deployed = bool(st.get("deployed"))
        else:
            deployed = bool(st.get("git"))
        ok("%s: install ✓" % cid) if deployed else bad("%s: install 后未落位" % cid)

        tx2 = base.Transaction("gate-r-" + cid)
        try:
            svc.remove(tx2)
            tx2.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: remove 失败 %s" % (cid, exc))
            continue
        left = [p for p in (st.get("files") or []) if Path(p).exists()]
        gone = not Path(spec["target_path"]).exists()
        pc = (cfgdir / "printer.cfg").read_text(encoding="utf-8")
        if not left and gone and pc == baseline:
            ok("%s: remove ✓（无残留 + 配置复原）" % cid)
        else:
            bad("%s: remove 后不一致（left=%s gone=%s pc_ok=%s）" % (cid, left, gone, pc == baseline))

    shutil.rmtree(tmp, ignore_errors=True)
    print("=" * 78)
    print("汇总：PASS=%d FAIL=%d" % (P, F))
    print("WOLOONG_CATALOG_OK ✓" if F == 0 else "WOLOONG_CATALOG_FAILED ✗")
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
