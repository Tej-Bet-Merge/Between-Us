# Local-First AI Relationship Analyst

An autonomous, private desktop application that analyzes large conversational JSON exports (such as Telegram Desktop or standard chat exports) using a local language model (via [Ollama](https://ollama.com)) and deterministic conversational metrics.

The software generates structured, evidence-based relationship and friendship reviews across **9 relational dimensions**, linking every observation directly back to original chat messages with complete conversational context.

---

## 🔒 Local-First & Privacy Guarantee

- **Zero Cloud AI Services:** All inference runs on your machine via local Ollama open-weights models or the built-in deterministic offline engine. No tokens or conversation excerpts are sent over the internet.
- **Local Storage:** SQLite database with WAL (Write-Ahead Logging) stored locally in `~/.local_relationship_analyst/` (or `%USERPROFILE%\.local_relationship_analyst\`).
- **No Telemetry / Analytics:** Zero external tracking, logging, or third-party SDKs.
- **User-Controlled Data:** Permanently delete projects and associated messages with one click from the UI.

---

## 🛠️ Technology Stack

- **Application & Language:** Python 3.11+
- **Desktop UI:** PySide6 (Qt for Python) with responsive multi-tab views and background worker threads (`QThread`)
- **Database & Persistence:** SQLite with WAL mode, foreign keys, and indexes for fast pagination and context retrieval
- **Streaming Parser:** `ijson` for memory-efficient iterative parsing of multi-gigabyte exports
- **Local AI Backend:** Ollama REST API (`127.0.0.1:11434`) with local-only host verification and bounded retries
- **Schema Validation:** Pydantic v2 for structured model outputs and report serialization
- **Report Rendering:** Responsive Standalone HTML and GitHub-Flavored Markdown

---

## 🚀 Installation & Quick Start

### 1. Prerequisites
- Python 3.11 or newer
- (Optional but recommended) [Ollama](https://ollama.com) installed for local model inference

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python run.py
```
Or:
```bash
python -m relationship_analyst.app
```

---

## 🤖 Local AI Setup (Ollama)

1. **Install Ollama:** Download from [https://ollama.com](https://ollama.com).
2. **Pull a Recommended Model:**
   Open a terminal and run one of the following:
   ```bash
   # Fastest, low memory, CPU friendly (Recommended for laptops)
   ollama pull llama3.2:3b

   # Highly structured JSON output and very fast
   ollama pull qwen2.5:3b

   # High accuracy and nuanced reasoning
   ollama pull qwen2.5:7b

   # Deep analytical nuance (Requires 8GB+ RAM/VRAM)
   ollama pull llama3.1:8b
   ```
3. **Offline / Test Mode:**
   If Ollama is not installed or running, you can select the built-in **`mock:test (Built-in Deterministic Offline Engine)`** option in the model dropdown to run the entire pipeline, verify evidence citations, and explore reports without needing any external daemon or GPU.

---

## 📂 Supported Chat Export Formats

The application uses an extensible streaming adapter architecture:

### 1. Telegram Desktop JSON Export
- **How to Export:** Open Telegram Desktop &rarr; Open Chat &rarr; `...` (Chat Info) &rarr; *Export chat history* &rarr; Format: **JSON**.
- Handles text arrays, formatted entities, service messages, sticker/media mentions, and reply links.

### 2. Standard / Generic JSON Format
Top-level JSON array or object containing messages:
```json
[
  {
    "id": 101,
    "sender": "Alex",
    "timestamp": "2023-01-15T10:00:00",
    "text": "Hey Jordan, are we still meeting today?",
    "reply_to": null
  },
  {
    "id": 102,
    "sender": "Jordan",
    "timestamp": "2023-01-15T10:05:00",
    "text": "Yes! See you at 1:00pm downtown.",
    "reply_to": 101
  }
]
```

---

## 🧠 Staged Analysis Pipeline

To reliably process exports containing hundreds of thousands of messages without context window exhaustion or memory spikes, the pipeline executes in 4 distinct stages:

```
[Chat Export JSON]
       │ (Streaming ijson)
       ▼
[SQLite Storage & Indexing]
       │
       ├─► Stage A: Deterministic Statistics (Exact metrics, response times, session initiations)
       │
       ├─► Stage B: Chunk-Level Interpretation (Chronological windows of 50-100 msgs + Checkpoints)
       │
       ├─► Stage C: Temporal Aggregation (Monthly/quarterly synthesis of recurring patterns & shifts)
       │
       └─► Stage D: Final Synthesis & Evidence Validation (9 categories + SQLite citation verification)
```

1. **Stage A: Deterministic Statistics**
   - Message counts & percentages per participant.
   - Word count and message length distributions.
   - Questions asked and media shared.
   - Response-time distributions (median, mean, 75th percentile) calculated between alternating speakers.
   - Conversation sessions identified via inactivity gap threshold (> 4 hours).
   - Conversation initiation ratios.
   - Hourly, weekday, and monthly message volume trends.

2. **Stage B: Chunk-Level Interpretation**
   - Breaks conversation into chronological chunks (default: 80 messages).
   - Preserves exact message IDs and timestamps.
   - Ollama extracts structured observations conforming to Pydantic schemas.
   - **SQLite Checkpointing:** Every completed chunk is stored immediately in SQLite. If stopped or interrupted, re-running resumes from the latest checkpoint without repeating completed work.

3. **Stage C: Temporal Aggregation**
   - Aggregates chunk observations into chronological periods (months or quarters).
   - Tracks shifts, improvements, communication rhythms, and persistent patterns over time.

4. **Stage D: Final Synthesis & Evidence Validation**
   - Compiles metrics, temporal patterns, and verified citations into the complete review.
   - **Evidence Validation Engine:** Every cited message ID and quote is validated against the SQLite database. If a citation doesn't exist in the database, it is flagged as unverified.

---

## 📋 The 9 Relationship Review Categories

1. **Communication:** Openness, responsiveness, engagement, conversational rhythm, clarity, and pacing.
2. **Effort & Reciprocity:** Initiation balance, follow-through, mutual contribution, and emotional investment.
3. **Emotional Support:** Responses to vulnerability, distress, personal struggles, validation, and empathy.
4. **Affection & Warmth:** Expressions of care, appreciation, closeness, shared humor, and banter.
5. **Conflict & Repair:** Disagreements, defensiveness vs openness, accountability, apologies, and reconciliation.
6. **Trust & Reliability:** Consistency, keeping commitments, dependability, and follow-through.
7. **Boundaries & Respect:** Responses to refusals, differing opinions, personal space, and respecting stated limits.
8. **Relationship Trajectory:** Evolution of closeness, cadence, and stability across early, middle, and recent periods.
9. **Overall Relationship Assessment:** Balanced synthesis of dynamics, core strengths, recurring friction, and realistic perspectives.

*Ethical Safeguard:* The analysis explicitly avoids clinical or psychiatric diagnoses, does not speculate on telepathic intentions, and assigns confidence ratings based on evidence density.

---

## 🖥️ User Interface Overview

- **Projects View:** Overview of imported chats, message counts, date ranges, and one-click access to reports or deletion.
- **Import View:** Native file picker, automatic schema detection, streaming progress bar with live message counter.
- **Setup View:** Ollama detection, local model selector, category checkboxes, chunk size adjustment, and workload estimator.
- **Progress View:** Visual stage indicators (Stages A &rarr; D), elapsed timer, progress bar, real-time log, and safe cancellation/pause button.
- **Report View:**
  - *Executive Summary Tab*
  - *Metrics Dashboard Tab* (KPI cards, comparison table, monthly breakdown)
  - *Category Reviews Tab* (Sidebar navigation across all 9 categories with confidence badges and citations)
  - *Trajectory Tab* (Period-by-period progression)
  - *Evidence Explorer Tab* (Click any cited message to view live **surrounding conversation context** from SQLite)
  - *Export Toolbar* (Export to Standalone HTML, GitHub Markdown, or Raw JSON)

---

## 🧪 Automated Test Suite

A test suite is included in `tests/`:

- `test_importers.py`: Streaming import, Telegram and Generic formats, malformed JSON recovery, format detection, cancellation.
- `test_statistics.py`: Stage A conversational metrics, response-time percentiles, session detection with 4h boundary, initiation rates.
- `test_ollama_client.py`: Local privacy enforcement, bounded retries, code-fence JSON extraction, schema validation.
- `test_pipeline.py`: Chunking, checkpointing, resumability, Stage B/C/D execution, cancellation.
- `test_evidence_validator.py`: SQLite citation verification, unverified reference flagging, context retrieval.
- `test_reports.py`: Markdown and standalone HTML export formatting and escaping.
- `test_privacy.py`: Validation of local-only host constraints and local database storage.

Run tests:
```bash
python -m pytest tests -v
```

---

## ⚠️ Known Limitations & Next Steps

1. **Text-Only Context:** Text exports do not reflect in-person interactions, voice tone, or phone calls. The report highlights this in its limitations section.
2. **Hardware Constraints:** When running larger models (e.g. 8B+) on CPU-only machines, chunk inference takes ~5–15 seconds per chunk. For large exports on low-spec hardware, choose smaller models (`llama3.2:3b`, `qwen2.5:3b`) or run limited test samples first.
3. **Future Adapters:** Additional chat export adapters (e.g., WhatsApp `.txt` exports, Discord JSON) can be added by implementing `BaseChatImporter`.
