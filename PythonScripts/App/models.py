from typing import TypedDict


class Vacancy(TypedDict, total=False):
    _temp_id: int
    Title: str
    Company: str
    Url: str
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
