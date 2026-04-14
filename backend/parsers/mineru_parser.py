"""
MinerU document parser using the MinerU API.
"""

import io
import zipfile
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from parsers.document_parser import DocumentParser

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
            "enable_table": True
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
