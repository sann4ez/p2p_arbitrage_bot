import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from config import Config


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
KNOWLEDGE_BASE_DIR = Path("knowledge_base")
MAX_QUESTION_CHARS = 800
MAX_CHUNK_CHARS = 2500
MAX_CONTEXT_CHARS = 12000
MAX_CONTEXT_CHUNKS = 6
MIN_RELEVANCE_SCORE = 2
RELATIVE_RELEVANCE_THRESHOLD = 0.5
OPENAI_KNOWLEDGE_TIMEOUT = 60

STOP_WORDS = {
    "а",
    "або",
    "але",
    "без",
    "бо",
    "в",
    "ви",
    "від",
    "до",
    "для",
    "де",
    "є",
    "з",
    "за",
    "і",
    "й",
    "на",
    "не",
    "ну",
    "по",
    "про",
    "та",
    "то",
    "у",
    "це",
    "чи",
    "що",
    "як",
    "які",
    "яка",
    "яке",
    "який",
    "таке",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
}


@dataclass(frozen=True)
class KnowledgeChunk:
    file_name: str
    title: str
    text: str


@dataclass(frozen=True)
class KnowledgeAnswer:
    answer: str
    sources: list[str]


async def answer_p2p_knowledge_question(question: str) -> KnowledgeAnswer:
    normalized_question = normalize_question(question)

    if not normalized_question:
        return KnowledgeAnswer(
            answer="Напишіть питання по P2P базі знань.",
            sources=[],
        )

    chunks = load_knowledge_chunks()

    if not chunks:
        return KnowledgeAnswer(
            answer=(
                "База знань поки порожня. Додайте .md файли у папку "
                "knowledge_base і спробуйте ще раз."
            ),
            sources=[],
        )

    selected_chunks = select_relevant_chunks(normalized_question, chunks)

    if not selected_chunks:
        return KnowledgeAnswer(
            answer="Не знайшов релевантної інформації в базі знань.",
            sources=[],
        )

    if not Config.OPENAI_API_KEY:
        return KnowledgeAnswer(
            answer="OPENAI_API_KEY не налаштований, тому я не можу сформувати відповідь.",
            sources=list_sources(selected_chunks),
        )

    answer = await request_openai_answer(normalized_question, selected_chunks)

    if not answer:
        return KnowledgeAnswer(
            answer="Не вдалося отримати відповідь від OpenAI. Спробуйте ще раз пізніше.",
            sources=list_sources(selected_chunks),
        )

    return KnowledgeAnswer(
        answer=answer,
        sources=list_sources(selected_chunks),
    )


def normalize_question(question: str | None) -> str:
    if not question:
        return ""

    return " ".join(str(question).split())[:MAX_QUESTION_CHARS]


def load_knowledge_chunks() -> list[KnowledgeChunk]:
    if not KNOWLEDGE_BASE_DIR.exists():
        return []

    chunks = []

    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        if not path.is_file():
            continue

        text = read_markdown_file(path)

        if not text:
            continue

        chunks.extend(split_markdown_into_chunks(path.name, text))

    return chunks


def read_markdown_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        logger.exception("P2P knowledge file read failed: path=%s", path)
        return ""


def split_markdown_into_chunks(file_name: str, text: str) -> list[KnowledgeChunk]:
    chunks = []
    current_title = file_name
    current_lines = []

    for line in text.splitlines():
        if is_chunk_heading(line) and current_lines:
            chunks.extend(build_chunks(file_name, current_title, current_lines))
            current_lines = []

        if is_chunk_heading(line):
            current_title = line.lstrip("#").strip() or file_name

        current_lines.append(line)

    chunks.extend(build_chunks(file_name, current_title, current_lines))

    return chunks


def is_chunk_heading(line: str) -> bool:
    return bool(re.match(r"^\s*#{1,2}\s+", line))


def build_chunks(
    file_name: str,
    title: str,
    lines: list[str],
) -> list[KnowledgeChunk]:
    text = "\n".join(lines).strip()

    if not text:
        return []

    if len(text) <= MAX_CHUNK_CHARS:
        return [KnowledgeChunk(file_name=file_name, title=title, text=text)]

    result = []
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    buffer = []
    buffer_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)

        if buffer and buffer_length + paragraph_length + 2 > MAX_CHUNK_CHARS:
            result.append(
                KnowledgeChunk(
                    file_name=file_name,
                    title=title,
                    text="\n\n".join(buffer).strip(),
                )
            )
            buffer = []
            buffer_length = 0

        buffer.append(paragraph)
        buffer_length += paragraph_length + 2

    if buffer:
        result.append(
            KnowledgeChunk(
                file_name=file_name,
                title=title,
                text="\n\n".join(buffer).strip(),
            )
        )

    return result


def select_relevant_chunks(
    question: str,
    chunks: list[KnowledgeChunk],
) -> list[KnowledgeChunk]:
    question_terms = tokenize(question)
    min_matched_terms = 2 if len(question_terms) > 1 else 1
    scored = [
        (
            score_chunk(question, chunk),
            count_matched_terms(question_terms, chunk),
            index,
            chunk,
        )
        for index, chunk in enumerate(chunks)
    ]
    scored.sort(key=lambda item: (-item[0], item[2]))
    best_score = scored[0][0] if scored else 0
    min_score = max(
        MIN_RELEVANCE_SCORE,
        int(best_score * RELATIVE_RELEVANCE_THRESHOLD + 0.999),
    )
    selected = [
        (index, chunk)
        for score, matched_terms, index, chunk in scored
        if score >= min_score and matched_terms >= min_matched_terms
    ][:MAX_CONTEXT_CHUNKS]

    if not selected:
        selected = [
            (index, chunk)
            for score, _, index, chunk in scored
            if score >= min_score
        ][:MAX_CONTEXT_CHUNKS]

    selected_titles = {chunk.title for _, chunk in selected}

    if selected_titles:
        selected_indices = {index for index, _ in selected}

        for score, _, index, chunk in scored:
            if len(selected) >= MAX_CONTEXT_CHUNKS:
                break

            if index in selected_indices:
                continue

            if score > 0 and chunk.title in selected_titles:
                selected.append((index, chunk))
                selected_indices.add(index)

    if not selected and len(chunks) <= MAX_CONTEXT_CHUNKS:
        selected = list(enumerate(chunks))

    return [chunk for _, chunk in sorted(selected, key=lambda item: item[0])]


def score_chunk(question: str, chunk: KnowledgeChunk) -> int:
    question_terms = tokenize(question)

    if not question_terms:
        return 0

    text = f"{chunk.file_name} {chunk.title} {chunk.text}".lower()
    score = 0

    for term in question_terms:
        occurrences = text.count(term)

        if occurrences:
            score += min(occurrences, 5)

        if term in chunk.title.lower():
            score += 3

        if term in chunk.file_name.lower():
            score += 2

    return score


def count_matched_terms(question_terms: set[str], chunk: KnowledgeChunk) -> int:
    text = f"{chunk.file_name} {chunk.title} {chunk.text}".lower()
    return sum(1 for term in question_terms if term in text)


def tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w'’.-]+", value.lower(), flags=re.UNICODE)
        if len(token) > 2 and token not in STOP_WORDS
    }


async def request_openai_answer(
    question: str,
    chunks: list[KnowledgeChunk],
) -> str | None:
    payload = build_openai_payload(question, chunks)
    headers = {
        "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=OPENAI_KNOWLEDGE_TIMEOUT)
    started_at = time.monotonic()

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(OPENAI_RESPONSES_URL, json=payload) as response:
                if response.status >= 400:
                    body = await response.text()
                    logger.warning(
                        "P2P knowledge OpenAI request failed: status=%s body=%s",
                        response.status,
                        safe_snippet(body, 500),
                    )
                    return None

                data = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError):
        logger.exception("P2P knowledge OpenAI request failed")
        return None

    logger.info(
        "P2P knowledge OpenAI request done: chunks=%s elapsed=%.2fs",
        len(chunks),
        time.monotonic() - started_at,
    )

    return extract_output_text(data)


def build_openai_payload(question: str, chunks: list[KnowledgeChunk]) -> dict:
    return {
        "model": Config.OPENAI_P2P_MODEL,
        "store": False,
        "instructions": (
            "Ти асистент Telegram-бота для P2P навчання. "
            "Відповідай українською мовою. Використовуй тільки наданий контекст "
            "з бази знань. Якщо в контексті є транскрипт голосового або відео, "
            "вважай його повноцінним текстовим джерелом і відповідай за ним. "
            "Не радь слухати голосове чи дивитися відео, якщо відповідь уже є "
            "в транскрипті. Якщо в контексті немає відповіді, чесно скажи, що "
            "не знайшов це в базі знань. Не вигадуй фактів. Відповідь має бути "
            "практичною, структурованою і короткою. Відповідай тільки на поставлене "
            "питання; не додавай суміжні розділи, типи, категорії або загальні блоки, "
            "якщо користувач прямо про них не питав. Зазвичай давай 4-8 коротких "
            "пунктів; довшу відповідь давай тільки коли користувач прямо просить "
            "детально. Форматуй відповідь для Telegram "
            "через HTML: використовуй тільки <b>, <i> і <code>. Не використовуй "
            "Markdown-розмітку, таблиці або вкладені списки. Для пунктів використовуй "
            "символ •, максимум один рівень списку. Ключові назви блоків виділяй <b>. "
            "Якщо пояснюєш типи, ролі або категорії, назву кожного типу став окремим "
            "жирним рядком, а деталі давай нижче простими пунктами. Якщо в контексті "
            "є висновок або правильний підхід після переліку типів, додай його окремим "
            "коротким блоком <b>Правильний підхід</b>."
        ),
        "input": [
            {
                "role": "user",
                "content": (
                    f"Питання користувача:\n{question}\n\n"
                    f"Контекст з бази знань:\n{build_context(chunks)}"
                ),
            },
        ],
    }


def build_context(chunks: list[KnowledgeChunk]) -> str:
    context_parts = []
    total_length = 0

    for chunk in chunks:
        part = (
            f"Джерело: {chunk.file_name}\n"
            f"Розділ: {chunk.title}\n"
            f"{chunk.text}"
        )

        if total_length + len(part) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(part)
        total_length += len(part)

    return "\n\n---\n\n".join(context_parts)


def extract_output_text(data: dict) -> str | None:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()

    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if isinstance(content_item.get("text"), str):
                return content_item["text"].strip()

    return None


def list_sources(chunks: list[KnowledgeChunk]) -> list[str]:
    sources = []

    for chunk in chunks:
        if chunk.file_name not in sources:
            sources.append(chunk.file_name)

    return sources


def safe_snippet(value: str, limit: int) -> str:
    return " ".join(str(value).split())[:limit]
