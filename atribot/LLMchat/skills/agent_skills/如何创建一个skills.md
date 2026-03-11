Skill 的核心结构
Skills 的核心就是：一个文件夹 + 一个 SKILL.md 文件。

SKILL.md 文件包含：

元数据（至少要有名称和描述）
告诉 AI 如何完成某一特定任务的指令


一个 Skill 本质上就是一个 Markdown 文件（文件名固定为 SKILL.md）

my-skill/
└── SKILL.md   （唯一必需）
SKILL.md 基本模板:

---
name: pdf-processing
description: 从 PDF 中提取文本和表格，填写表单，并合并文档
---

# PDF 处理

## 使用场景
当需要对 PDF 文件进行操作时使用，例如：

- 提取 PDF 文本或表格数据
- 填写 PDF 表单
- 合并多个 PDF 文件

## 提取文本
- 使用 `pdfplumber` 提取文本型 PDF 内容  
- 扫描版 PDF 需配合 OCR 工具  

## 填写表单
- 读取 PDF 表单字段  
- 按输入数据填充并生成新文件  
最小必填示例:

---
name: skill-name
description: 说明该 Skill 的功能以及适用场景
---
含可选字段示例:

---
name: pdf-processing
description: 从 PDF 中提取文本和表格，填写表单，并合并文档
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---
字段	必需	说明
name	是	Skill 名称，最长 64 字符，只能使用小写字母、数字和 -，且不能以 - 开头或结尾
description	是	功能与使用场景说明，最长 1024 字符，不能为空
license	否	许可证名称或指向随 Skill 附带的许可证文件
compatibility	否	环境与依赖说明（产品、系统包、网络权限等），最长 500 字符
metadata	否	自定义键值对，用于扩展元数据（如作者、版本号）
allowed-tools	否	允许使用的工具列表（空格分隔，实验性功能）
如果你需要一些参考资料，参考实例，执行脚本，可以使用更复制 Skill 的目录结构：

my-skill/
├── SKILL.md      # 必需：指令 + 元数据
├── scripts/      # 可选：可执行代码
├── references/   # 可选：文档资料
└── assets/       # 可选：模板、资源

技能如何工作
技能用渐进式加载来高效管理上下文：

发现：启动时，AI 只加载每个技能的名称和描述，只保留最基本的识别信息。
激活：当任务匹配某个技能的描述时，AI 才把完整的 SKILL.md 指令读入上下文。
执行：AI 按照指令执行，按需加载参考文件或运行代码。

## 关于我们bot这个Skill有什么用?

我们少了一些功能因为运行不了脚本，值能查看对应的提示词，简单来说可以让模型在对应的情况下查看你编写的文档,我们这里没有环境运行不了编写的脚本什么的