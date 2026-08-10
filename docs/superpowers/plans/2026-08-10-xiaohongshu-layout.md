# 小红书图文排版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** 生成可预览、下载并用于小红书半自动发布的 3:4 多图卡片包。

**Architecture:** 文案 Skill 输出 Markdown，独立解析器提取标题、正文要点和标签，Pillow 渲染器生成确定性的中文卡片。Web 任务结果保存卡片资产和 ZIP，并按渠道展示专属操作。

**Tech Stack:** Python 3.13、Pillow、标准库 `zipfile`、现有 HTTP Web 应用和 unittest。

---

### Task 1: 定义图片尺寸和发布包解析契约

**Files:**
- Modify: `tests/test_cover_generation.py`
- Create: `tests/test_xhs_layout.py`

- [ ] 为小红书 3:4 Replicate 请求和 1080 x 1440 输出编写失败测试。
- [ ] 为标题、正文、编号要点、标签及排除“封面图组”编写失败测试。
- [ ] 运行定向测试并确认因功能缺失而失败。

### Task 2: 实现排版 Skill 和渲染器

**Files:**
- Create: `content_agent/skills/xiaohongshu_layout/SKILL.md`
- Create: `content_agent/xhs_layout.py`
- Modify: `content_agent/cover_generation.py`
- Modify: `Dockerfile`

- [ ] 编写 Skill 触发条件、拆卡原则、主题和输出规则。
- [ ] 实现 Markdown 解析、主题选择、中文换行、卡片绘制和 ZIP 打包。
- [ ] 给封面生成器增加渠道尺寸参数，公众号默认行为保持不变。
- [ ] 为生产镜像安装可用的中文字体。
- [ ] 运行定向测试直到通过。

### Task 3: 接入任务与持久化

**Files:**
- Modify: `content_agent/web.py`
- Modify: `tests/test_web.py`

- [ ] 为 `xhs-layout` 前置条件、一键生成和资产持久化编写失败测试。
- [ ] 新增排版步骤并在小红书一键流程中自动执行。
- [ ] 将卡片和 ZIP 写入数据库资产索引。
- [ ] 运行 Web 定向测试直到通过。

### Task 4: 升级预览与发布操作

**Files:**
- Modify: `content_agent/web.py`
- Modify: `tests/test_web.py`

- [ ] 为卡片画廊、打包下载和纯净发布文案编写失败测试。
- [ ] 实现 3:4 卡片预览、逐张保存和 ZIP 下载。
- [ ] 让复制发布包使用 `publish_text`，不包含设计说明。
- [ ] 检查桌面和移动端布局。

### Task 5: 验证与交付

**Files:**
- Modify: `README.md`（仅在需要补充使用说明时）

- [ ] 运行 `python3 -m unittest discover -s tests -v`。
- [ ] 运行 `git diff --check`。
- [ ] 启动本地服务并检查页面与生成卡片。
- [ ] 提交并推送 `main`，确认生产站点响应。

