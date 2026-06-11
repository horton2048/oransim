"""Registry for diffusion-model variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import DiffusionModel


def _load_causal_neural_hawkes() -> type[DiffusionModel]:
    from .neural_hawkes import CausalNeuralHawkesProcess

    return CausalNeuralHawkesProcess


def _load_parametric() -> type[DiffusionModel]:
    from .hawkes import ParametricHawkes

    return ParametricHawkes


def _load_bass_saturated() -> type[DiffusionModel]:
    from .bass_saturated_hawkes import BassSaturatedHawkes

    return BassSaturatedHawkes


REGISTRY: dict[str, Callable[[], type[DiffusionModel]]] = {
    "causal_neural_hawkes": _load_causal_neural_hawkes,
    "parametric_hawkes": _load_parametric,
    "bass_saturated_hawkes": _load_bass_saturated,
    # Aliases
    "neural_hawkes": _load_causal_neural_hawkes,
    "transformer_hawkes": _load_causal_neural_hawkes,
    "thp": _load_causal_neural_hawkes,
    "hawkes": _load_parametric,
    "bass": _load_bass_saturated,
}


def get_diffusion_model(name: str, **kwargs: Any) -> DiffusionModel:
    try:
        factory = REGISTRY[name]
    except KeyError:
        raise KeyError(f"Unknown diffusion model '{name}'. Available: {sorted(REGISTRY)}") from None
    cls = factory()
    # Prefer locally-trained weights: training writes to <checkpoint_dir>/model.pt
    # and load_pretrained() auto-resolves that path. Without a checkpoint it raises
    # FileNotFoundError, so we fall back to a fresh (random-init) instance.
    if not kwargs and hasattr(cls, "load_pretrained"):
        try:
            return cls.load_pretrained()
        except FileNotFoundError:
            pass
    return cls(**kwargs)


def list_diffusion_models() -> list[str]:
    return ["causal_neural_hawkes", "parametric_hawkes", "bass_saturated_hawkes"]
