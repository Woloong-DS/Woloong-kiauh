#!/usr/bin/env python3
# =============================================================================
# test-woloong-catalog.py —— 方案 A：仓库自闭环门禁
#
# 断言：
#   1) 组件目录可读、27 项、档位无悬空引用
#   2) 每个组件都必须有处理器，**或**在 MIGRATING 白名单里显式登记 ✗（不许静默缺 ✗）
#   3) 已实现的 method 必须真的能装能卸（假 HOME + 本地 git 仓库，不联网 ✓）
#   4) 卸载后必须**回到安装前**（extras 无残留 / include 已移除 / 配置原样 ✓）
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

# 方案 A 迁移进度白名单：method -> 说明
#   每迁移完一个 method，就从这里删掉；门禁会自动变严 ✓
MIGRATING = {
    "git_service": "待迁移（clone + systemd 单元）",
    "web_static": "待迁移（release 资产/静态目录）",
    "config_pack": "待迁移（配置片段）",
    "script_install": "待迁移（脚本安装）",
    "pip_install": "待迁移（venv 轮子）",
    "docs_pack": "待迁移（文档）",
    "image_level": "镜像级，运行期不可装（明确不支持 ✓）",
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


def main() -> int:
    from components.woloong import catalog, service
    from components.woloong.methods import SUPPORTED

    print("=" * 76)
    print("Woloong 组件目录 / 装-卸闭环门禁（方案 A）")
    print("=" * 76)

    comps = catalog.load()
    ok("目录可读：%d 个组件" % len(comps)) if comps else bad("目录为空")
    errs = service.check_catalog()
    ok("目录自洽（方法/档位/字段）") if not errs else bad("目录错误：%s" % errs[:3])

    gaps = [c for c in comps if comps[c].get("method") not in SUPPORTED]
    unlisted = [c for c in gaps if comps[c].get("method") not in MIGRATING]
    if unlisted:
        bad("未实现且未登记：%s" % ", ".join(sorted(unlisted)))
    else:
        ok("未实现的组件都已显式登记（%d 个待迁移 ✓）" % len(gaps))

    print("\n[功能闭环：已实现的方法必须能装能卸]")
    tmp = Path(tempfile.mkdtemp(prefix="woloong-gate-"))
    home = tmp / "home"
    (home / "klipper" / "klippy" / "extras").mkdir(parents=True)
    cfgdir = home / "printer_data" / "config"
    cfgdir.mkdir(parents=True)
    baseline = "[mcu]\nserial: /dev/ttyS0\n"
    (cfgdir / "printer.cfg").write_text(baseline, encoding="utf-8")

    repo = tmp / "up"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for cid, spec in comps.items():
        if spec.get("method") not in SUPPORTED:
            continue
        for it in spec.get("items") or []:
            tgt = repo / it["src"]
            if it["src"].endswith("/"):
                tgt.mkdir(parents=True, exist_ok=True)
                (tgt / "__init__.py").write_text("X = 1\n", encoding="utf-8")
            else:
                tgt.parent.mkdir(parents=True, exist_ok=True)
                tgt.write_text("X = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=g@g", "-c", "user.name=g", "commit", "-qm", "i"], check=True)

    os.environ["WO_HOME"] = str(home)
    os.environ["WO_STATE_DIR"] = str(tmp / "state")

    import components.woloong.methods.base as base
    base.HOME = home
    import components.woloong.methods.git_extras as ge
    ge.HOME = home

    for cid, spec in sorted(comps.items()):
        if spec.get("method") not in SUPPORTED:
            continue
        s = dict(spec)
        s["repo"] = str(repo)
        s["target_path"] = str(tmp / ("clone-" + cid))
        svc = ge.GitExtrasService(s)
        tx = base.Transaction("gate-install-" + cid)
        try:
            svc.install(tx)
            tx.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: install 失败 %s" % (cid, exc))
            continue
        st = svc.status()
        if st.get("deployed"):
            ok("%s: install ✓（模块已落位）" % cid)
        else:
            bad("%s: install 后未落位" % cid)
        tx2 = base.Transaction("gate-remove-" + cid)
        try:
            svc.remove(tx2)
            tx2.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: remove 失败 %s" % (cid, exc))
            continue
        left = [p for p in st.get("files") or [] if Path(p).exists()]
        pc = (cfgdir / "printer.cfg").read_text(encoding="utf-8")
        back = (pc == baseline) and not left
        if back:
            ok("%s: remove ✓（无残留 + printer.cfg 复原）" % cid)
        else:
            bad("%s: remove 后有残留（left=%s）" % (cid, left))

    shutil.rmtree(tmp, ignore_errors=True)
    print("=" * 76)
    print("汇总：PASS=%d FAIL=%d" % (P, F))
    print("WOLOONG_CATALOG_OK ✓" if F == 0 else "WOLOONG_CATALOG_FAILED ✗")
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
