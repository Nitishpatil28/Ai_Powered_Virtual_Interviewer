"""
Simple relevance scoring utility for GD evaluation
"""


def simple_relevance_score(text: str, topic: str) -> float:
    """
    Calculate relevance score based on keyword overlap between text and topic.
    Returns score from 0-5.
    """
    topic_words = set(topic.lower().split())
    words = set(text.lower().split())
    overlap = len(topic_words & words)
    return min(5.0, (overlap / max(1, len(topic_words))) * 5)
