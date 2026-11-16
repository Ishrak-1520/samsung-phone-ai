# Samsung Phone AI

A technical submission for the Samsung Phone Query and Review System. The system scrapes specifications for 12 selected Samsung Galaxy smartphones from GSMArena into a PostgreSQL database (with pgvector), provides a RAG-powered chatbot answering natural-language queries, runs a two-agent pipeline to generate grounded product reviews and comparisons, and exposes everything through a FastAPI REST API.

---

## Project Structure

- `agents/`: Two-agent product review and comparison pipeline
  - `agents/pipeline.py`: Orchestrates Agent 1 and Agent 2 for review and comparison workflows
  - `agents/review_agent.py`: Agent 2 (Review Writer) generates grounded product reviews and comparisons
  - `agents/spec_agent.py`: Agent 1 (Spec Retriever) queries specifications from PostgreSQL in plain Python
- `api/`: REST API layer built with FastAPI
  - `api/main.py`: FastAPI server exposing /ask, /review, and /compare endpoints
- `db/`: Database configuration, models, migration and seeding
  - `db/database.py`: SQLAlchemy database engine and session configuration
  - `db/init_db.py`: Initializes PostgreSQL tables and vector extension
  - `db/models.py`: SQLAlchemy ORM models for Phone, Spec, and Embedding
  - `db/samsung_db_dump.sql`: Complete PostgreSQL database dump with pgvector data
  - `db/seed.py`: Parses phone specifications into PostgreSQL tables
- `rag/`: Retrieval-Augmented Generation subsystem
  - `rag/chatbot.py`: RAG chatbot with context assembly and pre-computed ranking logic
  - `rag/embedder.py`: Generates and stores 768-dimensional vector embeddings using nomic-embed-text
  - `rag/retriever.py`: Hybrid semantic search and category filtering over phone embeddings
- `scraper/`: Web scraping utilities and cache
  - `scraper/scraper.py`: Fetches and parses GSMArena specification tables for 12 phones
  - `scraper/html_cache/`: Local offline HTML cache directory for scraped device pages
- `tests/`: Automated test and verification suites
  - `tests/number_checker.py`: Validates that numerical tokens in generated text exist in input data
  - `tests/verify_a.py`: Verifies chatbot responses across 7 core evaluation queries
  - `tests/verify_b.py`: Verifies two-agent review and comparison pipeline outputs and grounding
  - `tests/verify_d.py`: Verifies FastAPI REST endpoints and response formats
- `.env.example`: Template for local environment variables
- `.gitignore`: Specifies files and directories ignored by git
- `requirements.txt`: Pinned Python dependencies for the project
- `README.md`: Project documentation and setup instructions

---

## Submission

- **Repository:** `samsung-phone-ai` (https://github.com/Ishrak-1520/samsung-phone-ai.git)
- A video walkthrough is provided separately.

---

## Architecture

```mermaid
flowchart TD
    subgraph data["Data Layer"]
        GSM[GSMArena Web Pages] -->|scraper.py| Cache[scraper/html_cache/*.html]
        Cache -->|seed.py| PG[(PostgreSQL + pgvector on port 5433)]
        PG -->|embedder.py| Embeddings[embeddings table: vector 768]
    end

    subgraph chatbot["Chatbot and RAG"]
        UserQ[User Question] --> SmartSearch[rag/retriever.py smart_search]
        SmartSearch --> PG
        PG --> Context[Context Chunks]
        Context --> QwenChat[qwen3:8b via Ollama temp=0]
        QwenChat --> ChatAnswer[Final Answer]
    end

    subgraph agents["Two-Agent Pipeline"]
        PhoneInput[Target Phone / Phones] --> Agent1[Agent 1: Spec Retriever<br/>agents/spec_agent.py<br/>Direct from PostgreSQL in plain Python]
        Agent1 -->|Verbatim Spec Summary| Agent2[Agent 2: Review Writer<br/>agents/review_agent.py<br/>qwen3:8b temp=0]
        Agent2 --> FinalReview[Grounded Product Review / Comparison]
    end

    subgraph api["API Layer"]
        FastAPIApp[FastAPI api/main.py]
        FastAPIApp -->|POST /ask| UserQ
        FastAPIApp -->|GET /review/phone| Agent1
        FastAPIApp -->|POST /compare| Agent1
    end
```

---

## Tech Stack

- **Language & Runtime:** Python 3.11.9
- **Database:** PostgreSQL 16 with `pgvector` extension (Docker container `samsung-postgres`, port `5433`)
- **ORM & DB Driver:** SQLAlchemy 2.0 + `psycopg2-binary`
- **Embeddings:** `nomic-embed-text` (768 dimensions) via local Ollama
- **Large Language Model:** `qwen3:8b` via local Ollama (`temperature=0.0`, `think=False`)
- **Frameworks:** LangChain, FastAPI, Uvicorn, Pydantic, Requests, BeautifulSoup4

---

## Setup & Running Instructions

### 1. Prerequisites

- Docker Desktop running
- Ollama running locally (`http://localhost:11434`)
- Python 3.11 installed

### 2. Pull Required Ollama Models

```powershell
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

### 3. Start PostgreSQL with pgvector (Port 5433)

```powershell
docker run -d `
  --name samsung-postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=samsung_db `
  -p 5433:5432 `
  pgvector/pgvector:pg16
```

*(Port 5433 is mapped to avoid conflicting with any local PostgreSQL instance on default port 5432).*

### 4. Setup Python Virtual Environment

```powershell
cd samsung-phone-ai
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Ensure `.env` matches:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/samsung_db
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen3:8b
EMBEDDING_MODEL=nomic-embed-text
```

---

## Database Population: Choose Path A or Path B

### Path A (Recommended): Instant Restore via SQL Dump

Since the raw HTML cache files are excluded from version control via `.gitignore`, restoring the pre-populated database dump is the fastest and most reliable way to set up the system. It restores all 12 phones, 601 specifications, and 180 pre-computed 768-dimensional vector embeddings without hitting GSMArena rate limits or requiring local embedding generation.

Run these PowerShell-safe commands:

```powershell
docker cp db/samsung_db_dump.sql samsung-postgres:/tmp/dump.sql
docker exec -it samsung-postgres psql -U postgres -d samsung_db -f /tmp/dump.sql
```

*(You can now skip directly to Step 6: Start the FastAPI Server).*

---

### Path B: Build From Scratch (Init DB, Seed, Embedder)

If you wish to run the full ingestion pipeline from scratch:

> [!WARNING]
> GSMArena aggressively rate-limits automated requests with HTTP 429 when scraping all 12 device pages in rapid succession. If rate-limited, save the HTML pages manually into `scraper/html_cache/<model_slug>.html` before running `seed.py`.

1. **Initialize Database Tables:**
   Creates `phones`, `specs`, and `embeddings` tables with pgvector extension:

   ```powershell
   python -m db.init_db
   ```
2. **Seed Phone Specifications:**
   Parses HTML files from `scraper/html_cache/` (or fetches from GSMArena if cache is missing) and populates `phones` and `specs`:

   ```powershell
   python -m db.seed
   ```
3. **Generate Vector Embeddings:**
   Generates 768-dimensional embeddings for each category chunk using `nomic-embed-text`:

   ```powershell
   python -m rag.embedder
   ```

---

### 6. Start the FastAPI Server

```powershell
uvicorn api.main:app --port 8000 --reload
```

Interactive Swagger API documentation will be available at: **http://localhost:8000/docs**

---

## Endpoints, Real Requests & Responses

*Timings measured on local GPU (NVIDIA RTX 3060) with models already loaded. The first request after Ollama has been idle can take longer.*

### 1. `GET /` — Health Check

**Request:**

```powershell
curl http://localhost:8000/
```

**Response:**

```json
{
  "status": "ok",
  "message": "Samsung Phone AI is running. Visit /docs for the API.",
  "supported_phones": [
    "Samsung Galaxy A34",
    "Samsung Galaxy A54",
    "Samsung Galaxy S21",
    "Samsung Galaxy S22",
    "Samsung Galaxy S22 Ultra",
    "Samsung Galaxy S23",
    "Samsung Galaxy S23 Ultra",
    "Samsung Galaxy S23+",
    "Samsung Galaxy S24",
    "Samsung Galaxy S24 Ultra",
    "Samsung Galaxy Z Flip5",
    "Samsung Galaxy Z Fold5"
  ]
}
```

---

### 2. `POST /ask` — RAG Chatbot

**Real Timing:** ~6s (measured ~5.62s)

**Request:**

```powershell
curl.exe -X POST http://localhost:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"question": "What are the camera specs of the Samsung Galaxy S23?"}'
```

**Response:**

```json
{
  "answer": "The Samsung Galaxy S23 features a triple main camera system with the following specs:\n\n- **Wide-angle lens**: 50 MP, f/1.8, 24mm, 1/1.56\", 1.0µm, dual pixel PDAF, OIS\n- **Telephoto lens**: 10 MP, f/2.4, 70mm, 1/3.94\", 1.0µm, PDAF, OIS, 3x optical zoom\n- **Ultrawide lens**: 12 MP, f/2.2, 13mm, 120°, 1/2.55\", 1.4µm, Super Steady video\n\nVideo capabilities include 8K@24/30fps, 4K@30/60fps, 1080p@30/60/120/240fps, HDR10+, stereo sound recording, and gyro-EIS."
}
```

---

### 3. `GET /review/{phone_model}` — Agent Pipeline Review

**Real Timing:** ~17s (measured ~17.10s)

**Request:**

```powershell
curl.exe "http://localhost:8000/review/Samsung%20Galaxy%20S23"
```

**Response:**

```json
{
  "phone": "Samsung Galaxy S23",
  "review": "**Design & Build**  \nThe Samsung Galaxy S23 features a glass front and back with Gorilla Glass Victus 2, supported by an aluminum frame. It measures 146.3 x 70.9 x 7.6 mm and weighs 168 g. The device is IP68 rated, offering dust and water resistance up to 1.5m for 30 minutes. It does not have a 3.5mm headphone jack and lacks an FM radio.\n\n**Display**  \nThe phone uses a Dynamic AMOLED 2X display with a 6.1-inch size and a 19.5:9 aspect ratio. It offers a resolution of 1080 x 2340 pixels, resulting in a pixel density of 425 ppi. The display supports HDR10+ and has a peak brightness of 1750 nits, with a maximum measured brightness of 1198 nits. It is protected by Gorilla Glass Victus 2.\n\n**Performance**  \nPowered by the Qualcomm Snapdragon 8 Gen 2 chipset (4 nm), the S23 runs on Android 13 with One UI 8.5. It features an octa-core CPU with a 3.36 GHz Cortex-X3 core, and a GPU of Adreno 740. Performance benchmarks include AnTuTu 1,231,075 (v9), GeekBench 4950 (v5.1), and GFXBench 110fps (ES 3.1 onscreen).\n\n**Camera System**  \nThe main camera system includes a 50 MP wide lens, a 10 MP telephoto lens with 3x optical zoom, and a 12 MP ultrawide lens. It supports 8K video recording at 24/30fps, 4K at 30/60fps, and 1080p at up to 240fps. The camera includes features such as auto-HDR, panorama, and stereo sound recording. The front-facing camera is a 12 MP wide lens with HDR and HDR10+ support.\n\n**Battery & Charging**  \nThe S23 is equipped with a 3900 mAh Li-Ion battery. It supports 25W wired charging, achieving 50% charge in 30 minutes. Wireless charging is available at 15W (Qi), and reverse wireless charging at 4.5W. The endurance rating is 101 hours, and the active use score is 11:27h.\n\n**Connectivity & Features**  \nThe S23 supports Wi-Fi 802.11 a/b/g/n/ac/6e with tri-band capability and Wi-Fi Direct. Bluetooth 5.3 is included, along with NFC, GPS, GLONASS, BDS, and GALILEO. It features USB Type-C 3.2 with OTG support. The device includes sensors such as fingerprint (under display, ultrasonic), accelerometer, gyro, proximity, compass, and barometer. Samsung DeX and Wireless DeX are supported.\n\n**Pricing & Value**  \nThe Samsung Galaxy S23 is priced at $230.61 / €292.99 / £242.99. It is available in multiple color variants and models. The device offers a range of features including high-end display, advanced camera capabilities, and robust connectivity.\n\n**Verdict**  \nThe Samsung Galaxy S23 offers a balanced combination of performance, display quality, and camera features at its current approximate market price."
}
```

---

### 4. `POST /compare` — Agent Pipeline Comparison

**Real Timing:** ~23s (measured ~23.05s)

**Request:**

```powershell
curl.exe -X POST http://localhost:8000/compare `
  -H "Content-Type: application/json" `
  -d '{"phone1": "Samsung Galaxy S23", "phone2": "Samsung Galaxy S22"}'
```

**Response:**

```json
{
  "phone1": "Samsung Galaxy S23",
  "phone2": "Samsung Galaxy S22",
  "comparison": "**Samsung Galaxy S23 vs. Samsung Galaxy S22: A Specification-Based Comparison**\n\n**Design & Build**  \nThe Galaxy S23 measures 146.3 x 70.9 x 7.6 mm and weighs 168 g, while the Galaxy S22 measures 146 x 70.6 x 7.6 mm and weighs 167 g / 168 g (mmWave). Both phones feature a glass front and back with an aluminum frame, and both are IP68 water-resistant. The S23 uses Gorilla Glass Victus 2 on both sides, while the S22 uses Gorilla Glass Victus+.\n\n**Display**  \nBoth phones have a 6.1-inch Dynamic AMOLED 2X display with a 120Hz refresh rate and HDR10+ support. The Galaxy S23 has a peak brightness of 1750 nits and a measured maximum of 1198 nits, while the Galaxy S22 has a peak brightness of 1300 nits and a measured maximum of 982 nits. The S23 has an 86.8% screen-to-body ratio, while the S22 has an 87.4% screen-to-body ratio.\n\n**Performance**  \nThe Galaxy S23 is powered by the Qualcomm Snapdragon 8 Gen 2 (4 nm), while the Galaxy S22 uses the Exynos 2200 (4 nm) in Europe and the Snapdragon 8 Gen 1 (4 nm) in other regions. The S23 scores 1,231,075 on AnTuTu v9, compared to the S22’s 881,428 on the same benchmark. The S23 also scores 4950 on GeekBench v5.1, versus the S22’s 3682. In GFXBench ES 3.1, the S23 achieves 110fps, while the S22 reaches 69fps.\n\n**Camera System**  \nBoth phones have a triple rear camera setup with a 50 MP wide, 10 MP telephoto (3x optical zoom), and 12 MP ultrawide lens. The S23 supports 8K@24/30fps video recording, while the S22 supports 8K@24fps. Both support Super Steady video and HDR10+ on rear video. The front camera on the S23 is a 12 MP sensor with HDR10+ support, while the S22 has a 10 MP front camera with Auto-HDR.\n\n**Battery & Charging**  \nThe Galaxy S23 has a 3900 mAh battery, while the Galaxy S22 has a 3700 mAh battery. Both support 25W wired charging, 15W wireless charging, and 4.5W reverse wireless charging. The S23 has an Active use score of 11:27h, while the S22 was not tested for this metric. The S23 has an endurance rating of 101h, while the S22 has an endurance rating of 85h.\n\n**Connectivity & Features**  \nBoth phones support Wi-Fi 802.11 a/b/g/n/ac/6e (S23) and Wi-Fi 802.11 a/b/g/n/ac/6 (S22), Bluetooth 5.3 (S23) and 5.2 (S22), and NFC. Neither phone has a 3.5mm headphone jack or a radio. Both support Samsung Wireless DeX and Super Steady video.\n\n**Pricing & Value**  \nThe Galaxy S23 is priced at $230.61 / €292.99 / £242.99, while the Galaxy S22 is priced at $198.50 / €237.14 / £196.00. The S23 offers a more recent release, improved performance, and enhanced display brightness, but at a higher price point.\n\n**Verdict: Which Should You Buy?**  \nThe Samsung Galaxy S23 offers superior performance, brighter display, and newer hardware, making it the better choice for users seeking the latest technology."
}
```

---

### 5. Unknown Phone (404 Error Handling)

**Request:**

```powershell
curl.exe http://localhost:8000/review/iPhone%2015
```

**Response:**

```json
{
  "detail": {
    "error": "Phone 'iPhone 15' not found.",
    "valid_phones": [
      "Samsung Galaxy A34",
      "Samsung Galaxy A54",
      "Samsung Galaxy S21",
      "Samsung Galaxy S22",
      "Samsung Galaxy S22 Ultra",
      "Samsung Galaxy S23",
      "Samsung Galaxy S23 Ultra",
      "Samsung Galaxy S23+",
      "Samsung Galaxy S24",
      "Samsung Galaxy S24 Ultra",
      "Samsung Galaxy Z Flip5",
      "Samsung Galaxy Z Fold5"
    ]
  }
}
```

---

## Running Verification Tests

The `tests/` directory contains automated verification suites:

- **`tests/verify_a.py`**: Runs chatbot evaluation across 7 core queries (camera specs, battery rankings, S23 vs S22 performance, single-model isolation, approximate pricing, out-of-domain rejection).
- **`tests/verify_b.py`**: Runs the complete Agent 1 -> Agent 2 pipeline (A34 review, S23 review, S23 vs S22 comparison, self-comparison validation), conducts the number audit, and checks for `<think>` tag leaks.
- **`tests/verify_d.py`**: Boots a local Uvicorn instance, calls all 4 REST endpoints with valid inputs, tests unknown phone 404 handling, and prints HTTP status codes and responses.
- **`tests/number_checker.py`**: Extracts all numerical tokens from LLM output and verifies that each exists within the input specification text.

**To run the test suites:**

```powershell
python tests/verify_a.py
python tests/verify_b.py
python tests/verify_d.py
```

---

## Known Limitations & Design Decisions

1. **Approximate Current Market Prices:**
   Prices on GSMArena reflect current approximate online retailer pricing at the time of scraping, **not** original device launch prices. All prompts and outputs explicitly describe prices as current approximate market prices (never "starts at" or "launch price").
2. **Deterministic Outputs & Temperature:**
   All LLM calls operate with `temperature=0.0` and `think=False` (`strip_think_tags`) to ensure factual consistency and repeatability across runs.
3. **Python-Computed vs LLM Lineup Rankings:**For questions requiring strict numerical ranking across the lineup (e.g. "Which phone has the best battery life?" and "Which phone is the cheapest?"), the ranking is computed deterministically in Python directly from PostgreSQL values:

   - Battery: parses Active use scores as `hours:minutes` and Endurance ratings as `hours`, separates newer vs older test methodologies, and detects near-ties (within 1%).
   - Price: parses the lowest USD dollar figure from the stored Price string.
     The pre-sorted rankings are provided to the LLM to phrase the answer. Lineup questions without dedicated numerical parsers (such as screen size or general specs) rely on hybrid RAG retrieval and LLM evaluation.
4. **Number Checker Scope:**
   The number verification script (`tests/number_checker.py`) checks that every numerical token (integers, decimals, hours, percentages, currency) present in generated text appears somewhere in the source specification text provided to the writer agent. For two-phone comparisons, it verifies that numbers exist within the combined specifications of both phones; it does not independently verify attribution if both phones are discussed in the same sentence.
5. **GSMArena Rate Limiting & Offline Cache:**
   GSMArena aggressively rate-limits with HTTP 429 when multiple pages are requested in rapid succession. The scraper checks `scraper/html_cache/` first; manual HTML saves with corresponding filenames are fully supported as an offline fallback.
6. **Seed & Embedder Dependency:**
   Re-running `python -m db.seed` deletes and re-inserts phones and specs via cascade deletion, which also clears related rows in `embeddings`. Therefore, re-running `seed.py` requires re-running `python -m rag.embedder`
7. **Review wording:** Agent 2 is told to avoid evaluative filler, but an 8B model does not follow every rule every time (the example S23 review above still says "high-end display" and "robust connectivity" in its pricing section). The number checker confirms the figures, not the adjectives.
