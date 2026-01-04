from __future__ import annotations

from echoagent.agent.prompting.history_renderer import render_iteration_history
from echoagent.context import create_conversation_state
from echoagent.context.state import IterationDigest


def test_digest_renderer_prefers_digest_for_old_iterations() -> None:
    state = create_conversation_state()

    iter1 = state.begin_iteration()
    iter1.observation = "obs1"
    iter1.set_digest(IterationDigest(summary="summary-1"))
    iter1.mark_complete()

    iter2 = state.begin_iteration()
    iter2.observation = "obs2"
    iter2.set_digest(IterationDigest(summary="summary-2"))
    iter2.mark_complete()

    iter3 = state.begin_iteration()
    iter3.observation = "obs3"
    iter3.mark_complete()

    iter4 = state.begin_iteration()
    iter4.observation = "obs4"
    iter4.mark_complete()

    output = render_iteration_history(
        state.iterations,
        include_current=False,
        current_iteration=state.current_iteration,
    )

    assert "summary: summary-1" in output
    assert "summary: summary-2" in output
    assert "<thought>\nobs3\n</thought>" in output
    assert "<thought>\nobs4\n</thought>" in output
