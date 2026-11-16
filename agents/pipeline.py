import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from agents.review_agent import run_comparison_agent, run_review_agent
from agents.spec_agent import run_spec_agent


def generate_review(phone_name: str) -> str:
    print(f"Generating review for '{phone_name}'")
    spec_summary = run_spec_agent(phone_name)
    review = run_review_agent(spec_summary, phone_name)
    return review


def generate_comparison(phone_name_1: str, phone_name_2: str) -> str:
    if phone_name_1.strip().lower() == phone_name_2.strip().lower():
        raise ValueError(
            f"Cannot compare a phone with itself: '{phone_name_1}' and '{phone_name_2}' are identical. "
            "Please provide two different phones."
        )

    print(f"Comparing '{phone_name_1}' vs '{phone_name_2}'")
    spec_summary_1 = run_spec_agent(
        phone_name_1,
        question=f"compare {phone_name_1} and {phone_name_2}",
    )
    spec_summary_2 = run_spec_agent(
        phone_name_2,
        question=f"compare {phone_name_1} and {phone_name_2}",
    )

    review = run_comparison_agent(
        spec_summary_1,
        phone_name_1,
        spec_summary_2,
        phone_name_2,
    )
    return review


if __name__ == "__main__":
    generate_review("Samsung Galaxy S23")
    generate_comparison("Samsung Galaxy S23", "Samsung Galaxy S22")
