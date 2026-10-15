"""Diagnose Private-Use-Area (PUA) glyphs in the PDF text layer and test repairs.

Legacy Arabic fonts often store letters as U+F000 + <byte of a legacy code page>.
For each PDF this prints STATISTICS ONLY (no legal text):
  - which PUA ranges are used,
  - for each candidate code page: % Arabic after decoding, "فصل" counts
    (normal and reversed order),
  - the same "فصل" counts in the OCR JSON of data/raw/txt (fallback source).
    python -m src.legal_retrieval.tools.diagnose_pua
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from src.legal_retrieval.corpus.loaders import load_pages, load_pdf_pages
from src.legal_retrieval.corpus.normalize import normalize_arabic

CANDIDATE_CODEPAGES = ("cp1256", "iso8859_6", "mac_arabic")


def decode_pua(text: str, codepage: str) -> str:
    """Map U+F0xx -> byte xx -> character of `codepage` (other chars kept)."""
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xF000 <= cp <= 0xF0FF:  # "symbol font" range
            out.append(bytes([cp - 0xF000]).decode(codepage, errors="replace"))
        else:
            out.append(ch)
    return "".join(out)


def _stats(text: str) -> dict[str, float | int]:
    """Share of Arabic letters + "فصل" counts in both reading orders."""
    letters = [c for c in text if c.isalpha()]
    arabic = sum("ء" <= c <= "ي" for c in letters)
    norm = normalize_arabic(text)
    return {
        "arabic_ratio": round(arabic / len(letters), 3) if letters else 0.0,
        "fasl": norm.count("فصل"),
        "fasl_reversed": norm.count("لصف"),
    }


def diagnose(pdf: Path, txt_dir: Path) -> dict[str, object]:
    """PUA profile + repair candidates for one PDF."""
    text = "\n".join(p.text for p in load_pdf_pages(pdf))
    pua = [ord(c) for c in text if 0xE000 <= ord(c) <= 0xF8FF]
    blocks = Counter(f"U+{cp >> 8:02X}xx" for cp in pua)  # e.g. U+F0xx
    report: dict[str, object] = {
        "file": pdf.name,
        "pua_chars": len(pua),
        "pua_blocks_top5": blocks.most_common(5),
        "raw": _stats(text),
        "decoded": {cp: _stats(decode_pua(text, cp)) for cp in CANDIDATE_CODEPAGES},
    }
    ocr_json = txt_dir / f"{pdf.stem}.json"
    if ocr_json.exists():  # Tradrly OCR output, as a fallback comparison
        report["ocr_json"] = _stats("\n".join(p.text for p in load_pages(ocr_json)))
    return report


def main() -> None:
    """Run on data/raw/pdf and data/raw/txt; save a UTF-8 JSON report."""
    pdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/pdf")
    txt_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/raw/txt")
    report = [diagnose(p, txt_dir) for p in sorted(pdf_dir.glob("*.pdf"))]
    out = Path("data/processed/legal_corpus/pua_diagnosis.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    for r in report:
        print(f"\n== {str(r['file'])[:45]}  pua={r['pua_chars']} {r['pua_blocks_top5']}")
        print(f"   raw      {r['raw']}")
        for cp, s in r["decoded"].items():  # type: ignore[attr-defined]
            print(f"   {cp:<9}{s}")
        print(f"   ocr_json {r.get('ocr_json', 'absent')}")
    print(f"\nRapport complet : {out}")


if __name__ == "__main__":
    main()
