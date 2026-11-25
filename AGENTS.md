# 项目记忆入口

项目长期记录见 [MEMORY.md](MEMORY.md)。涉及角色动画制作、扩展或流程复用时，先阅读其中链接的动画制作流程文档。

## 双 Agent 协作约定（Antigravity + Codex）

详细操作手册与指令模板见 [双Agent协作规范](文档/双Agent协作规范.md)。每次会话须严格遵守：

1. **互补分工与互审**：Antigravity 偏架构设计、UI/美术与实机多模态试玩验收，Codex 偏确定性编码、回归脚本与批处理；实质代码改动合入 `main` 前须经另一方独立交叉审查。
2. **任务与热文件防冲突**：以 GitHub Issues 为任务板；修改 `main.gd`、`smoke.gd`、`hex_board.gd`、`shield_stage.gd`、`sidecar/slice_view.py`、`export_presets.cfg` 等热文件前先核对认领，禁止双窗口同时改同一热文件。
3. **worktree 隔离与单远程分支**：并行开发须在仓库外创建本地 `git worktree` 与 `wt/*` 本地分支；严禁向 `origin` 推送除 `main` 外的分支。
4. **只读基线与归档边界**：不得未经批准修改 `local/p03_sol4_20261105/` 冻结基线；不提交构建产物、验收截图、日志或 `.gitignore` 屏蔽的二进制大文件。
5. **联接安全清理**：拆除 worktree 前先用 `cmd /c rmdir "<wt>\.toolchain"` 卸载目录联接，禁止直接递归删除。
