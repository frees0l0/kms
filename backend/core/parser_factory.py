"""
Factory for getting the appropriate document parser.
"""

from core.document_parser import DocumentParser


def get_document_parser() -> "DocumentParser":
    """Return appropriate parser based on settings.

    Uses PaddleOCR-VL API when PADDLE_OCR_VL_API_TOKEN is set,
    otherwise falls back to the local DocumentParser.
    """
    from core.config import settings
    if settings.paddle_ocr_vl_api_token:
        from core.paddle_ocr_vl_parser import PaddleOCRVLParser
        return PaddleOCRVLParser(api_token=settings.paddle_ocr_vl_api_token)
    return DocumentParser()
