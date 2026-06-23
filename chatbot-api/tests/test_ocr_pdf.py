"""
OCR Test — Dump toàn bộ nội dung ra file MD
=============================================
Cách chạy:

  # Chỉ định file cụ thể:
  python -m tests.test_ocr_pdf tests/file_test/test_tailieukythuat.pdf

  # Hoặc tên file thôi (tự tìm trong tests/file_test/):
  python -m tests.test_ocr_pdf test_tailieukythuat.pdf

  # Không truyền gì → liệt kê file có sẵn để chọn:
  python -m tests.test_ocr_pdf
"""

import asyncio, sys, time, tempfile, os
from pathlib import Path

ROOT = Path(__file__).parent.parent
FILE_DIR = ROOT / "tests" / "file_test"
SUPPORTED = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff"}


def resolve_input() -> Path:
    """Resolve input file từ arg hoặc hỏi user chọn."""
    if len(sys.argv) > 1:
        arg = Path(sys.argv[1])
        # Nếu chỉ là tên file, tìm trong FILE_DIR
        if not arg.is_absolute() and not arg.exists():
            candidate = FILE_DIR / arg.name
            if candidate.exists():
                return candidate
        if arg.exists():
            return arg
        print(f"[ERROR] Không tìm thấy file: {arg}")
        sys.exit(1)

    # Không truyền arg → liệt kê file để chọn
    files = sorted(f for f in FILE_DIR.iterdir() if f.suffix.lower() in SUPPORTED)
    if not files:
        print(f"[ERROR] Không có file nào trong {FILE_DIR}")
        sys.exit(1)

    print(f"\nCác file trong {FILE_DIR}:\n")
    for i, f in enumerate(files, 1):
        size_kb = f.stat().st_size / 1024
        print(f"  [{i}] {f.name}  ({size_kb:.0f} KB)")

    print()
    while True:
        choice = input("Chọn số thứ tự file (Enter = 1): ").strip()
        if choice == "":
            return files[0]
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return files[int(choice) - 1]
        print("  → Nhập số hợp lệ.")


async def main() -> None:
    pdf_path = resolve_input()
    output_md = FILE_DIR / (pdf_path.stem + "_ocr_result.md")

    print(f"\nFile  : {pdf_path}")
    print(f"Output: {output_md}")
    print("Đang load Docling + EasyOCR... (lần đầu ~30-90s)\n")

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(
                    do_ocr=True,
                    force_full_page_ocr=True,
                    ocr_options=EasyOcrOptions(lang=["vi", "en"]),
                    do_table_structure=True,
                )
            )
        }
    )

    file_bytes = pdf_path.read_bytes()
    with tempfile.NamedTemporaryFile(suffix=pdf_path.suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    print("Đang OCR...")
    t0 = time.time()
    try:
        result = await asyncio.to_thread(converter.convert, tmp_path)
    finally:
        os.unlink(tmp_path)

    elapsed = time.time() - t0
    md = result.document.export_to_markdown()
    output_md.write_text(md, encoding="utf-8")

    print(f"✅ OCR xong sau {elapsed:.1f}s — {len(md):,} ký tự")
    print(f"   Đã lưu: {output_md}")


if __name__ == "__main__":
    asyncio.run(main())
