"""Evaluator registry — maps string names to evaluator instances.

The framework maintains two **evaluator catalogs** that define which
evaluators are available in each execution mode:

* **Local catalog** — all 11 evaluators (scaffold, Azure SDK, LLM judges).
* **Cloud catalog** — the 4 Azure SDK evaluators supported by Foundry.

The catalogs are defined in ``config.models`` and exposed here for
convenience.  The :class:`EvaluatorRegistry` resolves names to instances;
the catalogs control which names are *valid* for a given mode.
"""

from __future__ import annotations

import logging
from typing import Literal

from rag_eval_framework.config.models import (
    CLOUD_EVALUATOR_NAMES,
    LOCAL_EVALUATOR_NAMES,
)
from rag_eval_framework.evaluators.base import BaseEvaluator

logger = logging.getLogger(__name__)


class EvaluatorRegistry:
    """A registry that maps evaluator names to their concrete classes.

    Evaluators are registered once and instantiated on demand.  This keeps
    configuration files human-readable (just evaluator names) while the
    registry handles resolution.

    Usage
    -----
    >>> registry = EvaluatorRegistry()
    >>> registry.register(MyEvaluator)
    >>> evaluator = registry.get("my_evaluator")
    """

    def __init__(self) -> None:
        self._evaluators: dict[str, type[BaseEvaluator]] = {}

    def register(self, evaluator_cls: type[BaseEvaluator]) -> None:
        """Register an evaluator class.

        The evaluator's ``name`` property is used as the registry key.
        """
        # Instantiate briefly to read the name property
        instance = evaluator_cls()
        name = instance.name
        if name in self._evaluators:
            logger.warning("Overwriting existing evaluator '%s'", name)
        self._evaluators[name] = evaluator_cls
        logger.debug("Registered evaluator '%s' -> %s", name, evaluator_cls.__name__)

    def get(self, name: str) -> BaseEvaluator:
        """Return a fresh instance of the evaluator registered under *name*.

        Raises
        ------
        KeyError
            If no evaluator is registered with that name.
        """
        if name not in self._evaluators:
            available = sorted(self._evaluators.keys())
            raise KeyError(f"No evaluator registered with name '{name}'. Available: {available}")
        return self._evaluators[name]()

    def list_evaluators(self) -> list[str]:
        """Return sorted list of registered evaluator names."""
        return sorted(self._evaluators.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._evaluators

    def __len__(self) -> int:
        return len(self._evaluators)

    # ------------------------------------------------------------------
    # Mode-aware helpers
    # ------------------------------------------------------------------

    def list_for_mode(self, mode: Literal["local", "cloud"]) -> list[str]:
        """Return sorted evaluator names available for the given mode."""
        catalog = LOCAL_EVALUATOR_NAMES if mode == "local" else CLOUD_EVALUATOR_NAMES
        return sorted(name for name in self._evaluators if name in catalog)

    def get_for_mode(self, name: str, mode: Literal["local", "cloud"]) -> BaseEvaluator:
        """Return a fresh instance, validating *name* against the mode catalog.

        Raises
        ------
        KeyError
            If the evaluator is not registered or not in the mode's catalog.
        """
        catalog = LOCAL_EVALUATOR_NAMES if mode == "local" else CLOUD_EVALUATOR_NAMES
        if name not in catalog:
            raise KeyError(
                f"Evaluator '{name}' is not available in {mode} mode. Available: {sorted(catalog)}"
            )
        return self.get(name)


def _create_default_registry() -> EvaluatorRegistry:
    """Create a registry pre-loaded with all built-in evaluators.

    Phase 1 scaffold evaluators are always available.  Phase 2 Azure
    SDK evaluators and LLM judges are also registered; they will produce
    a clear error at evaluation time when their dependencies are missing.
    """
    # --- Phase 1 built-ins ------------------------------------------------
    # --- Phase 2: Azure SDK evaluators ------------------------------------
    from rag_eval_framework.evaluators.azure.completeness import (
        ResponseCompletenessEvaluator,
    )
    from rag_eval_framework.evaluators.azure.groundedness import (
        GroundednessEvaluator,
    )
    from rag_eval_framework.evaluators.azure.relevance import RelevanceEvaluator
    from rag_eval_framework.evaluators.azure.retrieval import RetrievalEvaluator
    from rag_eval_framework.evaluators.builtin.answer_presence import (
        AnswerPresenceEvaluator,
    )
    from rag_eval_framework.evaluators.builtin.context_presence import (
        ContextPresenceEvaluator,
    )
    from rag_eval_framework.evaluators.builtin.exact_match_accuracy import (
        ExactMatchAccuracyEvaluator,
    )

    # --- Phase 2: LLM-as-a-judge evaluators -------------------------------
    from rag_eval_framework.evaluators.judges.accuracy import AccuracyJudge
    from rag_eval_framework.evaluators.judges.citation import CitationJudge
    from rag_eval_framework.evaluators.judges.hallucination import (
        HallucinationJudge,
    )
    from rag_eval_framework.evaluators.judges.policy_compliance import (
        PolicyComplianceJudge,
    )

    registry = EvaluatorRegistry()

    # Phase 1
    registry.register(AnswerPresenceEvaluator)
    registry.register(ContextPresenceEvaluator)
    registry.register(ExactMatchAccuracyEvaluator)

    # Phase 2 – Azure
    registry.register(GroundednessEvaluator)
    registry.register(RelevanceEvaluator)
    registry.register(RetrievalEvaluator)
    registry.register(ResponseCompletenessEvaluator)

    # Phase 2 – Judges
    registry.register(AccuracyJudge)
    registry.register(HallucinationJudge)
    registry.register(CitationJudge)
    registry.register(PolicyComplianceJudge)

    return registry


# Module-level singleton used by runners and CLI
default_registry: EvaluatorRegistry = _create_default_registry()
