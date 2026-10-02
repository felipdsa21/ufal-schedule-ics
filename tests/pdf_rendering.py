import pymupdf


def render_pdf(
    html: str,
    css: str | None = None,
    *,
    width: int = 560,
    height: int = 800,
    margin: int = 36,
) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    rect = pymupdf.Rect(margin, margin, width - margin, height - margin)
    page.insert_htmlbox(rect, html, css=css)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
