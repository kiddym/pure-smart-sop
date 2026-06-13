"""核查点 API schema（设计 spec §6）。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CheckType = Literal["ocr", "safety"]  # 第一期启用；object/action/semantic 后续
Modality = Literal["visual", "voice", "dual"]
Severity = Literal["info", "warn", "critical"]
Trigger = Literal["on_enter", "manual", "continuous"]


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    node_id: str
    procedure_id: str
    check_type: str
    modality: str
    severity: str
    trigger: str
    prompt: str
    keep_evidence: bool
    confidence_threshold: float | None
    params: dict[str, Any]
    sort_order: int


class CheckCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_type: CheckType
    modality: Modality = "visual"
    severity: Severity = "warn"
    trigger: Trigger = "on_enter"
    prompt: str = ""
    keep_evidence: bool = True
    confidence_threshold: float | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    sort_order: int | None = None


class CheckPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modality: Modality | None = None
    severity: Severity | None = None
    trigger: Trigger | None = None
    prompt: str | None = None
    keep_evidence: bool | None = None
    confidence_threshold: float | None = None
    params: dict[str, Any] | None = None
    sort_order: int | None = None
