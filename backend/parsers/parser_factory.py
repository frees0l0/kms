"""
Factory for getting the appropriate document parser.
"""

import logging

from parsers.document_parser import DocumentParser

logger = logging.getLogger("kms.parser_factory")

_parser_cache: DocumentParser | None = None


def get_document_parser() -> "DocumentParser":
    """Return appropriate parser based on settings.

    Priority: MinerU > PaddleOCR-VL > DocumentParser.
    Result is cached for reuse.
    """
    global _parser_cache
    if _parser_cache is not None:
        return _parser_cache

    from core.config import settings
    if settings.mineru_api_token:
        from parsers.mineru_parser import MinerUParser
        logger.info("Using MinerU parser")
        _parser_cache = MinerUParser(api_token=settings.mineru_api_token)
    elif settings.paddle_ocr_vl_api_token:
        from parsers.paddle_ocr_vl_parser import PaddleOCRVLParser
        logger.info("Using PaddleOCR-VL parser")
        _parser_cache = PaddleOCRVLParser(api_token=settings.paddle_ocr_vl_api_token)
    else:
        _parser_cache = DocumentParser()
    return _parser_cache
