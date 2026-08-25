from pathlib import Path
from string import Template


PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "Prompts" / "job_evaluator.txt"
)


from App.models import JobCriteria

def load_prompt(
    *,
    criteria: JobCriteria,
    vacancies_text: str,
) -> str:
    """Load the prompt template and fill its placeholders safely."""
    template = Template(PROMPT_PATH.read_text(encoding="utf-8"))

    return template.substitute(
        target_role=criteria.target_role,
        target_exp=criteria.target_exp,
        target_stack=criteria.target_stack,
        salary_expectations=criteria.salary_expectations,
        work_format=criteria.work_format,
        english_level=criteria.english_level,
        employment_type=criteria.employment_type,
        language=criteria.language,
        vacancies=vacancies_text,
    )
