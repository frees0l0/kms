"""
Document parser for PDF and DOCX files with chunking.
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError as exc:
    raise ImportError("pypdf is required for PDF parsing. Install with: pip install pypdf") from exc

class DocumentParser:
    """Parses PDF and DOCX documents into chunks."""

    # Chunking configuration
    CHUNK_SIZE = 500  # tokens (approximate)
    CHUNK_OVERLAP = 50  # tokens

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or self.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or self.CHUNK_OVERLAP

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse a document and return chunks.
        Supports PDF and DOCX files.
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == ".pdf":
            return self._parse_pdf(file_path)
        elif extension == ".docx":
            return self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    def _parse_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse PDF file and extract text with page info."""
        chunks = []
        reader = PdfReader(file_path)

        full_text = []
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text.append(f"[Page {page_num + 1}]\n{text}")

        combined_text = "\n\n".join(full_text)
        text_chunks = self._chunk_text(combined_text)

        for i, chunk_text in enumerate(text_chunks, 1):
            # Determine which page this chunk is from
            page_match = re.search(r'\[Page (\d+)\]', chunk_text)
            page = int(page_match.group(1)) if page_match else 1

            # Clean up page markers from content
            clean_content = re.sub(r'\[Page \d+\]\n?', '', chunk_text).strip()

            chunks.append({
                "content": clean_content,
                "metadata": {
                    "page": page,
                    "chunk_index": i,
                    "source": "pdf"
                }
            })

        return chunks

    def _parse_docx(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse DOCX file and extract text with paragraph info."""
        try:
            from docx import Document
        except ImportError as exc:
            raise ImportError("python-docx is required for DOCX parsing. Install with: pip install python-docx") from exc

        doc = Document(file_path)
        chunks = []

        # Extract paragraphs with their indices
        paragraphs = []
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                paragraphs.append((i, text))

        # Build full text and chunk
        full_text = "\n\n".join([f"[Para {idx}] {text}" for idx, text in paragraphs])
        text_chunks = self._chunk_text(full_text)

        for i, chunk_text in enumerate(text_chunks):
            # Determine paragraph range
            para_matches = re.findall(r'\[Para (\d+)\]', chunk_text)
            if para_matches:
                start_para = min(int(p) for p in para_matches)
                end_para = max(int(p) for p in para_matches)
                para_range = f"{start_para}-{end_para}"
            else:
                para_range = "unknown"

            # Clean up markers
            clean_content = re.sub(r'\[Para \d+\]', '', chunk_text).strip()

            chunks.append({
                "content": clean_content,
                "metadata": {
                    "paragraph_range": para_range,
                    "chunk_index": i,
                    "source": "docx"
                }
            })

        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        Supports both English (whitespace split) and CJK (character split).
        """
        # For CJK text, split by character; otherwise by whitespace
        is_cjk = bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text))
        if is_cjk:
            # CJK: split each character into list elements
            tokens = list(text)
        else:
            tokens = text.split()

        chunks = []

        if not tokens:
            return chunks

        # Estimate tokens (rough: 1 token ~ 4 chars)
        chunk_size = self.chunk_size * 4 // 5
        overlap_size = self.chunk_overlap * 4 // 5

        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk = ("".join(tokens[start:end]) if is_cjk else " ".join(tokens[start:end]))
            chunks.append(chunk)

            # Move start with overlap
            start = end - overlap_size
            if start >= len(tokens) - overlap_size:
                break

        return chunks
