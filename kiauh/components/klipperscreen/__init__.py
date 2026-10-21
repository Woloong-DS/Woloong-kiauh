# ======================================================================= #
#  Copyright (C) 2020 - 2026 Dominik Willner <dev.dw-0@proton.me>         #
#                                                                         #
#  This file is part of KIAUH - Klipper Installation And Update Helper    #
#  https://github.com/dw-0/kiauh                                          #
#                                                                         #
#  This file may be distributed under the terms of the GNU GPLv3 license  #
# ======================================================================= #

from pathlib import Path

from core.constants import SYSTEMD

# repo
KLIPPERSCREEN_REPO = "https://github.com/Woloong-DS/Woloong-klipperScreen.git"  # Woloong 去重：指向自有 fork ✓（上游 KlipperScreen ✗）

# ★★ P45 互斥保护（WOLOONG_EXCLUSIVE_GUARD）✓
#   Woloong-klipperScreen 与 KlipperScreen **功能一致**（仅多定制数据）→ 同时存在无意义 ✗
#   若已装 Woloong-klipperScreen → 拒绝装上游 KlipperScreen ✓
def woloong_exclusive_guard(product: str, our_dir: str) -> bool:
    """返回 True = 可以继续；False = 应中止安装。"""
    from pathlib import Path
    from core.logger import Logger
    p = Path(our_dir).expanduser()
    if p.exists():
        Logger.print_error(
            f"已安装 {product}（{our_dir}）—— 它与上游 KlipperScreen 功能一致，仅多 Woloong 定制数据。",
        )
        Logger.print_error("同时安装两个没有意义。请先卸载 " + product + " 再安装上游版本。")
        return False
    return True  # ★ 必须是**上游** ✓
#   Woloong-klipperScreen 是**另一个软件** ✓（= KlipperScreen + Woloong 定制，自有仓库 ✓）
#   由 Woloong 预置包 / woloong-base-install 安装 ✓ —— 绝不能塞进上游软件的安装入口 ✗
#   2026-10-19 用户纠正：「不同的名称就是不同的软件」✓

# names
KLIPPERSCREEN_SERVICE_NAME = "KlipperScreen.service"
KLIPPERSCREEN_UPDATER_SECTION_NAME = "update_manager KlipperScreen"
KLIPPERSCREEN_LOG_NAME = "KlipperScreen.log"

# directories
KLIPPERSCREEN_DIR = Path.home().joinpath("woloong-klipperScreen")  # Woloong 去重：产品目录 ✓（上游 KlipperScreen ✗ 不得并存）
KLIPPERSCREEN_ENV_DIR = Path.home().joinpath(".KlipperScreen-env")

# files
KLIPPERSCREEN_REQ_FILE = KLIPPERSCREEN_DIR.joinpath(
    "scripts/KlipperScreen-requirements.txt"
)
KLIPPERSCREEN_INSTALL_SCRIPT = KLIPPERSCREEN_DIR.joinpath(
    "scripts/KlipperScreen-install.sh"
)
KLIPPERSCREEN_SERVICE_FILE = SYSTEMD.joinpath(KLIPPERSCREEN_SERVICE_NAME)
