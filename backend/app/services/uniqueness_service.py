"""
uniqueness_service.py — similarity check between generated text and Wikipedia source.

Uses Jaccard similarity on word sets (no ML needed, fast, language-agnostic).
Threshold: if similarity > 0.35 → text is too close to Wikipedia → regenerate.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Similarity threshold: 0.0 = totally different, 1.0 = identical
SIMILARITY_THRESHOLD = float(0.35)

# Russian stopwords to ignore in comparison (they inflate similarity)
_STOPWORDS = {
    "в", "на", "и", "с", "по", "из", "к", "за", "от", "до",
    "не", "что", "он", "она", "они", "его", "её", "их", "это",
    "был", "была", "были", "есть", "быть", "как", "так", "но",
    "а", "же", "ли", "бы", "то", "или", "о", "об", "для", "при",
    "со", "во", "под", "над", "между", "через", "после", "перед",
    "когда", "если", "чтобы", "который", "которая", "которые",
    "также", "ещё", "уже", "всё", "все", "один", "одна", "своё",
    "своя", "свой", "свои", "этот", "эта", "эти", "такой", "такая",
}


def _tokenize(text: str) -> set[str]:
    """Lowercase words, strip punctuation, remove stopwords."""
    words = re.findall(r"[а-яёa-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity between two texts: |intersection| / |union|"""
    if not text_a or not text_b:
        return 0.0
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def is_unique_enough(generated: str, source: str, threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """Return True if generated text is sufficiently different from source."""
    similarity = jaccard_similarity(generated, source)
    logger.info("Uniqueness check: similarity=%.3f threshold=%.3f unique=%s",
                similarity, threshold, similarity <= threshold)
    return similarity <= threshold
