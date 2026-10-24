<p align="center">
  <img src="docs/assets/Woloong_Logo.png" alt="Woloong" height="88">
</p>

<h1 align="center">Woloong-KIAUH</h1>

<p align="center">
  <b>Woloong-OS 的设备端控制面</b><br>
  清单驱动的安装 / 卸载 / 更新 / 状态 / 体检 · 离线优先 · 事务回滚
</p>

<p align="center">
  <a href="https://github.com/Woloong-DS/Woloong-OS">Woloong-OS</a> ·
  <a href="https://github.com/dw-0/kiauh">上游 KIAUH</a>
</p>

---

## 这是什么

本仓库是 [KIAUH](https://github.com/dw-0/kiauh) 的 **Woloong 发行树**，但它不只是另一个 KIAUH 安装器：

> **Woloong-OS 运行时里，Klipper 软件栈唯一的“状态与动作”控制台。**

它不拥有物料、不做镜像构建、也不给自己做更新；它读 Woloong-OS 的清单，执行安装/卸载/更新/体检，并把结果写进本机台账。

| 项目 | 说明 |
| --- | --- |
| 上游 | `dw-0/kiauh`（GPL-3.0，版权归上游作者），当前基线 v6.3.2 |
| 清单真源 | `Woloong-OS/manifest/stack.json`（21 个组件） |
| 组件目录 | `kiauh/components/woloong/data/components.json`（生成物，禁止手改） |
| 运行位置 | 镜像内 `~/woloong-kiauh`，Python 3.8+ |
| 不负责 | 镜像构建、物料发布、自身在线升级 |

---

## 与上游 KIAUH 的关系

| 维度 | 上游 KIAUH | 本仓库 |
| --- | --- | --- |
| 清单 | 写死在代码里的菜单项 | **目录驱动**：21 个组件由 `stack.json` 生成 |
| 安装来源 | 在线 git clone / pip | **离线优先**：bundle / wheelhouse / 本地 apt 源 |
| 事务 | 无 | 每次安装/卸载一个事务，失败**整单回滚**（含配置与台账） |
| 台账 | 无 | `installed.json` 单一真源（安装器与 TUI 共用） |
| 更新策略 | 自身 `git pull` | **无自更新**：随镜像 OTA，由清单 pin 住 |
| 入口 | 上游固定项 | 保留 4 个内置入口 + **W) 预置包 / 组件管理**覆盖全部 21 项 |

本仓库不向上游提交 PR；上游有变化时由自有发行树吸收。

---

## 菜单与入口

| 入口 | 内容 |
| --- | --- |
| **主菜单** | 0 日志上传 · 1 安装 · 2 更新 · 3 卸载 · 4 高级 · 5 备份 · S 设置 · E 扩展 |
| **安装菜单** | 1 Klipper · 2 Moonraker · 3 Mainsail-Config · 4 Crowsnest · **W) Woloong 预置包** |
| **卸载菜单** | 1 Klipper · 2 Moonraker · 3 Crowsnest · 4 Mainsail-Config · **W) 组件管理** |
| **更新菜单** | Klipper / Moonraker / Mainsail / Mainsail-Config / KlipperScreen / Crowsnest / System |
| **W) 预置包** | 四档批量安装 + 单组件修复 + 组件管理（装/卸/更新/状态） |

### CLI（内置组件）

```bash
bash kiauh.sh                      # 交互式 TUI（推荐）
bash kiauh.sh install klipper      # 内置组件安装
bash kiauh.sh remove crowsnest     # 内置组件卸载
bash kiauh.sh update klipper       # 内置组件更新
```

> Woloong 清单里的 21 项统一走 **W) → 组件管理**；CLI 只保留上游兼容的内置组件命令。

---

## 核心机制

| 机制 | 说明 |
| --- | --- |
| **目录驱动** | `stack.json` + `payload-map.json` → `gen_catalog.py` → `components.json`；门禁重新生成并比对，漂移即失败 |
| **离线安装** | git 组件从 `cache/sources/*.git.bundle` 克隆（含 tag）；Python 依赖从 `wheelhouse`；系统包来自本地 apt 源 |
| **事务回滚** | 写文件/改配置/建目录/写台账都登记；失败逆序还原（含 `moonraker.conf` 与 `printer.cfg`） |
| **台账单源** | `/opt/woloong/state/installed.json`，安装器与 TUI 共用；属主固定 pi |
| **更新管理器** | 安装时登记 `[update_manager X]`，卸载时删除该段；KIAUH 自身不登记 |
| **pin 策略** | 有 pin 的组件装完即 pin，页面显示与清单一致 |
| **体检** | `woloong-doctor`（L0–L3）与接线校验（P24）在安装后当场执行 |

---

## 目录结构

```
kiauh/
├── core/menus/                主菜单、安装/卸载/更新、W) 预置包、组件管理
├── components/woloong/        清单读取、组件服务、安装方法、事务、目录生成器
│   ├── data/components.json   生成物（禁止手改）
│   ├── methods/               git_service / git_extras / script_install / pip_install / web_static 等
│   └── tools/gen_catalog.py   从 Woloong-OS 清单生成目录
├── components/<upstream>/     上游内置组件（klipper / moonraker / crowsnest 等）
└── utils/                     文件、git、输入、日志等工具
tests/                         目录完整性、装/卸闭环、菜单布局
```

---

## 开发与测试

```bash
# 单元测试（菜单 / CLI / 组件服务）
python -m pytest -q kiauh

# 目录完整性（需 Woloong-OS 的清单与载荷映射）
WO_STACK=../Woloong-OS/manifest/stack.json \
WO_PAYLOAD=../Woloong-OS/pack/payload-map.json \
python tests/test-catalog-integrity.py

# 装 → 卸 → 完全复原（沙箱）
python tests/test-woloong-catalog.py
```

门禁要求：目录完整性全绿、装/卸闭环全绿、菜单行宽 ≤57、安装与卸载入口对称。

---

## 版本与发布

- **不单独发版**：以 git 提交被 Woloong-OS `manifest/stack.json` 的 `kiauh.pin` 引用；
- **不在 `update_manager` 中**：KIAUH 是执行者，不被自身管理对象更新；
- **无运行期自更新**：随 Woloong-OS 镜像 OTA 更新；
- 上游变化通过自有发行树吸收，不向上游提交 PR。

---

## 许可证

本仓库基于 KIAUH（GPL-3.0）派生，遵循 GPL-3.0；上游版权归 Dominik Willner 及贡献者所有。
Woloong 定制部分（清单、菜单、离线安装、事务、组件服务）同样以 GPL-3.0 发布。

