# GitHub / 博客园发布前预览

> 当前状态：**只准备，不上传、不发布。** 用户明确确认后，才执行远程仓库创建/推送、Release 上传和博客园发布。

## 1. GitHub 预案

拟使用账号：`endlessmaybe`

拟定仓库名：

```text
neon-arrow-nexus
```

拟定仓库简介：

```text
Python/Pygame 实现的“一箭又一箭”课程项目：基础单格模式 + 进阶随机长箭模式，包含随机可解关卡、AI 求解、撤销、存档、动画音效与 Windows EXE。
```

拟定默认分支：`main`

拟定可见性：`Public`

### 仓库首页重点

- 首图使用 `docs/screenshots/py-00-setup.png`，先展示“基础 / 进阶 + 三档难度”的完整启动流程；
- 第二张展示 `docs/screenshots/py-01-basic.png`，证明基础模式不是文案换皮；
- 后续展示进阶中等、终极困难、通关页和箭头有序离场；
- README 先写作业基础规则，再写进阶创新，避免老师先看到机关却找不到题目主体；
- 源码入口保持 `main.py`，最终仓库不放旧 HTML / CSS / JavaScript 原型。

### 当前 Release 方案

Tag：

```text
v1.0.5
```

Release 标题：

```text
Neon Arrow Nexus v1.0.5
```

附件：

```text
NeonArrowNexus-v1.0.5-Windows-x64.zip
```

Release 说明草稿：

```text
课程提交版。正式实现为 Python 3 + Pygame。

- 基础模式：单格四方向箭头，按作业原规则做直线路径判断；
- 进阶模式：2–4 格随机长箭，加入折光、反相、双跃迁和阶段相位锁；
- 每次启动先选择玩法模式和简单 / 中等 / 终极困难；
- 游戏过程中可按 D 打开难度切换面板，直接改为简单 / 中等 / 终极困难；
- 支持撤销、自动存档、AI 自动求解、计分/计时/星级、量子超载、低动态和音效；
- Windows 单文件 EXE，可直接双击运行。
```

## 2. 博客园预案

拟发布账号主页：

```text
https://www.cnblogs.com/Heimdallr
```

拟定标题：

```text
2026 秋软件工程个人作业（第二次）——霓虹箭域 Neon Arrow Nexus
```

正式 Markdown 源稿：

```text
docs/BLOG_DRAFT.md
```

正文已经按作业提交结构重新整理为：课程信息表 → 项目展示 → 项目介绍 → 核心实现 → AIGC 使用过程 → T01–T06 与自动测试 → PSP → 运行方法 → 心得体会 → 总结。其中 AIGC 部分不再只放一张汇总表或要求读者跳转 `AIGC_LOG.md`，而是在正文内直接展开 3 次由真实开发线程压缩润色的“我 ↔ ChatGPT”对话，并接上实际修改和验证结果。学号和最终 GitHub URL 在正式发布前再填，不在当前预览阶段编造。

GitHub 侧同时提供 `docs/ASSIGNMENT_REQUIREMENTS.md`，把作业要求逐项映射到代码、测试和截图；老师不需要只靠 README 的功能描述判断是否完成。

### 拟上传图片顺序

1. `py-00-setup.png`：每次启动的模式与难度选择；
2. `py-01-basic.png`：基础模式单格箭头；
3. `py-02-level2.png`：进阶中等；
4. `py-03-level3.png`：进阶终极困难；
5. `py-04-complete.png`：结果页；
6. `py-06-arrow-exit.png`：箭头有序离场中间帧，可放在动画说明段落；
7. `py-07-difficulty-switch.png`：游戏进行中的难度切换面板；
8. `py-08-control-icons.png`：优化后的统一功能图标、文字和快捷键实战布局。

发布到博客园时，相对图片路径需要替换为博客园上传图片后返回的真实地址；当前草稿先保留仓库相对路径，方便 GitHub 直接预览。

## 3. 发布前还要核对的点

- [x] 最终全量 pytest 通过：`59 passed`，其中 T01–T06 为独立自动测试，并包含启动 UI 首帧回归；
- [x] 源码 `--headless-check` 通过；
- [x] 重新构建 EXE，打包后的 EXE 自检通过；
- [x] 启动页截图和基础模式截图为本轮新版本；
- [x] README / BLOG / TEST_REPORT 已统一到“基础单格 + 进阶长箭 + 启动选难度 + 实战 D 切换难度 + 功能图标说明 + 性能优化”的口径；
- [x] 已扫描最终文本文件，未发现疑似 Token / API Key；临时构建产物仍放在 H: 临时目录，不进入提交；
- [x] GitHub 仓库与 Release 已建立；本轮修复继续使用同一仓库，不创建重复仓库。

## 4. 当前远程状态

- GitHub 仓库：`https://github.com/endlessmaybe/neon-arrow-nexus`；
- `origin/main` 已存在，正式成品使用 GitHub Releases 发布；
- Release 工作流现已改成：标签触发 → 安装 Python/依赖 → 从标签源码重新构建 EXE → `--headless-check` → 打包 ZIP → 发布 Release；
- 因此 Release 不再直接复用仓库中可能过期的 `dist/NeonArrowNexus-Python.exe`，避免“博客截图是新 UI、下载成品仍是旧构建”的再次发生；
- 博客园正文仍由本人确认后发布。

本轮最终 EXE：

```text
dist/NeonArrowNexus-Python.exe
28,258,481 bytes
SHA-256 CDD85F2CC464B30708098F2B9A6BAFA3DD48867FFD0ED4C604080014B74766E9
```

