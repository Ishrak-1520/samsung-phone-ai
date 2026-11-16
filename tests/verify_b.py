import os
import sys

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agents.pipeline import generate_comparison
from agents.review_agent import run_comparison_agent, run_review_agent
from agents.spec_agent import run_spec_agent
from tests.number_checker import check_comparison_numbers, check_numbers


def test_single_phone_review(phone_name: str, test_num: int):
    print(f"Test B.{test_num}: Review for {phone_name}")
    print(f"Agent 1 Input: {phone_name}")

    spec_summary = run_spec_agent(phone_name)
    print(f"Agent 1 output passed to Agent 2 ({len(spec_summary)} chars)")

    review = run_review_agent(spec_summary, phone_name)

    check_result = check_numbers(review, spec_summary)
    print(f"Numbers checked: {check_result['total_numbers_checked']}")
    if check_result["ungrounded_numbers"]:
        print(f"Ungrounded numbers found: {check_result['ungrounded_numbers']}")
    else:
        print("All numbers grounded in input specifications.")

    return spec_summary, review


def test_comparison(phone1: str, phone2: str, test_num: int):
    print(f"Test B.{test_num}: Comparison of {phone1} vs {phone2}")

    summary1 = run_spec_agent(phone1, question=f"compare {phone1} and {phone2}")
    summary2 = run_spec_agent(phone2, question=f"compare {phone1} and {phone2}")

    print(f"Agent 1 outputs passed to Agent 2: {phone1} ({len(summary1)} chars), {phone2} ({len(summary2)} chars)")

    review = run_comparison_agent(summary1, phone1, summary2, phone2)

    check_result = check_comparison_numbers(review, summary1, summary2, phone1, phone2)
    print(f"Numbers checked: {check_result['total_numbers_checked']}")
    if check_result["ungrounded_numbers"]:
        print(f"Ungrounded numbers found: {check_result['ungrounded_numbers']}")
    else:
        print("All numbers grounded in input specifications.")

    return summary1, summary2, review


if __name__ == "__main__":
    a34_spec, a34_rev = test_single_phone_review("Samsung Galaxy A34", 1)
    s23_spec, s23_rev = test_single_phone_review("Samsung Galaxy S23", 2)
    s1, s2, comp_rev = test_comparison("Samsung Galaxy S23", "Samsung Galaxy S22", 3)

    print("Test B.4: Comparison of identical phones (Samsung Galaxy S23 vs Samsung Galaxy S23)")
    try:
        generate_comparison("Samsung Galaxy S23", "Samsung Galaxy S23")
    except Exception as e:
        print(f"Rejected as expected: {type(e).__name__}: {e}")

