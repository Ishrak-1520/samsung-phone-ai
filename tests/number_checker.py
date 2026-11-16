import re


def check_numbers(generated_text: str, source_text: str) -> dict:
    source_normalized = source_text.replace(",", "")
    pattern = r"\b\d+(?:[.,:\-]\d+)*\b"
    raw_matches = re.findall(pattern, generated_text)

    ungrounded = []
    seen = set()

    for token in raw_matches:
        if token in seen:
            continue
        seen.add(token)

        if token in source_text:
            continue

        clean_token = token.replace(",", "")
        if clean_token in source_normalized or clean_token in source_text:
            continue

        ungrounded.append(token)

    return {
        "total_numbers_checked": len(seen),
        "ungrounded_numbers": ungrounded,
    }


def check_comparison_numbers(
    generated_text: str,
    spec1_text: str,
    spec2_text: str,
    phone1_name: str = "S23",
    phone2_name: str = "S22",
) -> dict:
    # Checks each number against combined specs; numbers must exist in either phone's data
    combined_specs = spec1_text + "\n" + spec2_text
    return check_numbers(generated_text, combined_specs)

