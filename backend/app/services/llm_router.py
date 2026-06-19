"""LLMRouter — config-driven routing across local Ollama + cloud, with fallback."""
# TODO(plan: Phase 2) — route each agent task to the cheapest good-enough model;
# enforce per-tenant token budgets; fall back cloud -> local on rate-limit/quota.


class LLMRouter:
    """Single abstraction over all LLM providers. Never hardcode one provider."""
