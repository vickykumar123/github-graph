"""
Text utility functions for processing AI responses.
"""

import re


def strip_thinking_content(text: str) -> str:
    """
    Remove <think>...</think> tags and their content from AI responses.

    Some AI models (like Claude) may include thinking/reasoning content
    wrapped in <think> tags. We want to strip this out before storing
    responses to keep them concise.

    Args:
        text: Raw AI response text

    Returns:
        Cleaned text without thinking tags

    Example:
        >>> text = "Here is my answer\\n<think>Let me reason...</think>\\nFinal answer"
        >>> strip_thinking_content(text)
        'Here is my answer\\n\\nFinal answer'
    """
    # Remove <think>...</think> blocks (including newlines)
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # Remove extra whitespace and collapse multiple blank lines
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # Max 2 newlines
    cleaned = cleaned.strip()

    return cleaned
