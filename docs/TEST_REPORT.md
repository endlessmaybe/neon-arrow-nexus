# 霓虹箭域测试报告

测试日期：2026-09-15

## 1. 测试环境

```text
OS      Windows
Node    v24.19.0
npm     11.17.0
Server  http://127.0.0.1:4173
Browser Playwright Chromium
```

## 2. 静态与逻辑自动测试

执行：

```bash
npm run check
```

实际结果：

```text
> node --check src/engine.js
> node --check src/game.js
> node --check scripts/server.mjs
> node tests/engine.test.mjs

engine.test: 3 deterministic, solvable levels verified.
```

结论：**PASS**。

### 自动测试覆盖

| 编号 | 测试项 | 结果 |
| --- | --- | --- |
| E01 | 三个关卡相同 seed 重复生成，结构完全一致 | PASS |
| E02 | 每关生成箭路数量达到目标下限 | PASS |
| E03 | 每关保存的完整解序可由真实射线规则重新执行到底 | PASS |
| E04 | 初始局面至少存在一条被阻挡箭，具备真实解谜选择 | PASS |
| E05 | 解序第一条箭在当前棋盘中可安全离场 | PASS |

## 3. 浏览器首屏

### 步骤

1. `npm start`；
2. Playwright 打开 `http://127.0.0.1:4173`；
3. 获取无障碍快照；
4. 检查控制台。

### 实际结果

- 页面标题：`霓虹箭域 · Neon Arrow Nexus`；
- 关卡显示：`01 / 03`；
- 初始箭路：`20`；
- 开始按钮、音效、重开、超载、提示等控件均被浏览器识别；
- 首次测试发现 `favicon.ico 404`；
- 修复 `favicon.svg` 后重新开全新浏览器会话；
- 控制台最终为：`0 errors, 0 warnings`。

结论：**PASS**。

## 4. 错误点击分支

### 步骤

1. 进入第一关；
2. 用游戏引擎识别一条当前确实受阻的箭；
3. 通过与正常点击相同的处理函数执行该箭。

### 实际状态

点击前：

```json
{
  "status": "playing",
  "lives": 4,
  "remaining": 20
}
```

点击后：

```json
{
  "status": "playing",
  "lives": 3,
  "remaining": 20
}
```

结论：碰撞不会错误删除箭路，稳定度正确 `4 → 3`。**PASS**。

## 5. 第一关完整通关

### 步骤

按生成器记录、并已通过引擎验证的解序逐条执行所有剩余箭路。

### 实际结果

```text
remaining      0
best combo     ×20
score          8115
time bonus     +2003
result overlay “箭域已清空”
next action    “进入下一扇区”
```

结果弹层、分数、最高连击和下一关按钮均实际出现在浏览器快照中。

结论：**PASS**。

## 6. 第二关折光/量子系统

### 6.1 能量积累

进入第二关后连续正确清除前 6 条安全箭路。

实际状态：

```json
{
  "levelIndex": 1,
  "status": "playing",
  "combo": 6,
  "lives": 4,
  "charge": 100,
  "remaining": 20
}
```

浏览器中的“启动超载”按钮从 disabled 变成可点击，并显示“能量充满 · 可以启动”。

结论：**PASS**。

### 6.2 相位穿透

1. 真实点击“启动超载”；
2. 再选择一条当前受阻箭路。

实际状态：

```json
{
  "levelIndex": 1,
  "status": "playing",
  "combo": 7,
  "lives": 4,
  "charge": 0,
  "remaining": 19
}
```

对比可知：

- 受阻箭确实被删除：`20 → 19`；
- 没有受到碰撞伤害：`lives = 4`；
- 能力正确消耗：`100 → 0`。

结论：**PASS**。

## 7. 响应式验收

实际把 Chromium 视口切换为：

```text
375 × 812
```

并生成真实浏览器视口截图。CSS 针对 ≤720 px 会执行：

- 页面外边距缩小；
- HUD 改为两列；
- 关卡卡片和稳定度横跨两列；
- 右侧控制栏改为单列；
- 棋盘改为更适合手机的纵向比例；
- 桌面“重新校准”顶栏按钮隐藏，仍可使用键盘/游戏流程内控制。

浏览器页面仍可正常操作，控制台保持无应用错误。

结论：**PASS**。

### 留档截图

```text
docs/screenshots/01-home-desktop.png
docs/screenshots/02-level1-result.png
docs/screenshots/03-level2-overdrive.png
docs/screenshots/04-mobile-375x812.png
```

## 8. 可访问性与交互检查

| 检查项 | 实现 |
| --- | --- |
| 页面语言 | `lang="zh-CN"` |
| Viewport | 已设置移动端 viewport |
| 图标按钮 | 音效按钮有 `aria-label` 与 `aria-pressed` |
| Canvas | 有可读的 `aria-label`，可获取键盘焦点 |
| 键盘 | Enter 开始、R 重开、H 提示、O 超载 |
| 焦点 | `:focus-visible` 高对比描边 |
| 触控 | Canvas `touch-action: manipulation`，主要按钮 ≥44px |
| 减少动态 | 支持 `prefers-reduced-motion` |
| 状态提示 | toast 使用 `role=status` / `aria-live=polite` |

## 9. 回归建议

正式提交前如果再修改核心逻辑，至少重新运行：

```bash
npm run check
```

如果修改 Canvas、按钮或响应式 CSS，再追加一次浏览器首屏 + 通关流程检查。

