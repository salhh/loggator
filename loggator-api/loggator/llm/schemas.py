from typing import Literal
from pydantic import BaseModel, Field


class AnomalyResult(BaseModel):
    anomalies: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"] = "low"
    summary: str = ""
    root_cause_hints: list[str] = Field(default_factory=list)
    mitre_tactics: list[str] = Field(default_factory=list)
    # e.g. ["T1110 - Brute Force", "T1190 - Exploit Public-Facing Application"]


class SummaryResult(BaseModel):
    summary: str = ""
    top_issues: list[str] = Field(default_factory=list)
    error_count: int = 0
    recommendation: str = ""


class ChatResult(BaseModel):
    answer: str = ""
