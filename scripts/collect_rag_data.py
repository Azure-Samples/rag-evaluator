"""Automated RAG data collection script.

Reads test questions (+ optional ground truth) from a CSV file, calls your
RAG API for each question, captures the response and retrieved contexts,
and writes a JSONL evaluation dataset ready for consumption by the framework.

Usage
-----
    python scripts/collect_rag_data.py \\
        --questions datasets/hr-rag/questions.csv \\
        --output datasets/hr-rag/eval.jsonl \\
        --adapter http \\
        --rag-url http://localhost:8000/api/chat

Adapters
--------
The script ships with several built-in adapters:

* ``http`` — generic REST endpoint (JSON request/response).
* ``azure_chat_stream`` — Azure-style chat completion endpoints that
  return NDJSON streaming (``application/json-lines``).  Covers RAG
  chatbots built with Azure AI that stream responses.
* ``azure_agent`` — placeholder for Azure AI Foundry Agent API.

Implement your own by subclassing ``RagAdapter`` and registering it
in ``ADAPTER_REGISTRY``.

CSV format
----------
The input CSV must have a ``question`` column.  Optional columns:

    id, ground_truth_answer, metadata_*

Columns prefixed with ``metadata_`` are packed into the record's
``metadata`` dict (e.g. ``metadata_scenario`` → ``{"scenario": "..."}``)
"""

from __future__ import annotations

import abc
import argparse
import csv
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RagResponse:
    """Structured response from a RAG system."""

    response: str
    contexts: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------


class RagAdapter(abc.ABC):
    """Abstract base for RAG system adapters.

    Subclass this and implement ``query()`` to integrate with any backend.
    """

    @abc.abstractmethod
    def query(self, question: str, **kwargs: Any) -> RagResponse:
        """Send a question to the RAG system and return the response."""

    def setup(self, args: argparse.Namespace) -> None:
        """Optional one-time setup (called before the first query)."""


# ---------------------------------------------------------------------------
# Built-in adapters
# ---------------------------------------------------------------------------


class HttpAdapter(RagAdapter):
    """Generic HTTP adapter — POST ``{"question": ...}`` to a REST endpoint.

    Expected JSON response format::

        {
            "response": "The answer...",
            "contexts": ["chunk 1", "chunk 2"]
        }

    Customise the field names via ``--response-field`` and ``--contexts-field``.
    """

    def setup(self, args: argparse.Namespace) -> None:
        try:
            import requests  # noqa: F401
        except ImportError:
            logger.error("Install 'requests' to use the HTTP adapter:  pip install requests")
            sys.exit(1)
        self._url: str = args.rag_url
        self._response_field: str = args.response_field
        self._contexts_field: str = args.contexts_field
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if args.rag_api_key:
            self._headers["Authorization"] = f"Bearer {args.rag_api_key}"
        self._timeout: int = args.request_timeout
        logger.info("HttpAdapter configured → %s", self._url)

    def query(self, question: str, **kwargs: Any) -> RagResponse:
        import requests

        payload = {"question": question, **kwargs}
        resp = requests.post(
            self._url,
            json=payload,
            headers=self._headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        return RagResponse(
            response=str(data.get(self._response_field, "")),
            contexts=data.get(self._contexts_field, []),
            raw=data,
        )


class AzureChatStreamAdapter(RagAdapter):
    """Adapter for Azure-style chat completion endpoints with NDJSON streaming.

    Handles endpoints that:

    * Accept ``{"messages": [{"role": "user", "content": "..."}]}``
    * Return ``application/json-lines`` (NDJSON) where:
        - Line 0: ``role=tool`` → contains a ``citations`` array.
        - Lines 1-N: ``role=assistant`` → token-by-token answer chunks.

    This covers RAG chatbots built with Azure AI that stream
    NDJSON responses.

    Usage::

        python scripts/collect_rag_data.py \\
            --adapter azure_chat_stream \\
            --rag-url http://localhost:8000/conversation \\
            --questions datasets/my-project/questions.csv \\
            --output datasets/my-project/eval.jsonl
    """

    def setup(self, args: argparse.Namespace) -> None:
        try:
            import requests  # noqa: F401
        except ImportError:
            logger.error("Install 'requests' to use this adapter:  pip install requests")
            sys.exit(1)
        self._url: str = args.rag_url
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if args.rag_api_key:
            self._headers["Authorization"] = f"Bearer {args.rag_api_key}"
        self._timeout: int = args.request_timeout
        logger.info("AzureChatStreamAdapter configured → %s", self._url)

    def query(self, question: str, **kwargs: Any) -> RagResponse:
        import requests

        payload = {"messages": [{"role": "user", "content": question}]}
        resp = requests.post(
            self._url,
            json=payload,
            headers=self._headers,
            timeout=self._timeout,
            stream=True,
        )
        resp.raise_for_status()

        full_answer = ""
        contexts: list[str] = []
        raw_citations: list[dict] = []

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.strip():
                continue

            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON line: %s", raw_line[:120])
                continue

            for choice in obj.get("choices", []):
                for msg in choice.get("messages", []):
                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    if role == "tool" and content:
                        try:
                            tool_data = json.loads(content)
                            for citation in tool_data.get("citations", []):
                                ctx_text = citation.get("content", "").strip()
                                if ctx_text:
                                    contexts.append(ctx_text)
                                    raw_citations.append(citation)
                        except json.JSONDecodeError:
                            pass

                    elif role == "assistant":
                        full_answer += content

        return RagResponse(
            response=full_answer.strip(),
            contexts=contexts,
            raw={"citations": raw_citations},
        )


class AzureAgentAdapter(RagAdapter):
    """Placeholder adapter for Azure AI Foundry Agent / Assistant API.

    Replace the ``query()`` body with your actual agent invocation logic.
    """

    def setup(self, args: argparse.Namespace) -> None:
        self._endpoint: str = args.rag_url
        logger.info("AzureAgentAdapter configured → %s", self._endpoint)

    def query(self, question: str, **kwargs: Any) -> RagResponse:
        # TODO: Replace with your Azure Agent SDK call, e.g.:
        #
        #   from azure.ai.projects import AIProjectClient
        #   client = AIProjectClient(...)
        #   thread = client.agents.create_thread()
        #   client.agents.create_message(thread.id, role="user", content=question)
        #   run = client.agents.create_and_process_run(thread.id, agent_id=...)
        #   messages = client.agents.list_messages(thread.id)
        #   response_text = messages.data[0].content[0].text.value
        #   contexts = [cite.text for cite in messages.data[0].content[0].text.annotations]
        #
        raise NotImplementedError(
            "AzureAgentAdapter.query() is a placeholder. "
            "Implement it with your Azure Agent SDK calls."
        )


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: dict[str, type[RagAdapter]] = {
    "http": HttpAdapter,
    "azure_chat_stream": AzureChatStreamAdapter,
    "azure_agent": AzureAgentAdapter,
}


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------


def load_questions(csv_path: Path) -> list[dict[str, Any]]:
    """Read questions CSV and return a list of dicts.

    Required column : ``question``
    Optional columns: ``id``, ``ground_truth_answer``, ``metadata_*``
    """
    if not csv_path.exists():
        logger.error("Questions file not found: %s", csv_path)
        sys.exit(1)

    rows: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "question" not in (reader.fieldnames or []):
            logger.error("CSV must have a 'question' column. Found: %s", reader.fieldnames)
            sys.exit(1)

        for idx, row in enumerate(reader, start=1):
            question = row.get("question", "").strip()
            if not question:
                logger.warning("Row %d: empty question — skipping.", idx)
                continue

            record: dict[str, Any] = {
                "id": row.get("id", f"q-{idx:04d}").strip(),
                "question": question,
                "ground_truth_answer": row.get("ground_truth_answer", "").strip(),
            }

            # Pack metadata_* columns
            metadata: dict[str, str] = {}
            for key, value in row.items():
                if key.startswith("metadata_") and value:
                    meta_key = key[len("metadata_"):]
                    metadata[meta_key] = value.strip()
            record["metadata"] = metadata

            rows.append(record)

    logger.info("Loaded %d questions from %s", len(rows), csv_path)
    return rows


# ---------------------------------------------------------------------------
# Collection loop
# ---------------------------------------------------------------------------


def collect(
    adapter: RagAdapter,
    questions: list[dict[str, Any]],
    output_path: Path,
    delay: float = 0.0,
) -> None:
    """Query the RAG system for each question and write the JSONL output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    errors = 0

    with output_path.open("w", encoding="utf-8") as f:
        for i, q in enumerate(questions, start=1):
            question_text = q["question"]
            logger.info("[%d/%d] %s", i, len(questions), question_text[:80])

            try:
                rag_resp = adapter.query(question_text)
            except Exception as exc:
                logger.error("  Error: %s", exc)
                errors += 1
                # Write a record with empty response so the evaluator can still score it
                record = {
                    "id": q["id"],
                    "question": question_text,
                    "response": "",
                    "contexts": [],
                    "ground_truth_answer": q.get("ground_truth_answer", ""),
                    "metadata": {**q.get("metadata", {}), "collection_error": str(exc)},
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                continue

            record = {
                "id": q["id"],
                "question": question_text,
                "response": rag_resp.response,
                "contexts": rag_resp.contexts,
                "ground_truth_answer": q.get("ground_truth_answer", ""),
                "metadata": q.get("metadata", {}),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            success += 1

            if delay > 0:
                time.sleep(delay)

    logger.info(
        "Done — %d succeeded, %d errors.  Dataset written to %s",
        success,
        errors,
        output_path,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Collect RAG evaluation data by querying your RAG system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--questions", required=True, type=Path,
        help="Path to CSV file with test questions (must have a 'question' column).",
    )
    p.add_argument(
        "--output", required=True, type=Path,
        help="Output JSONL file path (e.g. datasets/my-project/eval.jsonl).",
    )
    p.add_argument(
        "--adapter", default="http", choices=sorted(ADAPTER_REGISTRY),
        help="RAG adapter to use (default: http).",
    )
    p.add_argument(
        "--rag-url", default="http://localhost:8000/api/chat",
        help="RAG API endpoint URL.",
    )
    p.add_argument(
        "--rag-api-key", default="",
        help="Optional Bearer token / API key for the RAG endpoint.",
    )
    p.add_argument(
        "--response-field", default="response",
        help="JSON field name for the RAG answer (default: response).",
    )
    p.add_argument(
        "--contexts-field", default="contexts",
        help="JSON field name for retrieved contexts (default: contexts).",
    )
    p.add_argument(
        "--request-timeout", type=int, default=60,
        help="HTTP request timeout in seconds (default: 60).",
    )
    p.add_argument(
        "--delay", type=float, default=0.0,
        help="Delay between requests in seconds (for rate limiting).",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Build adapter
    adapter_cls = ADAPTER_REGISTRY[args.adapter]
    adapter = adapter_cls()
    adapter.setup(args)

    # Load questions
    questions = load_questions(args.questions)
    if not questions:
        logger.error("No questions loaded — exiting.")
        sys.exit(1)

    # Collect data
    collect(adapter, questions, args.output, delay=args.delay)


if __name__ == "__main__":
    main()
