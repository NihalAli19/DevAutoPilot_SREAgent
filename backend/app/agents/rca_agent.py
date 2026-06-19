"""RCA Agent — RAG over past incidents + recent commits to rank root causes."""
# TODO(plan: Phase 3) — embed incident, query Azure AI Search, reason with frontier LLM.


class RCAAgent:
    """Generates ranked root-cause hypotheses with confidence and affected files."""
