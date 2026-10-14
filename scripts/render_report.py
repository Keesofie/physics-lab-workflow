#!/usr/bin/env python3
"""Render a supported Markdown subset to an A4 physics-report PDF.

No network calls. Accepts in-memory text or stdin, writes only a PDF, and
refuses existing output files. Markdown files remain supported as input.
MathText is imported only if equations occur. See references/pdf-and-archive.md.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import os
from pathlib import Path
import re
import sys
import tempfile
import warnings

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, KeepTogether, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

PAGE_WIDTH, PAGE_HEIGHT = 210 * mm, 297 * mm
MARGIN = 22 * mm
BODY_WIDTH = PAGE_WIDTH - 2 * MARGIN
BODY_HEIGHT = PAGE_HEIGHT - 2 * MARGIN


class ReportError(ValueError):
    pass


def choose_font(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ReportError(f"中文字体文件不存在: {path}")
        return path
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/simsun.ttc",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc",
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise ReportError("未找到中文字体；请用 --font 指定支持中文的 TTF/TTC 字体。")


def register_font(path: Path, index: int) -> None:
    try:
        pdfmetrics.registerFont(TTFont("ReportChinese", str(path), subfontIndex=index))
        pdfmetrics.registerFontFamily(
            "ReportChinese", normal="ReportChinese", bold="ReportChinese",
            italic="ReportChinese", boldItalic="ReportChinese",
        )
    except Exception as exc:
        raise ReportError(f"字体无法嵌入，请指定其他 TTF/TTC 字体: {exc}") from exc


def check_glyphs(text: str) -> None:
    glyphs = pdfmetrics.getFont("ReportChinese").face.charToGlyph
    missing = sorted({c for c in text if not c.isspace() and ord(c) not in glyphs})
    if missing:
        chars = " ".join(f"{c} U+{ord(c):04X}" for c in missing[:12])
        raise ReportError(f"中文字体缺少字符: {chars}；请更换 --font 或在不改意义的前提下改写符号。")


def blocks(source: str) -> list[tuple[str, object]]:
    """Strict block parser: unsupported structures fail instead of disappearing."""
    lines = source.splitlines()
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped == "$$":
            start = i
            i += 1
            equation = []
            while i < len(lines) and lines[i].strip() != "$$":
                equation.append(lines[i].strip())
                i += 1
            if i == len(lines):
                raise ReportError(f"第 {start + 1} 行的独立公式没有结束 $$")
            if not " ".join(equation).strip():
                raise ReportError(f"第 {start + 1} 行的公式为空")
            result.append(("math", " ".join(equation)))
            i += 1
            continue
        if stripped.startswith("```"):
            fence = stripped.split()[0]
            if not re.fullmatch(r"`{3,}(?:[\w+-]+)?", fence):
                raise ReportError(f"第 {i + 1} 行的代码围栏不受支持")
            close = re.match(r"`+", fence).group(0)
            code, start = [], i
            i += 1
            while i < len(lines) and lines[i].strip() != close:
                code.append(lines[i])
                i += 1
            if i == len(lines):
                raise ReportError(f"第 {start + 1} 行的代码块没有结束围栏")
            result.append(("code", "\n".join(code)))
            i += 1
            continue
        if re.match(r"\s*(?:>|~~~|<[/!A-Za-z])", line):
            raise ReportError(f"第 {i + 1} 行的引用、HTML 或波浪围栏不受支持，请转换成普通段落")
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            result.append(("heading", (len(heading[1]), heading[2])))
            i += 1
            continue
        if re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", stripped):
            result.append(("rule", ""))
            i += 1
            continue
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image:
            result.append(("image", (image[1], image[2])))
            i += 1
            continue
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                if not raw.endswith("|"):
                    raise ReportError(f"第 {i + 1} 行的表格需要结束竖线")
                cells = re.split(r"(?<!\\)\|", raw[1:-1])
                rows.append([cell.strip().replace(r"\|", "|") for cell in cells])
                i += 1
            if len(rows) < 2 or not all(re.fullmatch(r":?-{3,}:?", c) for c in rows[1]):
                raise ReportError("Markdown 表格缺少 --- 表头分隔行")
            count = len(rows[0])
            if any(len(row) != count for row in rows):
                raise ReportError("表格各行的列数不一致")
            result.append(("table", [rows[0], *rows[2:]]))
            continue
        bullet = re.match(r"^([-+*]|\d+[.)])\s+(.+)$", stripped)
        if bullet:
            if line != line.lstrip():
                raise ReportError(f"第 {i + 1} 行是嵌套列表；请改为平铺列表")
            result.append(("bullet", (bullet[1], bullet[2])))
            i += 1
            continue
        if stripped.startswith("$$") or stripped.endswith("$$"):
            raise ReportError(f"第 {i + 1} 行: 独立公式的 $$ 必须各占一行")
        paragraph = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip():
            nxt = lines[i].strip()
            if re.match(r"^(?:#|\||>|```|~~~|\$\$|!\[|[-+*]\s|\d+[.)]\s)", nxt):
                break
            if re.match(r"^<[/!A-Za-z]", nxt):
                break
            paragraph.append(nxt)
            i += 1
        result.append(("paragraph", " ".join(paragraph)))
    return result


class MathRenderer:
    def __init__(self, directory: Path):
        self.directory = directory
        self.cache = {}

    def render(self, expression: str, size: int = 12):
        key = (expression, size)
        if key in self.cache:
            return self.cache[key]
        try:
            from matplotlib import mathtext
            from matplotlib.font_manager import FontProperties
            from PIL import Image as PILImage
        except ImportError as exc:
            raise ReportError("公式渲染缺少 matplotlib；在项目隔离环境安装 scripts/requirements.txt。") from exc
        filename = hashlib.sha256(repr(key).encode()).hexdigest() + ".png"
        path = self.directory / filename
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                depth = mathtext.math_to_image(
                    "$" + expression + "$", str(path),
                    prop=FontProperties(size=size), dpi=240, format="png",
                )
            with PILImage.open(path) as im:
                width, height = im.size
        except Exception as exc:
            raise ReportError(f"公式无法可靠渲染: {expression}\n{exc}") from exc
        result = (path, width * 72 / 240, height * 72 / 240, float(depth))
        self.cache[key] = result
        return result


class Formula(Flowable):
    def __init__(self, rendered):
        super().__init__()
        self.path, self.width, self.height, _ = rendered
        self.hAlign = "CENTER"
        self.spaceBefore, self.spaceAfter = 6, 9

    def wrap(self, available_width, available_height):
        if self.width > available_width:
            raise ReportError("公式超过正文宽度；请拆成等价的短公式，不要缩成难以辨认的小字。")
        if self.height > BODY_HEIGHT:
            raise ReportError("公式超过一页高度")
        return self.width, self.height

    def draw(self):
        self.canv.drawImage(str(self.path), 0, 0, width=self.width, height=self.height, mask="auto")


def inline(text: str, math: MathRenderer, max_width=BODY_WIDTH) -> str:
    """Escape text before emitting ReportLab markup; equations are explicit images."""
    if re.search(r"<\s*/?\s*[A-Za-z][^>]*>", text):
        raise ReportError("正文中的 HTML 不受支持，请转换为普通 Markdown")
    parts = re.split(r"(`[^`\n]+`|(?<!\\)\$[^$\n]+(?<!\\)\$)", text)
    fragments = []
    for part in parts:
        if part.startswith("$") and part.endswith("$"):
            path, width, height, depth = math.render(part[1:-1], 11)
            if width > max_width * 0.85:
                raise ReportError("内联公式过长；请改为独立公式")
            fragments.append(
                f'<img src="{html.escape(str(path), quote=True)}" width="{width:.2f}" '
                f'height="{height:.2f}" valign="{-depth:.2f}"/>'
            )
            continue
        if part.startswith("`") and part.endswith("`"):
            part = part[1:-1]
            check_glyphs(part)
            fragments.append(html.escape(part))
            continue
        # Currency/literal dollars use \$. Unbalanced delimiters must not disappear.
        if re.search(r"(?<!\\)\$", part):
            raise ReportError("存在未配对的内联公式 $；普通美元符号请写成 \\$")
        part = part.replace(r"\$", "$")
        if "![" in part:
            raise ReportError("图片必须独立成段")
        part = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f"{m[1]} ({m[2]})", part)
        check_glyphs(part)
        escaped = html.escape(part)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
        fragments.append(escaped)
    return "".join(fragments)


def make_styles():
    base = dict(fontName="ReportChinese", fontSize=11, leading=17, wordWrap="CJK", autoLeading="max")
    return {
        "body": ParagraphStyle("body", **base, spaceAfter=6),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 9.5, "leading": 14}),
        "caption": ParagraphStyle("caption", **{**base, "fontSize": 9.5, "leading": 14}, alignment=TA_CENTER, spaceAfter=9),
        "code": ParagraphStyle("code", **{**base, "fontSize": 9, "leading": 13}, backColor=colors.HexColor("#F5F5F5"), spaceAfter=8),
        "title": ParagraphStyle("title", **{**base, "fontSize": 17, "leading": 25}, alignment=TA_CENTER, spaceAfter=14, keepWithNext=True),
        "heading": ParagraphStyle("heading", **{**base, "fontSize": 12.5, "leading": 20}, spaceBefore=9, spaceAfter=6, keepWithNext=True),
        "bullet": ParagraphStyle("bullet", **base, leftIndent=14, firstLineIndent=-10, spaceAfter=4),
    }


def story_from(source: str, base_dir: Path, math: MathRenderer):
    styles = make_styles()
    story = []
    for kind, value in blocks(source):
        if kind == "heading":
            level, text = value
            story.append(Paragraph(inline(text, math), styles["title" if level == 1 else "heading"]))
        elif kind == "paragraph":
            story.append(Paragraph(inline(value, math), styles["body"]))
        elif kind == "bullet":
            marker, text = value
            prefix = "·" if marker in "-+*" else marker
            story.append(Paragraph(html.escape(prefix) + " " + inline(text, math), styles["bullet"]))
        elif kind == "math":
            story.append(Formula(math.render(value)))
        elif kind == "code":
            check_glyphs(value)
            # Paragraph wrapping prevents long code lines overflowing the page.
            code = html.escape(value).replace(" ", "&#160;").replace("\n", "<br/>")
            story.append(Paragraph(code or " ", styles["code"]))
        elif kind == "rule":
            story.append(Spacer(1, 8))
        elif kind == "image":
            caption, location = value
            if re.match(r"^[A-Za-z]+://", location):
                raise ReportError("图片只支持本地文件，不自动下载外部链接")
            path = (base_dir / location).resolve()
            if not path.is_file():
                raise ReportError(f"图片不存在: {path}")
            try:
                img = Image(str(path))
                ratio = min(1, BODY_WIDTH / img.imageWidth, (BODY_HEIGHT - 75) / img.imageHeight)
                img.drawWidth, img.drawHeight = img.imageWidth * ratio, img.imageHeight * ratio
                img.hAlign = "CENTER"
            except Exception as exc:
                raise ReportError(f"图片无法读取: {path}: {exc}") from exc
            content = [img]
            if caption:
                content.append(Paragraph(inline(caption, math), styles["caption"]))
            if story and isinstance(story[-1], Paragraph) and story[-1].style.keepWithNext:
                content.insert(0, story.pop())
            story.append(KeepTogether(content))
        elif kind == "table":
            count = len(value[0])
            if count > 10:
                raise ReportError("表格列数超过 10，请按量组拆表")
            widths = [BODY_WIDTH / count] * count
            cells = [[Paragraph(inline(c, math, widths[col] - 10), styles["cell"])
                      for col, c in enumerate(row)] for row in value]
            table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.extend([table, Spacer(1, 9)])
    if not story:
        raise ReportError("源稿为空")
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("ReportChinese", 9)
    canvas.drawCentredString(PAGE_WIDTH / 2, 12 * mm, str(doc.page))
    canvas.restoreState()


def render(input_path: Path, output_path: Path, font=None, font_index=0):
    input_path, output_path = input_path.resolve(), output_path.resolve()
    if input_path == output_path:
        raise ReportError("输出不能与源稿相同")
    source = input_path.read_text(encoding="utf-8-sig")
    return render_text(source, output_path, base_dir=input_path.parent,
                       font=font, font_index=font_index, title=input_path.stem)


def render_text(source: str, output_path: Path, *, base_dir=None,
                font=None, font_index=0, title=None):
    """Render from memory without creating a source file or persistent assets.

    Image paths resolve against base_dir (cwd by default). Only the requested
    PDF is written outside the automatically cleaned temporary directory.
    """
    output_path = Path(output_path).resolve()
    base_dir = Path(base_dir).resolve() if base_dir is not None else Path.cwd()
    if output_path.exists():
        raise ReportError(f"输出已存在，拒绝覆盖: {output_path}")
    if output_path.suffix.lower() != ".pdf":
        raise ReportError("输出文件必须为 .pdf")
    register_font(choose_font(font), font_index)
    # Build fully in memory; reserve destination only once after success.
    with tempfile.TemporaryDirectory(prefix="physics-lab-render-") as directory:
        math = MathRenderer(Path(directory))
        story = story_from(source, base_dir, math)
        memory = io.BytesIO()
        doc = BaseDocTemplate(memory, pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
                              leftMargin=MARGIN, rightMargin=MARGIN,
                              topMargin=MARGIN, bottomMargin=MARGIN,
                              title=title or output_path.stem, author="", pageCompression=1)
        frame = Frame(MARGIN, MARGIN, BODY_WIDTH, BODY_HEIGHT,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=footer))
        doc.build(story)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("xb") as output:
            output.write(memory.getvalue())
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="已有的 UTF-8 Markdown 输入文件，或 - 从标准输入读取")
    parser.add_argument("--output", required=True, type=Path, help="不存在的 PDF 输出路径")
    parser.add_argument("--base-dir", type=Path, help="标准输入模式下相对图片路径的基目录，默认当前目录")
    parser.add_argument("--font", help="中文 TTF/TTC 字体文件")
    parser.add_argument("--font-index", type=int, default=0, help="TTC 子字体序号，默认 0")
    args = parser.parse_args()
    try:
        if args.input == "-":
            source = sys.stdin.buffer.read().decode("utf-8-sig")
            path = render_text(source, args.output, base_dir=args.base_dir,
                               font=args.font, font_index=args.font_index)
        else:
            if args.base_dir is not None:
                raise ReportError("--base-dir 仅用于标准输入模式；文件模式的图片相对于输入文件")
            path = render(Path(args.input), args.output, args.font, args.font_index)
    except Exception as exc:
        print(f"未生成 PDF: {exc}", file=sys.stderr)
        return 1
    print(f"已生成 PDF（仍需逐页视觉检查）: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
