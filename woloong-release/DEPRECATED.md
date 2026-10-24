# woloong-release/ 已退役（DEPRECATED）

**生效日期**：2026-10-22（整合决议 v1.0）

## 为什么退役

本目录原先承载“重叠加（restack）”发布模型：

```
baseline/（上游原件） + patches/（8 个补丁） → fork-sync.sh 重放 → assets.manifest 校验
```

定稿改为 **git-history** 模型（与 Woloong-OS 的 `tools/sync-upstream.sh` 一致）：

- fork 与上游保持**共同祖先**；
- 定制是 fork 上的**真实提交**（不是运行时打补丁）；
- 版本号 = 上游版本号（`v6.3.2-1` = 上游 v6.3.2 + 1 个定制提交）；
- 同步 = 合并上游（冲突必须显式失败），不是重放补丁。

实测证据：8 个补丁中 2 个已落后 HEAD；manifest 37 项中 18 项哈希过期 —— 重放链本身不可靠。

## 现在怎么办

| 旧文件 | 现状 | 替代 |
|---|---|---|
| `patches/`、`baseline/` | 仅作历史参考，**不再参与构建** | fork 上的真实提交 |
| `fork-sync.sh`、`upstream-sync.yml` | 已停用 / 已删除 | `tools/sync-upstream.sh kiauh`（Woloong-OS 侧） |
| `assets.manifest.*`、`verify-assets.sh` | 不再作为门禁 | `tools/check-kiauh-overlay.sh`（叠层 == 真源） |
| `upstream.json` | 仍记录基线声明 | 保留（只读参考） |

## 不要做的事

- ✗ 不要再用补丁重放覆盖 fork 的提交历史；
- ✗ 不要手工编辑 `kiauh/components/woloong/data/components.json`（它是生成物，见 `kiauh/components/woloong/tools/gen_catalog.py`）。
