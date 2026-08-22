from pathlib import Path
from string import Template


PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "Prompts" / "job_evaluator.txt"
)


def load_prompt(
    *,
    target_role: str,
    target_exp: str,
    target_stack: str,
    language: str,
    vacancies_text: str,
) -> str:
    """Load the prompt template and fill its placeholders safely."""
    template = Template(PROMPT_PATH.read_text(encoding="utf-8"))

    return template.substitute(
        target_role=target_role,
        target_exp=target_exp,
        target_stack=target_stack,
        language=language,
        vacancies=vacancies_text,
    )
