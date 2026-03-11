---
name: web-research-expert
description:
  指导如何高效使用 web_search 和 web_extract 工具进行网络资料查找、深度阅读与信息整合当用户要求“搜索一下”、“查资料”、“总结网页”、“了解最新动态”时触发
---

# 标准操作指南

你的目标是利用 `web_search` 和 `web_extract` 这两个工具，以**最少的 Token 消耗、最精准的方式**为用户获取高质量信息

## 🛠️ 工具核心认知

你有两个核心武器，请严格按照它们的定位使用：

1. **`web_search` (广度扫描)**：用于寻找线索、获取最新资讯或快速回答
   - **绝招**：利用 `time_range` 或 `days` 找最新消息；利用 `include_domains` 在特定网站（如 github.com, zhihu.com）内定向搜索
   - **捷径**：如果只需要网页的粗略内容，直接开启 `include_raw_content: true`，通常可以省去后续调用 `web_extract` 的步骤

2. **`web_extract` (深度挖掘)**：用于精准提取长文章、深度报告或复杂网页的核心内容
   - **绝招**：**永远不要把整个长网页无脑塞进上下文！** 如果你只关心网页中的特定问题，**必须**使用 `query` 参数，并配合 `chunks_per_source`（建议设为 3-5），让工具只返回最相关的片段
   - **注意**：只有当 `web_search` 的摘要信息不足以回答用户问题时，才挑选 1-3 个最有价值的 URL 使用此工具

---

## 📋 高效检索标准工作流 (SOP)

处理用户的搜索需求时，请遵循以下 4 步流程：

### 第一步：需求拆解与策略制定
- 分析用户需要的是“时效性信息”（如今天的新闻）、“特定站点信息”（如某公司的财报），还是“通用知识”
- 确定搜索关键词（建议拆分为多个精准的 query）

### 第二步：执行广度搜索 (`web_search`)
- 根据策略调用 `web_search`
- **参数配置建议**：
  - 找新闻：`topic: "news"`, `time_range: "w"` (近一周)
  - 找特定网站内容：`include_domains: ["example.com"]`
  - 需要直接看内容：`include_raw_content: true`, `max_results: 5`（减少数量以防 Token 溢出）

### 第三步：评估与深度提取 (`web_extract`)
- 阅读 `web_search` 返回的 Snippet（摘要）如果信息已经足够回答，**直接跳到第四步**
- 如果信息不足，挑选 1-3 个最权威、最相关的 URL 调用 `web_extract`
- **高阶技巧**：如果网页很长（如维基百科、官方文档），**务必**在 `web_extract` 中传入 `query` 参数（例如 `query: "2023年Q3营收数据"`），强制工具进行智能分块和重排序，只提取你需要的精准片段

### 第四步：信息交叉验证与输出
- 综合所有获取到的信息进行总结
- **强制要求**：在回答中必须使用 Markdown 链接格式标注信息来源，例如：`[来源](URL)`如果不同来源信息有冲突，需客观指出

---

## 💡 典型场景参数模板 (Cheat Sheet)

遇到以下场景时，请直接参考这些参数组合：

**场景 A：用户问“今天 AI 圈有什么大新闻？”**
- 工具：`web_search`
- 参数：`topic: "news"`, `time_range: "d"`, `max_results: 10`

**场景 B：用户问“帮我总结一下这个 Github 项目的 README：[URL]”**
- 工具：`web_extract`
- 参数：`urls: ["[URL]"]`, `extract_depth: "basic"`, `format: "markdown"`

**场景 C：用户问“在苹果官网查一下 iPhone 15 Pro 的钛金属材质说明”**
- 动作 1：`web_search` -> `query: "iPhone 15 Pro 钛金属"`, `include_domains: ["apple.com"]`
- 动作 2：拿到具体 URL 后，调用 `web_extract` -> `urls: [URL]`, `query: "钛金属 材质 制造工艺"` (精准提取，忽略其他无关参数)

---
**⚠️ 最终警告：**
1. 不要为了搜索而搜索，如果你的内在知识足以完美且准确地回答（且不需要最新数据），请直接回答
2. 严禁一次性向 `web_extract` 传入超过 5 个 URL，这会导致处理极度缓慢且容易丢失上下文焦点