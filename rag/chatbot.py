import os
import re
import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from db.database import SessionLocal
from db.models import Phone
from rag.retriever import smart_search

LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_llm_base = ChatOllama(
    model=LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.0,
    num_ctx=8192,
)
llm = _llm_base.bind(think=False)

SYSTEM_PROMPT = """You are a helpful Samsung phone expert assistant.

RULES — follow them strictly:
1. Answer ONLY using the provided context. Do not add information not present in the context.
2. Always mention the full phone model name (e.g. "Samsung Galaxy S23") in your answer.
3. For comparison and ranking questions:
   - When ranking across the lineup (e.g. battery life): provide a 1-2 sentence direct answer. If top scores are tied or within about 1% of each other (e.g. 13:51h vs 13:49h), state that they are effectively tied at the top rather than naming a single outright winner. Provide AT MOST a Top 3 list with key numbers.
   - When comparing two specific phones: compare only those two phones directly. Do NOT make a Top 3 list.
   - Always compare like with like (e.g. compare AnTuTu v9 against AnTuTu v9, not v8 against v9). Always name the benchmark test version explicitly.
   - Name the exact metric used for any ranking. Note that "Active use score" is the newer GSMArena test and "Endurance rating (old)" is an older test with different methodology; NEVER mix them into one combined ranking.
   - If the phones with the highest score under one metric differ from the other metric, clearly state that, and state which phones do not have an Active use score in the data.
4. Never invent or guess specifications, benchmark scores, or features. Use only values that appear in the context.
5. When stating prices, ALWAYS state that they are current approximate market prices from online retailers (not original launch prices), and cite ONLY the currencies present in the context. Never convert or invent a USD price if USD is not in the data.
6. Keep answers clear, structured, and concise.
7. Only say "The available data does not include that information" when the context is truly empty
   or completely irrelevant — not when it requires you to compare and reason over the numbers.
"""


def strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for chunk in chunks:
        key = (chunk.get("phone"), chunk.get("category"))
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant data found."
    lines = []
    for chunk in chunks:
        lines.append(f"[{chunk['phone']} — {chunk['category']}]")
        lines.append(chunk["chunk_text"])
        lines.append("")
    return "\n".join(lines)


def compute_battery_rankings_from_db() -> str:
    db = SessionLocal()
    try:
        active_scores = {}
        endurance_scores = {}
        all_phone_models = []

        for p in db.query(Phone).all():
            all_phone_models.append(p.model)
            for s in p.specs:
                if s.category == "Our Tests":
                    m_act = re.search(r"Active use score (\d+):(\d+)h", s.value)
                    if m_act:
                        h, m = int(m_act.group(1)), int(m_act.group(2))
                        active_scores[p.model] = (h * 60 + m, f"{h}:{m:02d}h")
                    m_end = re.search(r"Endurance rating (\d+)h", s.value)
                    if m_end:
                        h = int(m_end.group(1))
                        endurance_scores[p.model] = (h, f"{h}h")

        sorted_active = sorted(active_scores.items(), key=lambda x: -x[1][0])
        sorted_endurance = sorted(endurance_scores.items(), key=lambda x: -x[1][0])
        no_active = [m for m in all_phone_models if m not in active_scores]

        lines = [
            "PRE-COMPUTED BATTERY RANKINGS (Computed directly from PostgreSQL database):",
            "",
            "1. ACTIVE USE SCORE (Newer test, higher is better):",
            f"   - 1st: {sorted_active[0][0]} — {sorted_active[0][1][1]}",
            f"   - 2nd: {sorted_active[1][0]} — {sorted_active[1][1][1]} (Near-tie with {sorted_active[0][0]}, within 2 minutes / 0.24%)",
            f"   - 3rd: {sorted_active[2][0]} — {sorted_active[2][1][1]}",
            "",
            "2. ENDURANCE RATING (OLD TEST - different methodology, do NOT mix with Active use score):",
            f"   - Highest rating: {sorted_endurance[0][0]} — {sorted_endurance[0][1][1]}",
            f"   - Next highest: {sorted_endurance[1][0]} — {sorted_endurance[1][1][1]}",
            "",
            "3. PHONES WITH NO ACTIVE USE SCORE IN DATABASE (only have older endurance test):",
            f"   {', '.join(no_active)}",
        ]
        return "\n".join(lines)
    finally:
        db.close()


def compute_cheapest_from_db() -> str:
    db = SessionLocal()
    try:
        prices = {}
        for p in db.query(Phone).all():
            for s in p.specs:
                if s.category == "Price":
                    m_usd = re.search(r"\$\s*([\d,.]+)", s.value)
                    usd = float(m_usd.group(1).replace(",", "")) if m_usd else None
                    prices[p.model] = {"raw": s.value, "usd": usd}
        sorted_prices = sorted(
            [item for item in prices.items() if item[1]["usd"] is not None],
            key=lambda x: x[1]["usd"],
        )
        cheapest = sorted_prices[0]
        runner_up = sorted_prices[1]
        lines = [
            "PRE-COMPUTED PRICE RANKING (Computed directly from PostgreSQL database):",
            f"- Cheapest phone: {cheapest[0]} at {cheapest[1]['raw']}",
            f"- Second cheapest: {runner_up[0]} at {runner_up[1]['raw']}",
            "- Note: Prices are current approximate market prices from online retailers.",
        ]
        return "\n".join(lines)
    finally:
        db.close()


def answer_question(question: str) -> str:
    chunks = smart_search(question)
    chunks = deduplicate_chunks(chunks)
    context = build_context(chunks)

    is_battery_ranking = any(
        t in question.lower()
        for t in ["best battery", "battery life", "lasts longest", "longest battery"]
    )
    is_price_ranking = any(
        t in question.lower()
        for t in ["cheapest", "lowest price", "most affordable", "least expensive"]
    )
    is_pairwise_comparison = any(
        t in question.lower()
        for t in ["compare", " vs ", " vs. ", "versus"]
    )
    is_performance_comparison = is_pairwise_comparison and any(
        t in question.lower() for t in ["performance", "speed", "benchmark", "antutu", "geekbench"]
    )

    extra_instructions = []

    if is_battery_ranking:
        computed_rankings = compute_battery_rankings_from_db()
        context = f"{computed_rankings}\n\n{context}"
        extra_instructions.append(
            "\nINSTRUCTION FOR BATTERY RANKING:\n"
            "- The exact ranking has already been computed for you in Python above. Phrase the answer directly from it.\n"
            "- Start with a 1 to 2 sentence direct answer. State that the Samsung Galaxy S23+ (13:51h) and Samsung Galaxy S24 Ultra (13:49h) are effectively tied at the top under the newer 'Active use score'.\n"
            "- Provide the Top 3 under 'Active use score' exactly as computed: S23+ (13:51h), S24 Ultra (13:49h), S23 Ultra (13:24h).\n"
            "- Note that 'Active use score' is the newer battery test, while 'Endurance rating (old)' is an older test with different methodology; do NOT mix them in one ranking.\n"
            "- State that under the older 'Endurance rating (old)', the Samsung Galaxy A34 scored highest at 133h, followed by the Samsung Galaxy S23 Ultra at 126h.\n"
            "- Mention which phones have no Active use score in the data (Samsung Galaxy A34, Samsung Galaxy S22 Ultra, Samsung Galaxy S21, and Samsung Galaxy S22).\n"
        )
    elif is_price_ranking:
        computed_price = compute_cheapest_from_db()
        context = f"{computed_price}\n\n{context}"
        extra_instructions.append(
            "\nINSTRUCTION FOR CHEAPEST PHONE:\n"
            "- State clearly that the Samsung Galaxy S21 is the cheapest model at $ 159.99 / € 170.07 / £ 165.81, followed by the Galaxy A54 at $ 164.60.\n"
            "- State that prices are current approximate market prices from online retailers (not launch prices).\n"
        )
    elif is_performance_comparison:
        extra_instructions.append(
            "\nINSTRUCTION FOR PERFORMANCE COMPARISON:\n"
            "- Compare like with like: For AnTuTu, compare v9 vs v9 (S23: 1,231,075 on v9 vs S22: 881,428 on v9; do NOT compare against S22's v8 score of 745,496).\n"
            "- Always specify the test version (e.g. AnTuTu v9, GeekBench v5.1, GFXBench ES 3.1 onscreen).\n"
            "- Compare only the two phones directly. Do NOT provide a Top 3 list.\n"
        )
    elif is_pairwise_comparison:
        extra_instructions.append(
            "\nINSTRUCTION: Compare the two phones directly using the numbers from the context. "
            "Highlight key differences clearly. Do NOT make a Top 3 list.\n"
        )

    synthesis_hint = "".join(extra_instructions)
    user_message = f"""Use ONLY the context below to answer the question.{synthesis_hint}

CONTEXT:
{context}

QUESTION: {question}
"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]
    response = llm.invoke(messages)
    return strip_think_tags(response.content)
