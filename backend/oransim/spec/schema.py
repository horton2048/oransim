"""ProductSpec Pydantic schema — 自由文本 idea 的结构化抽取结果.

模式照抄 data/schema/canonical.py: extra='forbid' + 独立 schema_version.
忠实度三元标记: provenance / inferred / default_applied (规范 §3.2).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"

_VALID_PRICE_MODELS = {"one_time", "subscription", "freemium"}


class SpecField(BaseModel):
    """单字段忠实度包装.

    每个 ProductSpec 的细粒度字段可用此类携带 provenance/inferred/default_applied.
    """

    model_config = ConfigDict(extra="forbid")

    value: Any
    inferred: bool = False
    default_applied: bool = False
    provenance: list[dict[str, int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _force_inferred_when_no_provenance(self) -> SpecField:
        if not self.provenance and not self.default_applied:
            self.inferred = True
        return self


class ProductSpec(BaseModel):
    """Product launch spec — structured representation of a free-text idea.

    Fields:
    - *_raw fields: user verbatim text, never overwritten (规范 §3.2).
    - price_point: dict with keys amount/currency/model.
    - confidence: overall extraction confidence in [0, 1].
    - provenance: list of {start, end} character spans in the idea text.
    - inferred: True when LLM inferred this top-level field (no provenance).
    - default_applied: True when a system default was used.
    - fields: optional fine-grained per-field metadata (SpecField).
    """

    model_config = ConfigDict(extra="forbid")

    product_name: str
    one_liner: str
    category_raw: str
    target_user_raw: str
    price_point: dict[str, Any]
    differentiation: list[str] = Field(default_factory=list)
    substitutes_raw: list[str] = Field(default_factory=list)
    channels_hint: list[str] = Field(default_factory=list)
    value_props: list[str] = Field(default_factory=list)

    # top-level faithfulness metadata
    confidence: float = 0.5
    provenance: list[dict[str, int]] = Field(default_factory=list)
    inferred: bool = False
    default_applied: bool = False

    # fine-grained per-field metadata (optional)
    fields: dict[str, SpecField] = Field(default_factory=dict)

    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def _enforce_faithfulness(self) -> ProductSpec:
        # Red line: no provenance at top level → must be inferred
        if not self.provenance and not self.default_applied:
            self.inferred = True
        return self

    @property
    def assumed_fields(self) -> list[str]:
        """All field names where inferred=True OR default_applied=True."""
        result: list[str] = []
        for fname, fval in self.fields.items():
            if fval.inferred or fval.default_applied:
                result.append(fname)
        return result
