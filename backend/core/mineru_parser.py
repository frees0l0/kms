"""
MinerU document parser using the MinerU API.
"""

import io
import zipfile
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from core.document_parser import DocumentParser

logger = logging.getLogger("kms.mineru")


class MinerUParser(DocumentParser):
    """Parses PDF and DOCX documents using MinerU API."""

    BATCH_SUBMIT_URL = "https://mineru.net/api/v4/file-urls/batch"
    BATCH_RESULT_URL = "https://mineru.net/api/v4/extract-results/batch"
    POLL_INTERVAL = 5.0  # seconds
    MAX_POLL_ATTEMPTS = 60

    def __init__(
        self,
        api_token: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.api_token = api_token

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse document via MinerU API and return chunks."""
        path = Path(file_path)
        extension = path.suffix.lower()
        if extension not in (".pdf", ".docx"):
            raise ValueError(f"Unsupported file format: {extension}")

        with open(file_path, "rb") as f:
            file_data = f.read()

        logger.info(f"MinerU parsing started: file={path.name}, size={len(file_data)} bytes")

        # Step 1: Submit batch to get presigned upload URL
        batch_id, presigned_url = self._submit_batch(path.name)

        # Step 2: PUT file to presigned URL
        self._upload_file(presigned_url, file_data)

        # Step 3: Poll for results, download ZIP, extract markdown
        markdown_content = self._poll_for_results(batch_id, path.name)

        # Step 4: Build chunks
        return self._build_chunks(markdown_content, extension)

    def _submit_batch(self, file_name: str) -> tuple[str, str]:
        """Submit batch upload, return (batch_id, presigned_url)."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "files": [{"name": file_name, "data_id": file_name}],
            "model_version": "vlm",
            "enable_formula": True,
            "enable_table": True,
            "language": "ch"
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(self.BATCH_SUBMIT_URL, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()

        if result.get("code") != 0:
            raise RuntimeError(
                f"MinerU batch submit failed: code={result.get('code')}, msg={result.get('msg')}"
            )

        data = result.get("data", {})
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls", [])
        if not batch_id or not file_urls:
            raise RuntimeError(
                f"MinerU batch submit returned no batch_id or file_urls: {result}"
            )

        logger.info(f"MinerU batch submitted: batch_id={batch_id}")
        return batch_id, file_urls[0]

    def _upload_file(self, presigned_url: str, file_data: bytes) -> None:
        """PUT file to MinerU presigned URL. No Content-Type header."""
        with httpx.Client(timeout=120.0) as client:
            resp = client.put(presigned_url, content=file_data)
            resp.raise_for_status()
        logger.info(f"MinerU file uploaded: {len(file_data)} bytes")

    def _poll_for_results(self, batch_id: str, file_name: str) -> str:
        """Poll until done, then download ZIP and extract full.md."""
        url = f"{self.BATCH_RESULT_URL}/{batch_id}"
        headers = {"Authorization": f"Bearer {self.api_token}"}

        for attempt in range(self.MAX_POLL_ATTEMPTS):
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                result = resp.json()

            if result.get("code") != 0:
                raise RuntimeError(
                    f"MinerU result query failed: code={result.get('code')}, "
                    f"msg={result.get('msg')}"
                )

            extract_results = result.get("data", {}).get("extract_result", [])
            file_result = next(
                (r for r in extract_results if r.get("file_name") == file_name), None
            )

            if not file_result:
                raise RuntimeError(
                    f"MinerU result missing file {file_name}: {extract_results}"
                )

            state = file_result.get("state")

            if state == "done":
                logger.info(f"MinerU task {batch_id} completed successfully")
                zip_url = file_result.get("full_zip_url")
                return self._download_and_extract_markdown(zip_url)

            if state == "failed":
                task_error = file_result.get("error", "unknown")
                logger.error(f"MinerU task {batch_id} failed: {task_error}")
                raise RuntimeError(f"MinerU task failed: {task_error}")

            logger.info(
                f"MinerU task {batch_id} state={state}, "
                f"attempt {attempt + 1}/{self.MAX_POLL_ATTEMPTS}"
            )
            time.sleep(self.POLL_INTERVAL)

        logger.error(
            f"MinerU task {batch_id} timed out after {self.MAX_POLL_ATTEMPTS} polls"
        )
        raise RuntimeError(
            f"MinerU task {batch_id} timed out after {self.MAX_POLL_ATTEMPTS} polls"
        )

    def _download_and_extract_markdown(self, zip_url: str) -> str:
        """Download ZIP from url and extract full.md content."""
        with httpx.Client(timeout=120.0) as client:
            zip_resp = client.get(zip_url)
            zip_resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            if "full.md" in zf.namelist():
                return zf.read("full.md").decode("utf-8")
            # Fallback: try other common names
            for name in zf.namelist():
                if name.endswith(".md") and "full" in name.lower():
                    return zf.read(name).decode("utf-8")
            raise RuntimeError(
                f"MinerU ZIP does not contain full.md. Contents: {zf.namelist()}"
            )

    def _build_chunks(
        self, markdown_content: str, file_extension: str
    ) -> List[Dict[str, Any]]:
        """Parse markdown, add markers, chunk, and return in DocumentParser format."""
        plain_text = self._markdown_to_text(markdown_content)

        if file_extension == ".pdf":
            marked_text = self._add_page_markers(plain_text)
        else:
            marked_text = self._add_paragraph_markers(plain_text)

        text_chunks = self._chunk_text(marked_text)

        logger.info(f"MinerU parsed into {len(text_chunks)} chunks")

        chunks = []
        for i, chunk_text in enumerate(text_chunks, 1):
            if file_extension == ".pdf":
                page_match = re.search(r"\[Page (\d+)\]", chunk_text)
                page = int(page_match.group(1)) if page_match else 1
                clean_content = re.sub(r"\[Page \d+\]\n?", "", chunk_text).strip()
                chunks.append({
                    "content": clean_content,
                    "metadata": {"page": page, "chunk_index": i, "source": "pdf"}
                })
            else:
                para_matches = re.findall(r"\[Para (\d+)\]", chunk_text)
                if para_matches:
                    start_para = min(int(p) for p in para_matches)
                    end_para = max(int(p) for p in para_matches)
                    para_range = f"{start_para}-{end_para}"
                else:
                    para_range = "unknown"
                clean_content = re.sub(r"\[Para \d+\]", "", chunk_text).strip()
                chunks.append({
                    "content": clean_content,
                    "metadata": {
                        "paragraph_range": para_range,
                        "chunk_index": i,
                        "source": "docx"
                    }
                })
        return chunks

    def _markdown_to_text(self, markdown: str) -> str:
        """Strip markdown syntax to plain text."""
        text = re.sub(r"!\[.*?\]\(.*?\)", "", markdown)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)
        return text.strip()

    def _add_page_markers(self, text: str) -> str:
        """Detect page boundaries, mark with [Page N]."""
        if re.search(r"---.*?---", text, re.DOTALL):
            pages = re.split(r"(?=\n---\n)", text)
            if len(pages) > 1:
                return "\n\n".join(
                    f"[Page {i}]\n{page.strip()}"
                    for i, page in enumerate(pages, 1)
                )
        return f"[Page 1]\n{text}"

    def _add_paragraph_markers(self, text: str) -> str:
        """Split text into paragraphs, mark with [Para N]."""
        paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
        if not paragraphs:
            return text
        return "\n\n".join(
            f"[Para {i}]\n{p}" for i, p in enumerate(paragraphs, 1)
        )
