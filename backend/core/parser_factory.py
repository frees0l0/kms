"""
Factory for getting the appropriate document parser.
"""

import logging

from core.document_parser import DocumentParser

logger = logging.getLogger("kms.parser_factory")


def get_document_parser() -> "DocumentParser":
    """Return appropriate parser based on settings.

    Priority: MinerU > PaddleOCR-VL > DocumentParser.
    """
    from core.config import settings
    if settings.mineru_api_token:
        from core.mineru_parser import MinerUParser
        logger.info("Using MinerU parser")
        return MinerUParser(api_token=settings.mineru_api_token)
    if settings.paddle_ocr_vl_api_token:
        from core.paddle_ocr_vl_parser import PaddleOCRVLParser
        logger.info("Using PaddleOCR-VL parser")
        return PaddleOCRVLParser(api_token=settings.paddle_ocr_vl_api_token)
    return DocumentParser()
