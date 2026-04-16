"""
CLI test script for process_query.
Usage: python -m tests.test_cli "query text" [source] [chat_id]
"""

import asyncio
import sys
import logging

sys.path.insert(0, "backend")

from utils.logging import setup_logging
from core.orchestrator import process_query


async def main():
    setup_logging(logging.DEBUG)

    args = sys.argv[1:]
    if len(args) < 1:
        print("Usage: python -m tests.test_cli <query> [source] [chat_id]")
        print("  source: 'telegram' or 'teams' (default: telegram)")
        print("  chat_id: arbitrary string (default: cli)")
        sys.exit(1)

    query_text = args[0]
    source = args[1] if len(args) > 1 else "cli"
    chat_id = args[2] if len(args) > 2 else "admin"

    print(f"\n--- Processing query ---")
    print(f"Query: {query_text}")
    print(f"Source: {source}")
    print(f"Chat ID: {chat_id}\n")

    result = await process_query(query_text, source, chat_id)

    print(f"\n--- Result ---")
    print(f"Response: {result['response']}")
    print(f"Intent: {result['intent_name']} (id={result['intent_id']})")
    print(f"Confidence: {result['confidence']}")
    print(f"Document ID: {result['document_id']}")
    print(f"Response time: {result['response_time_ms']}ms")


if __name__ == "__main__":
    asyncio.run(main())
