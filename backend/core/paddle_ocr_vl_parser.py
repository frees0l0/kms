"""
PaddleOCR-VL document parser using Baidu Cloud API.
"""

import base64
import time
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from core.document_parser import DocumentParser

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

    def _build_chunks(self, markdown_content: str, file_extension: str) -> List[Dict[str, Any]]:
        """Parse markdown content, add markers, chunk, and return in DocumentParser format."""
        plain_text = self._markdown_to_text(markdown_content)

        if file_extension == ".pdf":
            marked_text = self._add_page_markers(plain_text)
        else:
            marked_text = self._add_paragraph_markers(plain_text)

        text_chunks = self._chunk_text(marked_text)

        logger.info(f"PaddleOCR-VL parsed into {len(text_chunks)} chunks")
        chunks = []
        for i, chunk_text in enumerate(text_chunks, 1):
            if file_extension == ".pdf":
                page_match = re.search(r"\[Page (\d+)\]", chunk_text)
                page = int(page_match.group(1)) if page_match else 1
                clean_content = re.sub(r"\[Page \d+\]\n?", "", chunk_text).strip()
                chunks.append({
                    "content": clean_content,
                    "metadata": {
                        "page": page,
                        "chunk_index": i,
                        "source": "pdf"
                    }
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
        """Convert markdown to plain text."""
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
        text = text.strip()
        return text

    def _add_page_markers(self, text: str) -> str:
        """Try to detect page boundaries in the text."""
        if re.search(r"---.*?---", text, re.DOTALL):
            pages = re.split(r"(?=\n---\n)", text)
            if len(pages) > 1:
                return "\n\n".join(
                    f"[Page {i}]\n{page.strip()}" for i, page in enumerate(pages, 1)
                )
        return f"[Page 1]\n{text}"

    def _add_paragraph_markers(self, text: str) -> str:
        """Split text into paragraphs and add markers."""
        paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
        if not paragraphs:
            return text
        return "\n\n".join(
            f"[Para {i}]\n{p}" for i, p in enumerate(paragraphs, 1)
        )
