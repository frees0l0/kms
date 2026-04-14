"""
PaddleOCR-VL document parser using Baidu Cloud API.
"""

import base64
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from parsers.document_parser import DocumentParser

logger = logging.getLogger("kms.paddle_ocr")


class PaddleOCRVLParser(DocumentParser):
    """Parses PDF and DOCX documents using PaddleOCR-VL API."""

    SUBMIT_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task"
    QUERY_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"
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
        """
        Parse document via PaddleOCR-VL API and return chunks.
        Uses async submit/poll pattern: submit task, poll for completion, fetch results.
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension not in (".pdf", ".docx"):
            raise ValueError(f"Unsupported file format: {extension}")

        # Read and base64-encode file
        with open(file_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode("utf-8")

        file_name = path.name

        # Submit parsing task
        logger.info(f"PaddleOCR-VL parsing started: file={file_name}, size={len(file_data)} bytes")
        task_id = self._submit_task(file_data, file_name)

        # Poll for results
        markdown_content = self._poll_for_results(task_id)

        # Build chunks with page/paragraph markers
        return self._build_chunks(markdown_content, extension)

    def _submit_task(self, file_data: str, file_name: str) -> str:
        """Submit document parsing task and return task_id."""
        url = f"{self.SUBMIT_URL}?access_token={self.api_token}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "file_data": file_data,
            "file_name": file_name,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, data=data)
            resp.raise_for_status()
            result = resp.json()

        if result.get("error_code") != 0:
            raise RuntimeError(
                f"PaddleOCR-VL submit failed: error_code={result.get('error_code')}, "
                f"error_msg={result.get('error_msg')}"
            )

        task_id = result.get("result", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"PaddleOCR-VL submit returned no task_id: {result}")

        logger.info(f"PaddleOCR-VL task submitted: task_id={task_id}")
        return task_id

    def _poll_for_results(self, task_id: str) -> str:
        """Poll until task completes, then return markdown content."""
        url = f"{self.QUERY_URL}?access_token={self.api_token}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"task_id": task_id}

        for attempt in range(self.MAX_POLL_ATTEMPTS):
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, headers=headers, data=data)
                resp.raise_for_status()
                result = resp.json()

            if result.get("error_code") != 0:
                raise RuntimeError(
                    f"PaddleOCR-VL query failed: error_code={result.get('error_code')}, "
                    f"error_msg={result.get('error_msg')}"
                )

            status = result.get("result", {}).get("status")

            if status == "success":
                logger.info(f"PaddleOCR-VL task {task_id} completed successfully")
                markdown_url = result.get("result", {}).get("markdown_url")
                if markdown_url:
                    with httpx.Client(timeout=60.0) as client:
                        content_resp = client.get(markdown_url)
                        content_resp.raise_for_status()
                        return content_resp.text
                parse_result_url = result.get("result", {}).get("parse_result_url")
                if parse_result_url:
                    with httpx.Client(timeout=60.0) as client:
                        content_resp = client.get(parse_result_url)
                        content_resp.raise_for_status()
                        return self._extract_text_from_json(content_resp.json())

                raise RuntimeError(
                    f"PaddleOCR-VL success but no result URL: {result}"
                )

            if status == "failed":
                task_error = result.get("result", {}).get("task_error")
                logger.error(f"PaddleOCR-VL task {task_id} failed: {task_error}")
                raise RuntimeError(f"PaddleOCR-VL task failed: {task_error}")

            logger.info(
                f"PaddleOCR-VL task {task_id} status={status}, "
                f"attempt {attempt + 1}/{self.MAX_POLL_ATTEMPTS}"
            )
            time.sleep(self.POLL_INTERVAL)

        logger.error(f"PaddleOCR-VL task {task_id} timed out after {self.MAX_POLL_ATTEMPTS} polls")
        raise RuntimeError(
            f"PaddleOCR-VL task {task_id} timed out after {self.MAX_POLL_ATTEMPTS} polls"
        )

    def _extract_text_from_json(self, parse_result: dict) -> str:
        """Extract text content from parse_result JSON structure."""
        pages = parse_result.get("pages", [])
        texts = []
        for i, page in enumerate(pages, 1):
            page_text = page.get("text", "")
            if page_text:
                texts.append(f"[Page {i}]\n{page_text}")
        return "\n\n".join(texts)
