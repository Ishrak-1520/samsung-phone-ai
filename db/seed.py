from datetime import datetime
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
from scraper.scraper import PHONES, get_html, parse_specs


def seed_database():
    db = SessionLocal()
    print("Starting database seeding (12 phones)")

    no_price_phones = []
    specs_per_phone = {}
    garbled_char_count = 0
    garbled_samples = []
    garbled_markers = ["Â", "â€", "Ë", "Ã", "ï¿½"]

    try:
        for phone_name, url in PHONES.items():
            print(f"Seeding '{phone_name}'...")
            html = get_html(phone_name, url)
            specs_dict = parse_specs(html, phone_name)

            has_price = "Price" in specs_dict and any(specs_dict["Price"].values())
            if not has_price:
                no_price_phones.append(phone_name)

            # Deletes existing phone record first so re-running does not duplicate specs
            existing_phone = db.query(Phone).filter(Phone.model == phone_name).first()
            if existing_phone:
                db.delete(existing_phone)
                db.flush()

            phone_record = Phone(
                model=phone_name,
                url=url,
                scraped_at=datetime.utcnow(),
            )
            db.add(phone_record)
            db.flush()

            spec_count = 0
            for category, entries in specs_dict.items():
                for key, value in entries.items():
                    for marker in garbled_markers:
                        if marker in value or marker in key:
                            garbled_char_count += 1
                            if len(garbled_samples) < 5:
                                garbled_samples.append(f"{phone_name} [{category}] {key}: {value}")

                    spec_row = Spec(
                        phone_id=phone_record.id,
                        category=category,
                        key=key,
                        value=value,
                    )
                    db.add(spec_row)
                    spec_count += 1

            specs_per_phone[phone_name] = spec_count
            print(f"  Inserted {spec_count} specs across {len(specs_dict)} categories")

        db.commit()
        print("Committed all phones to database")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()

    verify_db = SessionLocal()
    try:
        total_phones = verify_db.query(Phone).count()
        total_specs = verify_db.query(Spec).count()

        print(f"Total phones in DB: {total_phones}")
        print(f"Total specs in DB: {total_specs}")
        for name, count in specs_per_phone.items():
            print(f"  {name:26}: {count} specs")

        if no_price_phones:
            print(f"Phones missing price ({len(no_price_phones)}):")
            for p in no_price_phones:
                print(f"  - {p}")
        else:
            print("All 12 phones have pricing stored")

        print(f"Garbled character count: {garbled_char_count}")
        if garbled_samples:
            for s in garbled_samples:
                print(f"  {s}")
    finally:
        verify_db.close()


if __name__ == "__main__":
    seed_database()
