"""
Memory Summarizer for GalSen IA.

Simple extractive summarizer for memories.
"""

import re
from typing import List
from .types import MemoryItem
from .interfaces import MemorySummarizer


class SimpleMemorySummarizer(MemorySummarizer):
    """Simple extractive summarizer."""

    def summarize(self,
                  items: List[MemoryItem],
                  max_length: int = 500,
                  language: str = "fr") -> str:
        """
        Summarize a list of memory items by concatenating their content
        up to max_length.

        Args:
            items: List of memory items to summarize.
            max_length: Maximum length of the summary in characters.
            language: Language for the summary (not used in this simple version).

        Returns:
            A summarized string.
        """
        if not items:
            return ""
        # For simplicity, we'll just concatenate the string representations
        # of the content, separating by spaces, and truncate to max_length.
        parts = []
        current_length = 0
        for item in items:
            if isinstance(item.content, str):
                text = item.content.strip()
                if text:
                    # Add a space if not the first part
                    if parts:
                        text = " " + text
                    if current_length + len(text) > max_length:
                        # Truncate to fit
                        remaining = max_length - current_length
                        if remaining > 0:
                            parts.append(text[:remaining])
                        break
                    else:
                        parts.append(text)
                        current_length += len(text)
            else:
                # For non-string, convert to string
                text = str(item.content).strip()
                if text:
                    if parts:
                        text = " " + text
                    if current_length + len(text) > max_length:
                        remaining = max_length - current_length
                        if remaining > 0:
                            parts.append(text[:remaining])
                        break
                    else:
                        parts.append(text)
                        current_length += len(text)
        return "".join(parts)

    def summarize_conversation(self,
                               conversation_id: str,
                               max_length: int = 500,
                               language: str = "fr") -> Optional[str]:
        """
        Summarize a conversation by its ID.

        In this simple implementation, we treat the conversation_id as a session_id
        and retrieve all items from that session, then summarize them.

        Args:
            conversation_id: Identifier of the conversation (session_id).
            max_length: Maximum length of the summary.
            language: Language for the summary.

        Returns:
            A summarized string or None if no items found.
        """
        # Note: We don't have access to the store here, so we cannot retrieve items.
        # In a real implementation, the summarizer would need access to the store
        # or be a method of the memory manager.
        # For now, we'll return an empty string or None.
        # Since this is a simple implementation, we'll return an empty string.
        # However, the method signature says it can return None.
        # We'll return an empty string as a placeholder.
        return ""