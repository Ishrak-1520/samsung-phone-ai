import os
import sys
import time
from dotenv import load_dotenv
import requests
from sqlalchemy import text

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from db.database import SessionLocal

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# nomic-embed-text requires search_query prefix for questions
QUERY_PREFIX = "search_query: "

CATEGORY_KEYWORDS: dict[str, str] = {
    "battery": "Battery",
    "battery life": "Battery",
    "charging": "Battery",
    "camera": "Main Camera",
    "photo": "Main Camera",
    "selfie": "Selfie Camera",
    "front camera": "Selfie Camera",
    "display": "Display",
    "screen": "Display",
    "performance": "Our Tests",
    "benchmark": "Our Tests",
    "antutu": "Our Tests",
    "geekbench": "Our Tests",
    "processor": "Platform",
    "chipset": "Platform",
    "cpu": "Platform",
    "gpu": "Platform",
    "storage": "Memory",
    "memory": "Memory",
    "ram": "Memory",
    "price": "Price",
    "cost": "Price",
    "cheap": "Price",
    "expensive": "Price",
    "affordable": "Price",
    "network": "Network",
    "5g": "Network",
    "connectivity": "Comms",
    "wifi": "Comms",
    "bluetooth": "Comms",
    "nfc": "Comms",
    "build": "Body",
    "design": "Body",
    "weight": "Body",
    "size": "Body",
    "dimensions": "Body",
}

PHONE_ALIASES: dict[str, str] = {
    "s21": "Samsung Galaxy S21",
    "s22": "Samsung Galaxy S22",
    "s22 ultra": "Samsung Galaxy S22 Ultra",
    "s23": "Samsung Galaxy S23",
    "s23+": "Samsung Galaxy S23+",
    "s23 plus": "Samsung Galaxy S23+",
    "s23 ultra": "Samsung Galaxy S23 Ultra",
    "s24": "Samsung Galaxy S24",
    "s24 ultra": "Samsung Galaxy S24 Ultra",
    "a54": "Samsung Galaxy A54",
    "a34": "Samsung Galaxy A34",
    "z flip5": "Samsung Galaxy Z Flip5",
    "flip5": "Samsung Galaxy Z Flip5",
    "z fold5": "Samsung Galaxy Z Fold5",
    "fold5": "Samsung Galaxy Z Fold5",
}

ALL_PHONES_TRIGGERS = [
    "which phone", "which samsung", "best battery", "best camera",
    "best display", "best performance", "highest score", "lowest price",
    "most affordable", "compare all", "all phones", "lasts longest",
    "battery life", "longest battery",
]


def get_query_embedding(question: str) -> list[float]:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": EMBEDDING_MODEL, "prompt": QUERY_PREFIX + question}

    for attempt in range(1, 4):
        response = requests.post(url, json=payload, timeout=60)
        # Ollama can briefly return 500 while swapping models into GPU
        if response.status_code == 500 and attempt < 3:
            time.sleep(4)
            continue
        response.raise_for_status()
        return response.json()["embedding"]


def detect_phones(question: str) -> list[str]:
    q = question.lower()
    found = []
    # Longer aliases checked first so e.g. 's23 ultra' matches before 's23'
    for alias, full_name in sorted(PHONE_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q and full_name not in found:
            found.append(full_name)
            # Blank out matched alias so shorter substring aliases cannot re-match
            q = q.replace(alias, " " * len(alias), 1)
    return found


def detect_category(question: str) -> str | None:
    q_lower = question.lower()
    for keyword, category in sorted(CATEGORY_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in q_lower:
            return category
    return None


def is_all_phones_question(question: str) -> bool:
    q_lower = question.lower()
    return any(trigger in q_lower for trigger in ALL_PHONES_TRIGGERS)


def is_battery_life_question(question: str) -> bool:
    triggers = [
        "battery life", "best battery", "lasts longest", "longest battery",
        "endurance", "how long does", "how long will", "battery score",
    ]
    q_lower = question.lower()
    return any(t in q_lower for t in triggers)


def search(question: str, top_k: int = 5, phone: str = None, category: str = None) -> list[dict]:
    db = SessionLocal()
    try:
        query_vector = get_query_embedding(question)
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"
        all_phones = is_all_phones_question(question)

        if all_phones and category:
            sql = text("""
                SELECT p.model AS phone, e.category, e.chunk_text,
                       e.embedding <=> CAST(:vec AS vector) AS distance
                FROM embeddings e
                JOIN phones p ON p.id = e.phone_id
                WHERE e.category = :cat
                ORDER BY distance ASC
            """)
            rows = db.execute(sql, {"vec": vector_str, "cat": category}).fetchall()
        else:
            where_parts = []
            params: dict = {"vec": vector_str, "top_k": top_k}

            if phone:
                where_parts.append("p.model = :phone")
                params["phone"] = phone
            if category:
                where_parts.append("e.category = :cat")
                params["cat"] = category

            where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
            sql = text(f"""
                SELECT p.model AS phone, e.category, e.chunk_text,
                       e.embedding <=> CAST(:vec AS vector) AS distance
                FROM embeddings e
                JOIN phones p ON p.id = e.phone_id
                {where_clause}
                ORDER BY distance ASC
                LIMIT :top_k
            """)
            rows = db.execute(sql, params).fetchall()

        return [
            {
                "phone": row.phone,
                "category": row.category,
                "chunk_text": row.chunk_text,
                "distance": round(row.distance, 4),
            }
            for row in rows
        ]
    finally:
        db.close()


def search_two_categories(question: str, cat1: str, cat2: str, phone: str = None) -> list[dict]:
    results = []
    for cat in [cat1, cat2]:
        results += search(question, top_k=12, phone=phone, category=cat)
    return results


def smart_search(question: str, top_k: int = 5) -> list[dict]:
    detected_phones = detect_phones(question)
    detected_category = detect_category(question)
    all_phones = is_all_phones_question(question)
    battery_life_q = is_battery_life_question(question)

    if battery_life_q and all_phones:
        return search_two_categories(question, "Battery", "Our Tests")

    if battery_life_q and len(detected_phones) == 1:
        return search_two_categories(question, "Battery", "Our Tests", phone=detected_phones[0])

    if all_phones and detected_category:
        return search(question, top_k=top_k, category=detected_category)

    if len(detected_phones) == 1 and detected_category:
        return search(question, top_k=1, phone=detected_phones[0], category=detected_category)

    if len(detected_phones) > 1 and detected_category:
        results = []
        for phone_name in detected_phones:
            results += search(question, top_k=1, phone=phone_name, category=detected_category)
        return results

    if detected_phones:
        results = []
        for phone_name in detected_phones:
            results += search(question, top_k=top_k, phone=phone_name)
        return results

    return search(question, top_k=top_k)


if __name__ == "__main__":
    for q in [
        "What are the camera specs of the Samsung Galaxy S23?",
        "Which Samsung phone has the best battery life?",
        "camera specs of the S23 Ultra",
    ]:
        print(f"\nQuestion: {q}")
        for r in smart_search(q):
            print(f"  [{r['phone']}] {r['category']} (dist: {r['distance']})")
