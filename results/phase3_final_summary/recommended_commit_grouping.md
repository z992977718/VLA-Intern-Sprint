# 建议的 Git 提交分组（仅建议，未执行）

当前工作区包含 Phase 2、Phase 3、迁移诊断、视频和收尾文档的大量未提交内容。为了保留证据链，建议先核对大文件策略，再按逻辑分组提交；不要使用一个覆盖所有内容的巨型 commit。

## Group 1：RTX 5090 迁移与 Isaac 启动复现

建议范围：

```text
scripts/check_5090_migration.py
phase2/scripts/configure_headless_vulkan_icd.sh
phase2/scripts/isaac_env.sh
notes/migration_5090_audit.md
notes/isaac_5090_startup_diagnosis.md
results/migration_smoke_5090_*/
results/isaac_5090_startup_diagnosis_*/
results/stage_a_5090*.log
```

建议 commit 主题：

```text
chore: document RTX 5090 migration and Isaac startup verification
```

## Group 2：Phase 2 Observation / Policy / Action Runtime

建议范围：

```text
phase2/ros2_ws/
phase2/scripts/（Step 2–5 runtime 脚本）
notes/phase2_*.md
results/phase2_step1/
results/phase2_step2/
results/phase2_step3/
results/phase2_step4/
results/phase2_step5/
assets/images/phase2_*
assets/videos/phase2_*
```

建议 commit 主题：

```text
feat: add Isaac ROS2 Franka closed-loop VLA runtime
```

## Group 3：Phase 3 Step 6 Cross-simulator Evaluation

建议范围：

```text
phase3/ 中仅属于 Step 6 的脚本和配置
notes/phase3_step6_*.md
results/phase3_step6/
assets/images/phase3_step6_*
assets/videos/phase3_step6_*
```

建议 commit 主题：

```text
feat: add LIBERO to Isaac cross-simulator task evaluation
```

## Group 4：Phase 3 Step 7 Audits、Oracle 与最小修复

建议范围：

```text
phase3/ 中属于 Step 7 的脚本、测试和配置
notes/phase3_step7_*.md（暂不含 final closeout）
results/phase3_step7/
results/phase3_step7_action_parity_matrix_remote.json
assets/images/phase3_step7_*
assets/videos/phase3_step7_*
```

建议 commit 主题：

```text
fix: localize and clear Franka state safety and PINK blockers
```

提交前应逐一确认：

- 原始失败结果与 post-fix 结果同时保留；
- diagnostic trial 没有被改写为 formal benchmark；
- 上游 LeRobot、LIBERO、PINK 源码未被混入；
- 视频大小适合 GitHub；如过大，应使用 Git LFS 或保留索引，不要静默删除。

## Group 5：Phase 3 Closeout 与项目声明边界

建议范围：

```text
README.md
AGENTS.md
notes/commands.md
notes/daily_log.md
notes/project_facts.md
notes/phase3_final_closeout.md
results/phase3_final_summary/
```

建议 commit 主题：

```text
docs: close Phase 3 and freeze Franka Isaac mainline
```

## 提交前检查

1. 逐组使用 `git diff --cached --stat` 和 `git diff --cached` 审查；
2. 对 MP4、模型权重、cache 和大型日志先确认仓库策略；
3. 不提交 token、SSH key、Hugging Face 凭据或服务器私密配置；
4. 不删除或重写 checkpoint、evaluation、视频和原始日志；
5. 保持每个 commit 能解释“新增了什么证据”，不要用结果好坏来筛选文件；
6. 最后一组再更新 README 与冻结边界，确保文档引用的文件已经进入前置 commit。

本轮没有执行 `git add`、`git commit` 或 `git push`。
