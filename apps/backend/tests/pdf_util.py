"""Generate a real, valid PDF for tests using pypdf's writer."""

from __future__ import annotations

from pypdf import PdfWriter


def make_pdf(text: str = "Machine learning is a branch of AI.") -> bytes:
    """Create a minimal valid PDF. pypdf can write but not easily add text, so
    we assemble a valid content stream with correct offsets."""
    # Build objects.
    objs: list[bytes] = []

    def obj(n: int, body: bytes) -> None:
        objs.append(b"%d 0 obj\n" % n + body + b"\nendobj\n")

    stream = b"BT /F1 12 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
    obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    obj(
        3,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    )
    obj(4, b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for o in objs:
        offsets.append(len(out))
        out += o
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += b"trailer << /Root 1 0 R /Size %d >>\n" % (len(objs) + 1)
    out += b"startxref\n%d\n%%%%EOF" % xref_pos
    return bytes(out)


def _unused():
    PdfWriter()
