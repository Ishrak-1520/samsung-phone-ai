import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from db.database import SessionLocal
from db.models import Phone, Spec


def get_specs_from_db(phone_name: str) -> str:
    db = SessionLocal()
    try:
        phone = db.query(Phone).filter(Phone.model == phone_name).first()
        if not phone:
            return f"No data found for '{phone_name}' in the database."

        specs = db.query(Spec).filter(Spec.phone_id == phone.id).order_by(Spec.category, Spec.id).all()

        categories: dict[str, list[str]] = {}
        for s in specs:
            categories.setdefault(s.category, []).append(f"- {s.key}: {s.value}")

        lines = [f"**{phone_name} Specifications**", ""]
        for cat, rows in categories.items():
            lines.append(f"**{cat}**")
            for row in rows:
                lines.append(row)
            lines.append("")

        return "\n".join(lines).strip()
    finally:
        db.close()


def run_spec_agent(phone_name: str, question: str = None) -> str:
    print(f"Spec Retriever input: '{phone_name}'")
    if question:
        print(f"Context: '{question}'")

    summary = get_specs_from_db(phone_name)
    print(f"Retrieved {len(summary)} characters of specs")
    return summary


if __name__ == "__main__":
    result = run_spec_agent("Samsung Galaxy S23")
    print(f"Done. Length: {len(result)} chars")
