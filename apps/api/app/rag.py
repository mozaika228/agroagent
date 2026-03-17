import math
import re
from collections import Counter
from pathlib import Path

import httpx

from .llm import ollama_chat

VECTOR_DIM = 768


def extract_text_from_file(file_path: Path, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(pages).strip()
    return file_path.read_text(encoding="utf-8", errors="ignore").strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    n = len(clean)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(clean[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


def _fit_dim(vec: list[float], dim: int = VECTOR_DIM) -> list[float]:
    if len(vec) == dim:
        return vec
    if len(vec) > dim:
        return vec[:dim]
    return vec + ([0.0] * (dim - len(vec)))


def fallback_embed(text: str, dim: int = VECTOR_DIM) -> list[float]:
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    counts = Counter(tokens)
    vec = [0.0] * dim
    for token, value in counts.items():
        idx = hash(token) % dim
        vec[idx] += float(value)
    return vec


def embed_texts(texts: list[str], base_url: str, model: str, timeout: float = 20.0) -> list[list[float]]:
    if not texts:
        return []

    try:
        with httpx.Client(timeout=timeout) as client:
            # Preferred endpoint in newer Ollama versions.
            resp = client.post(
                f"{base_url.rstrip('/')}/api/embed",
                json={"model": model, "input": texts},
            )
            if resp.is_success:
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if embeddings and isinstance(embeddings[0], list):
                    return [_fit_dim([float(x) for x in emb]) for emb in embeddings]
    except httpx.HTTPError:
        pass

    # Backward-compatible fallback endpoint.
    embedded: list[list[float]] = []
    try:
        with httpx.Client(timeout=timeout) as client:
            for text in texts:
                resp = client.post(
                    f"{base_url.rstrip('/')}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                resp.raise_for_status()
                vec = resp.json().get("embedding", [])
                embedded.append(_fit_dim([float(x) for x in vec]))
        return embedded
    except httpx.HTTPError:
        return [fallback_embed(t, VECTOR_DIM) for t in texts]


def generate_answer_with_context(
    question: str,
    context_blocks: list[dict],
    base_url: str,
    model: str,
    timeout: float = 30.0,
) -> str:
    if not context_blocks:
        return "No relevant documents found. Upload PDF/TXT recommendations and try again."

    context_text = "\n\n".join(
        [
            f"[{item['doc_id']}:{item['chunk_id']}] {item['chunk_text'][:500]}"
            for item in context_blocks
        ]
    )
    system_prompt = (
        "You are an agriculture assistant for West Kazakhstan. "
        "Answer using only provided context. "
        "If unsure, say what is missing. "
        "Cite chunk references in format [doc_id:chunk_id]."
    )
    user_prompt = f"Question: {question}\n\nContext:\n{context_text}"

    content = ollama_chat(
        base_url=base_url,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout=timeout,
    )
    if content:
        return content

    # Deterministic fallback without LLM.
    snippets = "\n".join([f"- {c['chunk_text'][:220]}..." for c in context_blocks[:3]])
    return (
        "Draft answer from retrieved context:\n"
        f"{snippets}\n"
        "Run Ollama chat model to generate a grounded natural-language recommendation."
    )


def tokenize_for_bm25(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def bm25_scores(query: str, docs: list[str], k1: float = 1.2, b: float = 0.75) -> list[float]:
    if not docs:
        return []

    q_terms = tokenize_for_bm25(query)
    if not q_terms:
        return [0.0] * len(docs)

    tokenized_docs = [tokenize_for_bm25(d) for d in docs]
    lengths = [len(toks) for toks in tokenized_docs]
    avgdl = max(1e-9, (sum(lengths) / len(lengths)))

    df: dict[str, int] = {}
    for terms in set(q_terms):
        df[terms] = sum(1 for doc in tokenized_docs if terms in set(doc))

    scores: list[float] = []
    n_docs = len(docs)
    for i, doc_terms in enumerate(tokenized_docs):
        tf = Counter(doc_terms)
        dl = lengths[i]
        score = 0.0
        for term in q_terms:
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            term_df = df.get(term, 0)
            idf = math.log(1 + (n_docs - term_df + 0.5) / (term_df + 0.5))
            denom = freq + k1 * (1 - b + b * (dl / avgdl))
            score += idf * ((freq * (k1 + 1)) / max(1e-9, denom))
        scores.append(score)
    return scores
