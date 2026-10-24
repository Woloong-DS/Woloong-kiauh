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
    n_blk = sum(1 for v in caps.values() if v == "blocked")
    print("\n[分类] native=%d  delegate=%d  blocked=%d  unsupported=%d" % (n_native, n_del, n_blk, n_uns))
    ok("27 个组件全部归类（无遗漏 ✓）") if n_native + n_del + n_blk + n_uns == len(comps) else bad("有组件未归类")

    blocked = sorted(c for c, v in caps.items() if v == "blocked")
    for cid in blocked:
        if comps[cid].get("blocked_reason"):
            ok("%s: blocked 且已登记理由 ✓（%s）" % (cid, comps[cid]["blocked_reason"][:40]))
        else:
            bad("%s: blocked 但无理由 ✗" % cid)

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

    # ---- pip_install：假 pip 记录调用（不联网 ✓）----
    print("\n[pip_install：pip 调用参数正确性]")
    pitmp = Path(tempfile.mkdtemp(prefix="woloong-pip-"))
    phome = pitmp / "h"
    venv = phome / "klippy-env"
    (venv / "bin").mkdir(parents=True)
    log = pitmp / "pip.log"
    fake = venv / "bin" / "pip"
    fake.write_text(
        "#!/usr/bin/env python3\nimport sys, pathlib\n"
        "+pathlib.Path(r'" + str(log) + "').open('a').write(' '.join(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    import components.woloong.methods.pip_install as pi

    pi.HOME = phome
    pips = [c for c, v in caps.items() if comps[c].get("method") == "pip_install"]
    if os.name != "posix":
        ok("pip_install：非 POSIX 平台跳过执行 ✓（shebang 无法在 Windows 执行 ✗）") if pips else None
    for cid in ([] if os.name != "posix" else pips):
        s2 = dict(comps[cid])
        s2["venv"] = str(venv)
        svc2 = make(s2)
        import components.woloong.methods.base as base

        tx3 = base.Transaction("gate-pip-i-" + cid)
        try:
            svc2.install(tx3)
            tx3.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: pip install 失败 %s" % (cid, exc))
            continue
        calls = log.read_text(encoding="utf-8") if log.exists() else ""
        want = comps[cid].get("package_primary") or ""
        if "install" in calls and want and want in calls:
            ok("%s: pip install ✓（主包=%s）" % (cid, want))
        else:
            bad("%s: pip 调用异常（%s）" % (cid, calls[:120]))
        tx4 = base.Transaction("gate-pip-r-" + cid)
        try:
            svc2.remove(tx4)
            tx4.commit()
            ok("%s: pip uninstall ✓" % cid)
        except Exception as exc:  # noqa: BLE001
            bad("%s: pip uninstall 失败 %s" % (cid, exc))
    shutil.rmtree(pitmp, ignore_errors=True)

    # ---- web_static：离线目录部署（不联网 ✓）----
    print("\n[web_static：离线目录部署 + nginx 片段]")
    wtmp = Path(tempfile.mkdtemp(prefix="woloong-web-"))
    whome = wtmp / "h"
    wcache = wtmp / "cache"
    wnginx = wtmp / "nginx"
    wnginx.mkdir(parents=True)
    os.environ["WO_CACHE_FILES"] = str(wcache)
    os.environ["WO_NGINX_DIR"] = str(wnginx)
    import components.woloong.methods.base as base

    import components.woloong.methods.web_static as ws

    ws.HOME = whome
    for cid in sorted(c for c, v in caps.items() if v == "native" and comps[c].get("method") == "web_static"):
        src = wcache / cid
        src.mkdir(parents=True, exist_ok=True)
        (src / "index.html").write_text("<title>%s</title>" % cid, encoding="utf-8")
        s3 = dict(comps[cid])
        s3["target_path"] = str(wtmp / ("site-" + cid))
        svc3 = make(s3)
        txi = base.Transaction("gate-web-i-" + cid)
        try:
            svc3.install(txi)
            txi.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: web install 失败 %s" % (cid, exc))
            continue
        idx = Path(s3["target_path"]) / "index.html"
        if idx.exists():
            ok("%s: 部署 ✓（index.html 就位）" % cid)
        else:
            bad("%s: 部署后无 index.html" % cid)
        wp = comps[cid].get("web_path") or ""
        snip = wnginx / (cid + ".conf")
        if wp in ("", "/"):
            ok("%s: 根站不写片段 ✓（避免重复 server）" % cid) if not snip.exists() else bad("%s: 根站不该写片段" % cid)
        else:
            ok("%s: 已写 location 片段 ✓" % cid) if snip.exists() else bad("%s: 缺 location 片段" % cid)
        txr = base.Transaction("gate-web-r-" + cid)
        try:
            svc3.remove(txr)
            txr.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: web remove 失败 %s" % (cid, exc))
            continue
        if (not Path(s3["target_path"]).exists()) and (not snip.exists()):
            ok("%s: web remove ✓（站点与片段均清理）" % cid)
        else:
            bad("%s: web remove 有残留" % cid)
    shutil.rmtree(wtmp, ignore_errors=True)

    # ---- docs_pack：离线仓库拷贝（不联网 ✓）----
    print("\n[docs_pack：拷贝 + 完全复原]")
    dtmp = Path(tempfile.mkdtemp(prefix="woloong-docs-"))
    dhome = dtmp / "h"
    dhome.mkdir(parents=True)
    import components.woloong.methods.base as base

    import components.woloong.methods.docs_pack as dp

    dp.HOME = dhome
    drepo = dtmp / "up-docs"
    git_init(drepo, {"docs/a.md": "# a\n", "README.md": "r\n"})
    for cid in sorted(c for c, v in caps.items() if comps[c].get("method") == "docs_pack"):
        s4 = dict(comps[cid])
        s4["repo"] = "file://" + str(drepo)
        s4["target_path"] = str(dtmp / ("docs-" + cid))
        svc4 = make(s4)
        txi2 = base.Transaction("gate-docs-i-" + cid)
        try:
            svc4.install(txi2)
            txi2.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: docs install 失败 %s" % (cid, exc))
            continue
        tgt = Path(s4["target_path"])
        if (tgt / "docs" / "a.md").exists():
            ok("%s: docs 部署 ✓" % cid)
        else:
            bad("%s: docs 部署后缺文件" % cid)
        txr2 = base.Transaction("gate-docs-r-" + cid)
        try:
            svc4.remove(txr2)
            txr2.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: docs remove 失败 %s" % (cid, exc))
            continue
        if not tgt.exists() and not (dhome / (".woloong-src-" + cid)).exists():
            ok("%s: docs remove ✓（目标与暂存均清理）" % cid)
        else:
            bad("%s: docs remove 有残留" % cid)
    shutil.rmtree(dtmp, ignore_errors=True)

    # ---- script_install / 带服务的 git_service：克隆 + 单元（不建 venv ✓）----
    print("\n[app_service：克隆 + 单元文件 + 完全复原]")
    atmp = Path(tempfile.mkdtemp(prefix="woloong-app-"))
    ahome = atmp / "h"
    ahome.mkdir(parents=True)
    aunits = atmp / "units"
    aunits.mkdir(parents=True)
    os.environ["WO_SYSTEMD_DIR"] = str(aunits)
    os.environ["WO_SKIP_VENV"] = "1"
    import components.woloong.methods.base as base

    import components.woloong.methods.app_service as ap

    ap.HOME = ahome
    arepo = atmp / "up-app"
    git_init(arepo, {"main.py": "print(1)\n", "README.md": "r\n"})
    appids = sorted(
        c for c, v in caps.items()
        if caps[c] == "native"
        and (
            comps[c].get("method") == "script_install"
            or (comps[c].get("method") == "git_service" and comps[c].get("service"))
        )
    )
    for cid in appids:
        s5 = dict(comps[cid])
        s5["repo"] = "file://" + str(arepo)
        s5["target_path"] = str(atmp / ("app-" + cid))
        s5["items"] = [{"src": ".", "dest": ".", "exclude": [".git"]}]
        s5.pop("venv", None)
        svc5 = ap.AppService(s5)
        txi3 = base.Transaction("gate-app-i-" + cid)
        try:
            svc5.install(txi3)
            txi3.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: app install 失败 %s" % (cid, exc))
            continue
        tgt = Path(s5["target_path"])
        if (tgt / "main.py").exists():
            ok("%s: 部署 ✓" % cid)
        else:
            bad("%s: 部署后缺文件" % cid)
        svc_name = s5.get("service")
        if svc_name:
            u = aunits / (svc_name + ".service")
            ok("%s: 单元已生成 ✓（%s）" % (cid, u.name)) if u.exists() else bad("%s: 缺单元文件" % cid)
        txr3 = base.Transaction("gate-app-r-" + cid)
        try:
            svc5.remove(txr3)
            txr3.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: app remove 失败 %s" % (cid, exc))
            continue
        left = tgt.exists() or (ahome / (".woloong-src-" + cid)).exists()
        unit_left = bool(svc_name) and (aunits / (svc_name + ".service")).exists()
        ok("%s: app remove ✓（目标/暂存/单元均清理）" % cid) if not left and not unit_left else bad("%s: app remove 有残留" % cid)
    shutil.rmtree(atmp, ignore_errors=True)

    # ---- native：假 HOME 真装真卸 ----
    print("\n[native：装 → 卸 → 复原]")
    tmp = Path(tempfile.mkdtemp(prefix="woloong-gate-"))
    home = tmp / "home"
    (home / "klipper" / "klippy" / "extras").mkdir(parents=True)
    cfgdir = home / "printer_data" / "config"
    cfgdir.mkdir(parents=True)
    baseline = "[mcu]\nserial: /dev/ttyS0\n"
    (cfgdir / "printer.cfg").write_text(baseline, encoding="utf-8")

    natives = sorted(
        c for c, v in caps.items()
        if v == "native"
        and comps[c].get("method") not in ("pip_install", "web_static", "docs_pack", "script_install")
        and comps[c].get("service") is None
    )
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
        # 每个组件一个**独立的**源码目录（git_extras 软链到它 ✓，remove 时删掉 ✓）
        src = tmp / ("src-" + cid)
        if not src.exists():
            shutil.copytree(repo, src)
        spec["repo"] = "file://" + str(src)
        spec["src_dir"] = str(src)
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
        if spec["method"] == "git_service":
            deployed = bool(st.get("git"))
        else:
            deployed = bool(st.get("deployed"))
        ok("%s: install ✓" % cid) if deployed else bad("%s: install 后未落位" % cid)

        tx2 = base.Transaction("gate-r-" + cid)
        try:
            svc.remove(tx2)
            tx2.commit()
        except Exception as exc:  # noqa: BLE001
            bad("%s: remove 失败 %s" % (cid, exc))
            continue
        left = [p for p in (st.get("files") or []) if Path(p).exists()]
        src_gone = not Path(spec.get("src_dir") or (home / (".woloong-src-" + cid))).exists()
        gone = not Path(spec["target_path"]).exists() and src_gone
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
