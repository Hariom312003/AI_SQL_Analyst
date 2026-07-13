"""Memory Agent -- loads and formats prior conversation turns (module 9:
Conversation Memory) so the Intent Agent can resolve follow-ups like 'now
only Electronics' without the user restating the whole question."""
from __future__ import annotations

from backend.agents.instrumentation import instrumented


@instrumented("memory_agent")
def load_history(messages) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]
