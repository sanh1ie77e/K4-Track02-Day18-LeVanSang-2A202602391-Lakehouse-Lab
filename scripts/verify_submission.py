"""Verify saved evidence without executing/mutating lakehouse tables."""
from pathlib import Path
import json
import nbformat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"
files = sorted((OUT / "notebooks").glob("*.ipynb"))
assert len(files) == 8, "Exactly eight notebook submissions are required"
for n, p in enumerate(files, 1):
    nb = nbformat.read(p, as_version=4)
    nbformat.validate(nb)
    code = [c for c in nb.cells if c.cell_type == "code"]
    assert all(c.execution_count is not None for c in code), f"Unexecuted cell: {p.name}"
    assert not any(o.output_type == "error" for c in code for o in c.outputs), p.name
    assert any(c.metadata.get("lab_explanation") for c in nb.cells), p.name
    assert list((OUT / "screenshots").glob(f"nb{n:02}_*.jpg")), p.name
    print(f"PASS {p.name}: {len(code)} executed cells, explanation, screenshots")
words = len((OUT / "REFLECTION.md").read_text(encoding="utf-8").split())
assert words <= 200, f"Reflection has {words} words"
assert json.loads((OUT / "evidence" / "original_data_integrity.json").read_text(encoding="utf-8"))["unchanged"]
assert "8/8 passed" in (OUT / "evidence" / "run_all.txt").read_text(encoding="utf-8")
assert "30 passed, 1 skipped" in (OUT / "evidence" / "pytest.txt").read_text(encoding="utf-8")
print(f"PASS reflection: {words}/200 words; original data unchanged; checks successful")
