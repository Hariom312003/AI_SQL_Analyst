"""Prompt templates for the Intent Agent (module: conversational memory / intent
classification). Kept separate from the LLM provider code so prompts can be
iterated on and reviewed without touching client/plumbing code."""
from __future__ import annotations

INTENT_SYSTEM_PROMPT = (
    "You are the Intent Agent of an enterprise natural-language-to-SQL system. "
    "Rewrite the user's new message into a fully self-contained question that folds "
    "in any filters, entities, or comparisons implied by the conversation history. "
    'Classify it. JSON schema: {"resolved_question": str, "intent_type": '
    '"lookup"|"aggregation"|"trend"|"comparison"|"ranking"|"other", "filters": [str]}'
)


def build_intent_user_prompt(question: str, history_text: str) -> str:
    return f"Conversation history:\n{history_text or '(no prior turns)'}\n\nNew message: {question}"
