import re
import sys


def safe_log(msg: str) -> None:
    """Safe UTF-8 print for Windows and background tasks."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        try:
            sys.stdout.buffer.write(f"{msg}\n".encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        except Exception:
            pass


def clean_tech_token(token: str) -> str:
    """Normalize Cyrillic lookalikes in tech tokens (e.g. 'С#' -> 'C#')."""
    t = token.strip()
    t = re.sub(r'[сС](?=[#\+])', 'C', t)
    return t


def normalize_experience_text(text: str) -> str:
    """Normalize any experience string (UA/EN/RU) to clean Russian format."""
    if not text:
        return "в описании"
    t = text.strip().lower()

    if "без" in t or "no experience" in t or "trainee" in t or "студент" in t:
        return "без опыта"
    if "в описі" in t or "в описании" in t or t in ("не указано", "не указан"):
        return "в описании"

    # Match 0.5 year / 6 months / 0.5 року
    if re.search(r'(0[.,]5|пів|пол|6\s*міс|6\s*мес)', t):
        return "до 1 года"

    # Match range e.g. '1-3 года', '1-3 роки', '2-5 years', '1–3y'
    range_match = re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)?', t)
    if range_match:
        n1, n2 = range_match.group(1), range_match.group(2)
        return f"{n1}-{n2} года"

    # Match '5+ years', '5+ лет', '3+ роки'
    plus_match = re.search(r'(\d+)\s*\+\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)?', t)
    if plus_match:
        n = int(plus_match.group(1))
        unit = "год" if n == 1 else "года" if 2 <= n <= 4 else "лет"
        return f"{n}+ {unit}"

    # Match 'от X лет', 'від X років', 'from X years'
    from_match = re.search(r'(?:від|от|from|більше|более)\s*(\d+)\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)?', t)
    if from_match:
        n = int(from_match.group(1))
        unit = "года" if n == 1 else "лет"
        return f"от {n} {unit}"

    # Match single number e.g. '1 year', '2 роки', '5 years', '5 лет'
    num_match = re.search(r'(?:досвід|опыт|experience|вимоги)?\D*(\d+)\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)', t)
    if num_match:
        n = int(num_match.group(1))
        unit = "год" if (n % 10 == 1 and n % 100 != 11) else "года" if (2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20)) else "лет"
        return f"{n} {unit}"

    return "в описании"
