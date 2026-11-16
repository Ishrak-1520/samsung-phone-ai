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

from rag.chatbot import answer_question

questions = [
    "What are the camera specs of the Samsung Galaxy S23?",
    "Which Samsung phone has the best battery life?",
    "How does the Galaxy S23 compare to the S22 in terms of performance?",
    "What are the camera specs of the Samsung Galaxy S23 Ultra?",
    "Tell me about the Galaxy S24",
    "What is the price of the Galaxy A34?",
    "What is the weather in Paris?",
]

if __name__ == "__main__":
    for idx, q in enumerate(questions, 1):
        print(f"Question {idx}: {q}")
        answer = answer_question(q)
        print(f"\n[Answer {idx}]:\n{answer}\n")

