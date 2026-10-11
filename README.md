# physics-lab-workflow

可迁移的中文大学物理实验 skill，覆盖预习、现场记录表设计、课后数据核算和报告整理。默认输出 PDF，并保留 Markdown 源稿。

输入学案、教材片段、原始数据、现场记录及个人想法。Agent 先读取并检查已有信息，再集中追问必要的现场观察和你自己的判断，最后整理完整、简练、可追溯的报告底稿。

## 工作方式

1. 只有学案时，生成五部分预习材料和记录表，不编造课后结果。
2. 课后保留原始读数、精度和异常值，实际执行计算并留下可复查记录。
3. 针对本次实验询问实际操作、现象、异常和个人判断，允许口语回答。
4. 按当前课程要求整理正式报告。缺核心信息时明确标为待补充草稿。
5. 输出 PDF 与源稿，计算代码、AI 使用范围和修改记录另存；后续版本不覆盖原稿。

现场记录、核心分析和结论需由学生本人提供依据。AI 可解释、核算和润色，不能编造观察或凭“确认”代替学生自己的理由。报告底稿需学生理解、核验，并按课程规定完成最终报告。

默认课程配置来自用户提供的 2026-09-24 山东大学物理实验绪论笔记，要求最终手写。适用于其他课程时，使用该课程提供的要求，不自动沿用山东大学规定。

## 在 agent 中使用

支持 skill 的工具可将整个目录放入对应技能目录。跨工具核心入口为 [SKILL.md](SKILL.md)，引用文件均在包内；`agents/openai.yaml` 仅用于 Codex 的发现与显示。

Codex 个人技能目录通常为 `~/.codex/skills/physics-lab-workflow`。克隆到那里或复制整个仓库目录；已有同名技能时先检查，勿覆盖个人修改。其他工具的目录及自动发现行为以对应工具为准。

不支持自动发现的 agent，可明确要求它读取 `SKILL.md`，并按当前阶段读取相关参考。

```text
使用 $physics-lab-workflow。读取我提供的实验学案和原始记录，先检查数据与缺项，再问我的现场观察和个人判断，最后生成 PDF 报告并保留 Markdown。
```

## PDF 辅助脚本

建议在项目隔离环境中安装依赖，不修改系统环境：

```bash
python -m venv .venv
# 按操作系统激活 .venv；Windows 可直接使用 .venv\Scripts\python.exe
python -m pip install -r scripts/requirements.txt
python scripts/render_report.py report.md --output report.pdf
```

脚本支持中文 A4、标题、列表、表格、图片和 MathText 公式，拒绝覆盖已有 PDF。可以通过 `--font` 指定中文 TTF/TTC 字体，`--font-index` 指定 TTC 子字体序号。默认探测 Windows、Linux 和 macOS 的部分常见中文字体；包内不分发字体。

独立公式使用单独一行的 `$$` 开始和结束，内联公式用 `$...$`。仅支持 Matplotlib MathText 子集，复杂公式需等价拆分。图片使用本地路径；不自动下载外部链接。

PDF 导出后必须逐页检查，不能仅凭生成成功判定可交付。完整规则见 [PDF 与归档](references/pdf-and-archive.md)。

## 验证与当前状态

```bash
python tests/validate_structure.py
python tests/test_renderer.py
```

制作环境已通过基础结构检查及 6 项脚本测试，4 页模拟 PDF 已逐页视觉检查。该环境缺 Matplotlib，2 项公式测试尚未执行；官方 skill-creator 校验所需 PyYAML 也未安装。不能把现有验收视为实际公式渲染已验证。

仓库包含 GitHub Actions 验证配置，在安装依赖和中文字体后执行结构检查及全部渲染测试。CI 的真实运行状态以 GitHub 为准，不预先宣称通过。自动测试不能代替每份最终报告的视觉检查，也不能证明 agent 的实际追问和分析行为符合全部要求。

## 文件

- `SKILL.md`：通用工作流入口。
- `references/`：课程要求、数据与证据、PDF 和归档规则。
- `scripts/`：PDF 生成脚本及依赖列表。
- `agents/`：Codex 专用显示和调用配置。
- `tests/`：结构和渲染检查。

仓库不包含真实实验数据、课程教材、个人对话记录、虚拟环境、字体或生成报告。
