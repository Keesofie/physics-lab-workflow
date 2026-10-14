# physics-lab-workflow

可迁移的中文大学物理实验报告 skill。根据已有实验材料生成或修改实验报告，**只交付一份 PDF；缺失内容留空，不发起补充问答**。

## 使用行为

1. 读取学案、教材片段、原始数据、照片、已有现场记录和草稿。
2. 对信息充分的部分实际核算，保留原始精度及异常值。
3. 不追问现象、步骤、异常原因或个人判断。未知字段、歧义读数及缺少依据的讨论直接留空，缺项依赖的计算结果也留空。
4. 按课程要求整理正式报告。仅有学案时也生成七部分的可填写实验报告，不生成预习报告或现场记录表。
5. 在临时目录或内存处理源稿、图表和核算，只把最终 PDF 写入报告目录；逐页检查后仅返回 PDF 链接。

已有个人观察和判断可润色，不能编造实验经历或代写缺失的个人分析。未提供内容不会用“无异常”“未知”或数字零替代。PDF 有空缺时用一句注记说明需本人补全，保留填写位置。

默认课程结构摘自用户提供的 2026-09-24 山东大学绪论笔记，要求最终手写；其他课程使用其已提供要求。PDF 是报告底稿，学生仍需自行理解、核验、补全个人分析并满足课程的最终提交要求。

## 安装与调用

将整个目录安装到对应工具的技能目录。Codex 个人目录通常为 `~/.codex/skills/physics-lab-workflow`；已有同名版本时先检查个人修改。其他工具按其自己的技能目录配置。

通用入口是 [SKILL.md](SKILL.md)，内部引用均为相对路径；`agents/openai.yaml` 为 Codex 的显示与自动匹配配置。不支持技能自动发现的 agent，可让它直接读取入口。

```text
使用 $physics-lab-workflow，根据这些材料生成实验报告。未知内容留空，不追问，只输出 PDF。
```

本 skill 不支持预习报告、课前准备或现场记录表设计。

## PDF 脚本

在项目隔离环境安装依赖：

```bash
python -m venv .venv
# 按系统激活隔离环境；Windows 可直接使用 .venv\Scripts\python.exe
python -m pip install -r scripts/requirements.txt
```

从内存传入正文，仅写入 PDF：

```python
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from render_report import render_text

render_text(report_text, Path("实验报告/实验报告.pdf"), base_dir=temporary_asset_dir)
```

或者向脚本的标准输入发送 UTF-8 正文：

```text
python scripts/render_report.py - --base-dir <临时图片目录> --output <报告.pdf>
```

为兼容已有输入，脚本仍能读取 Markdown 文件；不需要新建或输出源稿。支持中文 A4、标题、列表、表格、本地图片和 MathText 公式；拒绝覆盖现有 PDF。`--font` 指定中文 TTF/TTC，`--font-index` 指定 TTC 子字体，包内不分发字体。

独立公式的 `$$` 各占一行，内联公式用 `$...$`。复杂公式需等价拆分为 MathText 支持的形式。中间图表和预览使用临时目录，检查后清理；不输出为附件。完整规则见 [PDF 输出](references/pdf-and-archive.md)。

## 验证

```bash
python tests/validate_structure.py
python tests/test_renderer.py
```

GitHub Actions 安装依赖和中文字体后运行结构及渲染测试，包括公式、表格、内存与标准输入模式和只留下 PDF 的检查。实际结果以仓库 Actions 状态为准。自动测试不能代替每份报告的逐页视觉检查，也不是 agent 行为评测。

技能包包含入口、课程与数据参考、PDF 脚本、Codex 配置和测试，不包含真实实验数据、教材、个人对话、虚拟环境、字体或生成报告。
