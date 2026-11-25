# Antigravity 与 Codex 双 Agent 协作规范

本文档定义同一 Windows 开发机上 **Antigravity** 与 **Codex** 双窗口并行开发《火种计划 · 边境回响》的协作契约、工作树隔离方法与交叉审查流程。

---

## 1. 协作定位与基本原则

- **协作方式**：由开发者在本地分别打开 Antigravity 与 Codex 双窗口并行推进，通过 `git worktree` 进行文件系统隔离，以 GitHub 仓库 [fireseed-frontier-echoes](https://github.com/moudi01/fireseed-frontier-echoes) 的 Issues（总览 `#1` 及子 Issue `#2`–`#10`）作为任务进度与交接的唯一真值。
- **共同入口**：双方会话均会自动读取根目录 [AGENTS.md](../AGENTS.md) 与 [MEMORY.md](../MEMORY.md)，所有硬约束以这两份入口文件及本规范为准。
- **既有目录边界**：`.acms/` 为本地历史协作快照元数据（已在 `.gitignore` 中忽略），本双窗口协作流程不改写或依赖其生成目录；`local/p03_sol4_20261105/` 为经哈希锁定的 P03 权威运行时基线，未经明确授权不得修改。

---

## 2. 互补分工与交叉审查矩阵

| 角色 | 主责工作 | 交叉审查职责 |
| :--- | :--- | :--- |
| **Antigravity** | 需求拆解与架构/方案设计、P04B 美术风格与 UI/交互设计、真实 GPU 试玩与多模态截图直审、性能曲线分析、GitHub 路线图与 Issue 维护 | 对 Codex 提交的代码分支执行 `git diff main...<分支>` 独立 Review，并运行导出包进行实机画面与交互验收 |
| **Codex** | 确定性 GDScript / Python / PowerShell / Blender 批处理脚本实现、`smoke.gd` 回归用例编写与维护、定向 Bug 修复、导出打包卫生校验 | 对 Antigravity 提交的代码分支执行 `git diff main...<分支>` 独立 Review、静态脚本检查与回归用例复核 |

- **交叉审查原则**：凡合入 `main` 的实质性代码改动，原则上需由另一方进行独立 Review（纯文档更新或开发者显式豁免的极小改动除外）。
- **双方行为底线**：不得绕过 P03 旁载权威回执或篡改事件/存档指纹校验；Codex 如需截取桌面交互窗口画面，须严格按 [CODEX_SHOT_USAGE.md](../_tools/CODEX_SHOT_USAGE.md) 走 `shot_client.ps1` 桥接。

---

## 3. GitHub Issue 认领与热文件防冲突规则

### 3.1 开工前价值判断与认领声明

**先判断 Issue 是否值得做。** Antigravity 和 Codex 在认领或实施前，先核实问题或需求是否成立、是否已有 Issue 覆盖，以及预期收益是否值得投入实现、回归与后续维护的成本。结合实际影响判断，例如玩家体验、项目稳定性、维护效率或当前里程碑进度。确认有价值后再认领。发现重复时关联已有 Issue，证据不足时先记录待核实项并补查，收益不足以支撑投入时在原 Issue 说明理由并建议暂缓。

认领某个 GitHub Issue 并开始编码前，先在对应 Issue 下发表认领评论（或在双窗口派工指令中写明），至少包含四项信息：
1. **执行方**：`Antigravity` 或 `Codex`
2. **本地分支与 Worktree 路径**：如 `wt/codex-issue-5` · `D:\Personal_dev-wt\issue-5-codex`
3. **拟改动热文件**：显式列出计划编辑的高冲突文件
4. **验收方式**：如 `--smoke=chapter --mouse`、GPU 实机截图或单测列表

### 3.2 热文件独占清单
以下文件被多条路线共用，修改频率高，列入**并发独占控制**：
- `原型/P06_首章/main.gd`
- `原型/P06_首章/smoke.gd`
- `原型/P06_首章/hex_board.gd`
- `原型/P06_首章/shield_stage.gd`
- `原型/P06_首章/sidecar/slice_view.py`
- `原型/P06_首章/export_presets.cfg`

### 3.3 防冲突与 Godot UID 规则
- **禁止并发改同一热文件**：同一时刻两个并行窗口**不得同时修改同一热文件**。若两个并行 Issue 都会触及同一热文件，优先将新增逻辑抽离为独立脚本文件（如新建 `*.gd` 模块），否则按依赖顺序串行合入 `main`。
- **Godot UID 规范**：新增 `.gd` 脚本后，必须在对应 worktree 中运行 Godot `--import` 自动生成并同步提交对应的 `.gd.uid` 文件，**严禁手工编造 UID**。

---

## 4. 单远程分支 `main` + 本地 `git worktree` 隔离操作手册（Windows）

### 4.1 分支铁律
- 遵循 [MEMORY.md](../MEMORY.md)：远程仓库 `origin` **只保留一个分支 `main`**。
- **严禁将任何 `wt/*` 本地开发分支推送到 GitHub**。所有特性分支仅在本地使用，合入 `main` 后即在本地删除。

### 4.2 目录与分支命名约定
- Worktree 统一建在主仓库目录之外：`D:\Personal_dev-wt\issue-<编号>-<agy|codex>`
- 本地分支统一命名为：`wt/<agy|codex>-issue-<编号>`（或追加短后缀如 `wt/codex-issue-5-fix-chapter`）

### 4.3 创建 Worktree 与安全补齐忽略依赖（PowerShell 5.1）
由于 `原型/P06_首章/assets/*.import`、`原型/P06_首章/playtest_seeds/.gdignore` 与 `local/p03_sol4_20261105/dist/.../bundle.json` 等文件受 Git 跟踪，而对应的 `.glb` / `.png` / `.jpg` / `.wav`、`python.exe` / `.dll` 及 `playtest_seeds/*.json` 被 `.gitignore` 屏蔽：
- **仅 `.toolchain`** 可创建 NTFS 目录联接（Junction）；
- `local/p03_sol4_20261105/dist`、`原型/P06_首章/assets` 与 `原型/P06_首章/playtest_seeds` **必须用 `robocopy` 只补齐缺失的忽略文件**，不得整目录联接或覆盖 Git 跟踪文件；
- 各 worktree 的 `.godot/`、`build/`、`evidence/` **独立生成与隔离**，严禁跨 worktree 共享。

在主仓或任意 PowerShell 5.1 会话中执行以下模板（按实际 Issue 编号与执行方替换前 3 个变量）：

```powershell
$main = 'D:\Personal_dev'
$wt   = 'D:\Personal_dev-wt\issue-5-codex'
$br   = 'wt/codex-issue-5'

git -C $main worktree add $wt -b $br main
cmd /c mklink /J "$wt\.toolchain" "$main\.toolchain"

robocopy "$main\local\p03_sol4_20261105\dist" "$wt\local\p03_sol4_20261105\dist" /E /XC /XN /XO /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw "robocopy p03 dist failed: $LASTEXITCODE" }

robocopy "$main\原型\P06_首章\assets" "$wt\原型\P06_首章\assets" /E /XC /XN /XO /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw "robocopy P06 assets failed: $LASTEXITCODE" }

robocopy "$main\原型\P06_首章\playtest_seeds" "$wt\原型\P06_首章\playtest_seeds" *.json /XC /XN /XO /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw "robocopy playtest_seeds failed: $LASTEXITCODE" }
```

> 说明：`robocopy` 退出码 `0–7` 均属正常成功状态（无错误），仅 `>= 8` 代表复制异常；`/XC /XN /XO` 可跳过同名且已存在的 Git 跟踪文件（如 `.import`、`.json` 清单）。

### 4.4 安全拆除 Worktree（强制警告）

> [!CAUTION]
> **严禁在 Windows PowerShell 5.1 中对包含 `.toolchain` 目录联接的 worktree 直接执行 `Remove-Item -Recurse`！**
> 递归删除可能穿透 NTFS Junction 并清空主仓库 `D:\Personal_dev\.toolchain\` 下的 Godot 与 Blender 工具链。

必须按以下顺序拆除：

```powershell
$main = 'D:\Personal_dev'
$wt   = 'D:\Personal_dev-wt\issue-5-codex'
$br   = 'wt/codex-issue-5'

# 1. 先卸载 NTFS 目录联接（仅移除联接点，不影响主仓 .toolchain）
if (Test-Path "$wt\.toolchain") { cmd /c rmdir "$wt\.toolchain" }

# 2. 拆除 git worktree 并清理本地分支
git -C $main worktree remove --force $wt
git -C $main branch -d $br
```

---

## 5. 交付、交叉审查与合入 `main` 标准闭环

### 阶段 A · 开发自测与交接
1. 执行方在各自 worktree 内完成开发，并在本地分支提交干净 commit。
2. 在该 worktree 下运行 `.\原型\P06_首章\build_windows.ps1` 构建隔离测试包，并执行相关 `smoke.gd` 回归或单元测试。
3. 在对应的 GitHub Issue 下发表交接评论，列出：
   - 本地分支名与最新 Commit SHA
   - 改动文件列表与核心实现说明
   - 本次构建目录 / 包编号及已通过的 `smoke.gd` / 测试场景
   - 本机截图或报告目录路径（**不提交进 Git**，遵照 [MEMORY.md](../MEMORY.md) 归档规则）

### 阶段 B · 独立交叉审查
1. 另一方在本机以只读视角执行 `git -C D:\Personal_dev diff main..<分支名>` 逐行审查代码改动。
2. 必要时直接启动作者 worktree 的 `build\windows-*\P06.exe`，在正常正交镜头与 1x 播放速度下复核实机观感、告警与 UI 可读性。
3. 在 GitHub Issue 下回复 `LGTM` 或逐条列出阻塞项（附文件路径、行号或截图依据）；若有阻塞项则由作者在原 worktree 修复并更新 Commit SHA。

### 阶段 C · 合入 `main` 与推送
审查通过后，由主合入方按顺序执行：
1. 在作者 worktree 中同步最新 `main`（如有推进则执行 `git rebase main` 并复测受影响用例）。
2. 回到主仓 `D:\Personal_dev`（确保工作区干净且位于 `main`）：
   ```powershell
   git -C D:\Personal_dev merge --ff-only <分支名>
   git -C D:\Personal_dev status -sb
   git -C D:\Personal_dev push origin main
   ```
3. 在对应 Issue 评论合入 `main` 的 Commit SHA、关闭 Issue，并在总览路线图 `#1` 中勾选对应任务项。
4. 按第 4.4 节安全步骤卸载 `.toolchain` 联接并拆除 worktree、删除本地临时分支。

### 5.4 二进制资产变更同步规则
若某个任务新增或修改了 `.glb`、`.png`、`.jpg`、`.wav`、`.blend` 等被 `.gitignore` 忽略的文件：
1. 必须按 [MEMORY.md](../MEMORY.md) 同步更新 Google 云盘资产分包及仓库内 `_tools/workflow-packages.json` 校验清单；
2. 在 Issue 交接评论中显式列出新增/变更的二进制相对路径，提示另一方先从该 worktree 同步或重新运行 `_tools/restore_workflow.ps1` 后再做实机复测。

---

## 6. 双窗口快捷开场指令模板

### 模板 1 · 向 Codex 窗口派发编码 / 回归任务
```text
请评估 GitHub Issue #<编号>（<标题>），确认值得做后再认领和实施。
要求：
1. 先阅读根目录 AGENTS.md、MEMORY.md 与 文档/双Agent协作规范.md，按第 3.1 节判断 Issue 是否值得做，再决定是否认领。
2. 在 D:\Personal_dev-wt\issue-<编号>-codex 创建 worktree 与本地分支 wt/codex-issue-<编号>，按规范补齐 .toolchain 联接与 assets/p03/playtest_seeds 依赖。
3. 仅修改与 #<编号> 直接相关的文件（热文件修改前先检查冲突边界），禁止改动 local/p03_sol4_20261105/ 冻结目录。
4. 完成后在该 worktree 运行 build_windows.ps1 与相关 smoke.gd 用例，提交本地 commit，不要推送分支；将改动清单、Commit SHA 与测试结果汇报给我（并更新到 Issue 评论），等待 Antigravity 交叉审查。
```

### 模板 2 · 向 Antigravity 窗口派发设计 / 验收或交叉 Review 任务
```text
请对 Codex 完成的 Issue #<编号> 分支 wt/codex-issue-<编号>（worktree 位于 D:\Personal_dev-wt\issue-<编号>-codex）进行独立交叉审查与实机验收。
要求：
1. 对照 main 执行 git diff main..wt/codex-issue-<编号>，检查逻辑正确性、P03 权威回执边界与代码质量。
2. 直接使用该 worktree 下构建好的 P06.exe 在正交棋盘镜头和常速下抽检实机画面与回归报告。
3. 在 GitHub Issue #<编号> 下给出 LGTM 或具体修改意见（附文件/行号或截图依据）。
```

### 模板 3 · 审查通过后下达合入与清理指令
```text
Issue #<编号> 已交叉审查通过，请将本地分支 <分支名> 合入 D:\Personal_dev 的 main 分支并推送 origin main：
1. 确认 D:\Personal_dev 工作区干净，必要时先在 worktree 内 rebase main 并复验。
2. 在 D:\Personal_dev 执行 git merge --ff-only <分支名> 并 git push origin main。
3. 更新 Issue #<编号> 状态与 #1 路线图勾选，然后严格按 文档/双Agent协作规范.md 第 4.4 节先 rmdir .toolchain 联接再拆除 worktree 并删除本地分支。
```
