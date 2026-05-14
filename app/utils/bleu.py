"""bleu.py — Score BLEU pur Python (sans dépendances UI)"""

def compute_bleu1(reference: str, hypothesis: str) -> float:
    if not reference or not hypothesis:
        return 0.0
    ref_tokens = set(reference.lower().split())
    hyp_tokens = hypothesis.lower().split()
    if not hyp_tokens:
        return 0.0
    matches   = sum(1 for t in hyp_tokens if t in ref_tokens)
    precision = matches / len(hyp_tokens)
    bp        = min(1.0, len(hyp_tokens) / max(1, len(ref_tokens)))
    return round(precision * bp, 3)

def compute_bleu_sacrebleu(reference: str, hypothesis: str) -> float:
    try:
        import sacrebleu
        result = sacrebleu.corpus_bleu([hypothesis], [[reference]])
        return round(result.score / 100.0, 3)
    except Exception:
        return compute_bleu1(reference, hypothesis)
