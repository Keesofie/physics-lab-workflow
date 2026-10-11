"""Dependency-free structural check for this package, not a PyYAML substitute.

Only accepts this package's intentionally simple frontmatter. The bundled
quick_validate.py remains a separate check requiring PyYAML.
"""
from pathlib import Path
import re

SKILL = Path(__file__).resolve().parents[1]
source = (SKILL / "SKILL.md").read_text(encoding="utf-8")
match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", source, re.S)
assert match, "Frontmatter missing"
front = {}
for line in match[1].splitlines():
    key, value = line.split(":", 1)
    assert key not in front
    assert not value.lstrip().startswith(("[", "{", "|", ">", "&", "*", "!"))
    front[key] = value.strip()
assert set(front) == {"name", "description"}
assert front["name"] == "physics-lab-workflow"
assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", front["name"])
assert len(front["name"]) <= 64
assert 0 < len(front["description"]) <= 1024
assert "[TODO:" not in source
for file in SKILL.rglob("*.md"):
    text = file.read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if re.match(r"^[A-Za-z]+://", link) or "<" in link or "相对路径" in link:
            continue
        if not link.startswith(("references/", "scripts/")):
            continue
        assert (file.parent / link).is_file(), f"Broken reference: {file}: {link}"
assert "allow_implicit_invocation: true" in (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
assert not re.search(r"[CD]:[/\\]", source), "Core instructions tied to machine"
print("PASS: simple frontmatter, skill name/description, references, invocation policy, portable core")
