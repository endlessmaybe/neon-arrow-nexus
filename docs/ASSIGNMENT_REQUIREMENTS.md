# 第二次个人作业要求核对与证据表

本文用于提交前逐项核对课程作业要求。它不替代博客正文和测试报告，而是把“要求 → 实现 → 可检查证据”连起来，避免最终提交时只凭描述判断是否完成。

当前课程作业列表显示本次作业截止时间为 **2026-09-22 23:59:59**。正式提交前仍应使用本人登录状态再次确认课程页面是否有临时通知或补充要求。

## 1. 基础交付要求

| 要求 | 当前实现 | 证据 |
| --- | --- | --- |
| 使用 Python 完成“一箭又一箭” | 正式实现唯一使用 Python 3 + pygame-ce | `main.py`、`neon_arrow/engine.py`、`neon_arrow/app.py` |
| 基础箭头规则 | 基础模式为单格箭头，仅按上/下/左/右直线检查到边界 | `create_basic_level()`、`docs/screenshots/py-01-basic.png` |
| 简单 / 中等 / 终极困难三档 | 启动页只能选择三档；代码层拒绝越界难度 | `docs/screenshots/py-00-setup.png`、自动测试 |
| 游戏中可重新开始 | `R` 重开当前关并恢复同一 RUN 初始局面 | 功能测试、README 快捷键说明 |
| 通关与失败流程 | 清空全部箭头进入结算；容错或时间耗尽进入失败 | Pygame 状态机、T04/T05 |
| 可直接运行成品 | 提供 PyInstaller 单文件 Windows EXE | `dist/NeonArrowNexus-Python.exe` |

## 2. T01–T06 验收

| 编号 | 测试场景 | 预期 | 对应实现/证据 |
| --- | --- | --- | --- |
| T01 | 点击前方无阻挡的箭头 | 箭头飞出并消失 | 正式点击逻辑 + 离场队列；`--headless-check` 会实际完成一次安全点击 |
| T02 | 点击前方有阻挡的箭头 | 箭头保留，失误次数减 1 | `trace_arrow()/trace_ray()` 的阻挡结果进入碰撞分支 |
| T03 | 点击位于边缘且朝棋盘外的箭头 | 正常消失，不出现越界 | 射线使用边界终止条件；规则测试覆盖边界路径 |
| T04 | 清除本关全部箭头 | 显示通关/进入结算 | 最后一条离场动画完成后进入结果状态 |
| T05 | 失误次数耗尽 | 显示失败，可重新开始 | 稳定度归零进入失败状态，`R` 可重开 |
| T06 | 游戏中重新开始 | 布局和失误次数恢复 | 同一 RUN 重新生成相同布局，并重置本关状态 |

博客园正文 `docs/BLOG_DRAFT.md` 中也有一张面向提交的 T01–T06“预期 / 实际 / 是否通过”表。最终提交前以本轮重新执行后的 `docs/TEST_REPORT.md` 为准。

## 3. AIGC 过程要求

| 检查项 | 当前状态 | 证据 |
| --- | --- | --- |
| 说明使用的 AIGC 工具 | 已记录 ChatGPT / GPT-5.6 Sol | `docs/AIGC_LOG.md` |
| 记录提示目标与修改过程 | 已按多轮开发过程记录 | `docs/AIGC_LOG.md` 第 2 节以后 |
| 说明 AIGC 建议是否合理 | 记录了网页原型、唯一解、基础模式缺失等被否决/修正的方案 | `docs/AIGC_LOG.md` |
| 博客中给出简洁 AIGC 协作记录 | 已用表格汇总“问题 / 建议 / 效果 / 我的修改” | `docs/BLOG_DRAFT.md` |
| 不把 AIGC 输出当作未验证事实 | 所有最终功能继续经过源码测试或实机验证 | `docs/TEST_REPORT.md` |

## 4. 博客园内容

最终博客稿 `docs/BLOG_DRAFT.md` 已按以下顺序组织：

1. 课程 / 作业 / 目标 / 学号 / GitHub 仓库信息；
2. 项目展示与运行截图；
3. 项目介绍、基础规则、三档难度；
4. 核心实现与随机关卡可解性；
5. AIGC 使用过程；
6. T01–T06 与自动化测试结果；
7. PSP 表格；
8. 运行方法；
9. 心得体会与总结。

正式发布前只保留两类必须由本人补齐的内容：**学号**和**真实 GitHub 仓库 URL**。仓库相对图片还需在博客园 Markdown 编辑器中上传后替换为博客园图片地址。

## 5. GitHub 仓库提交内容

应提交：

```text
README.md
main.py
requirements.txt
requirements-dev.txt
neon_arrow/
tests/
scripts/
dist/NeonArrowNexus-Python.exe
docs/
```

其中 `docs/` 至少包含：

- `BLOG_DRAFT.md`：博客园 Markdown 最终稿；
- `AIGC_LOG.md`：AIGC 完整使用记录；
- `ASSIGNMENT_REQUIREMENTS.md`：本要求核对与证据表；
- `TEST_REPORT.md`：测试与 EXE 验收；
- `SUBMISSION_CHECKLIST.md`：本人正式发布前的检查表；
- `screenshots/`：最终 Python/Pygame 实机截图。

不要提交 Token、Cookie、账号密码、浏览器配置或其它敏感信息；不要把早期 HTML/JavaScript 原型混入最终正式实现。

## 6. 提交前唯一不能自动代填的事项

- 学号；
- 创建远程仓库后得到的真实 GitHub URL；
- 博客园上传图片后生成的图片 URL；
- 本人确认无误后的 GitHub push、博客发布和课程平台提交动作。

这些内容必须使用真实本人信息或真实发布结果，不能为了“文档没有空白”而编造。
