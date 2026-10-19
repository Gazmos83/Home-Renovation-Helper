"""Offline Ragas evaluation of retrieval and answers (openspec change ragas-evaluation).

Run with `uv run python -m app.evals`. Never imported by the running app.
"""

import os

# Ragas reports usage to its own analytics service unless told not to; nothing
# about a run leaves except through the gateway and the score-only Langfuse trace.
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
