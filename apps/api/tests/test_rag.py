from app.rag import bm25_scores, chunk_text


def test_chunk_text_non_empty():
    chunks = chunk_text("a" * 2000, chunk_size=500, overlap=50)
    assert len(chunks) >= 4


def test_bm25_scores_order():
    docs = [
        "wheat fertilizer recommendation for spring",
        "tractor maintenance guide",
        "wheat disease and fertilizer dosage",
    ]
    scores = bm25_scores("wheat fertilizer", docs)
    assert scores[0] > scores[1]
    assert scores[2] > scores[1]
