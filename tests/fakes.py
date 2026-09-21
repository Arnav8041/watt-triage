from types import SimpleNamespace


def tool_use(name, **input):
    """A tool-call block shaped like the real API's."""
    return SimpleNamespace(type="tool_use", id=f"toolu_{name}", name=name, input=input)


def submit(outcome, confidence, reasoning="Looks normal for this appliance."):
    return tool_use(
        "submit_triage_decision", outcome=outcome, confidence=confidence, reasoning=reasoning
    )


class ScriptedClient:
    """Fake anthropic.Anthropic. Each reply is one model turn (a list of blocks, or an Exception to raise).
    Out of script it raises, so no test can reach the real API."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.messages = self  # so client.messages.create(...) works
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=reply, stop_reason="tool_use")
