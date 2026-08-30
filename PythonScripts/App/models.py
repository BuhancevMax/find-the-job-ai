from dataclasses import dataclass, field
from typing import TypedDict


class Vacancy(TypedDict, total=False):
    _temp_id: int
    Title: str
    Company: str
    Url: str
    Source: str
    RequiredExperience: str
    DescriptionSnippet: str
    TechStack: str
    AiSummary: str
    AiMatchScore: int


class AIEvaluation(TypedDict):
    temp_id: int
    detected_role: str
    detected_level: str
    role_match: int
    level_match: int
    tech_match: int
    experience_match: int
    critical_mismatch: bool
    critical_reason: str
    TechStack: str
    AiSummary: str
    ExtractedExperience: str


@dataclass(frozen=True)
class JobCriteria:
    target_role: str
    target_exp: str
    target_stack: str
    language: str
    salary_expectations: str = ""
    work_format: str = ""
    english_level: str = ""
    employment_type: str = ""
    stacks: list[str] = field(default_factory=list)

    def get_stack_list(self) -> list[str]:
        """Return list of distinct stack tokens."""
        if self.stacks:
            return [s.strip() for s in self.stacks if s.strip()]
        if self.target_stack:
            return [s.strip() for s in self.target_stack.split(",") if s.strip()]
        return []

    def is_remote(self) -> bool:
        """Check if work format specifies remote."""
        wf = (self.work_format or "").lower()
        return "remote" in wf or "удален" in wf or "віддален" in wf or "дистанц" in wf
