# ===========================
# OpenRouter parallel runner 
# ===========================
# - Processes ALL rows every run (overwrites outputs)
# - Per-model throttles (workers/rps)
# - Exponential backoff for 408/429/5xx (+ Retry-After)
# - Threaded batching + single writer thread
#
# Before running this cell:
#   import os; os.environ["OPENROUTER_API_KEY"] = "sk-or-..."

import os, time, json, hashlib, re, random, csv, math, threading
import requests
import pandas as pd
from datetime import datetime, timezone
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.colab import drive

# -------- Mount Drive --------
drive.mount('/content/drive')  # no-op if already mounted

# -------- Paths --------
ROOT_DIR  = "/content/drive/MyDrive/Models Bias"
INPUT_CSV = f"{ROOT_DIR}/runs_to_do.csv"
OUT_BASE  = f"{ROOT_DIR}/runs_done_New_7500_openrouter"  # outputs -> OUT_BASE_<modelslug>.csv
assert os.path.exists(INPUT_CSV), f"Not found: {INPUT_CSV}"

# -------- Model map (OpenRouter IDs) --------
MODEL_MAP = {
    "chatgpt-4o": "openai/gpt-4o",
    "llama3.3": "meta-llama/llama-3.3-70b-instruct",
    "gemini2.5": "google/gemini-2.5-pro",
    "claude-sonnet-4": "anthropic/claude-sonnet-4",
    "qwen2.5": "qwen/qwen-2.5-72b-instruct",   # change to non-:free if you have paid access
    # Example paid swap:
    # "qwen2.5": "qwen/qwen-2.5-72b-instruct",
}
# -------- Per-model throttles (override globals) --------
# Free-tier safe defaults. If you’re on a paid tier, raise rps/workers for that model.
PER_MODEL_LIMITS = {
    "qwen2.5":         {"workers": 4, "rps": 3.0},  # free ~12/min; for paid try rps=3.0, workers=4–6
    "llama3.3":        {"workers": 4, "rps": 3.0},
    "chatgpt-4o":      {"workers": 6, "rps": 3.0},
    "gemini2.5":       {"workers": 6, "rps": 3.0},
    "claude-sonnet-4": {"workers": 6, "rps": 3.0},
}
# -------- Which models to run --------
# MODEL_KEYS = None                   # run ALL in MODEL_MAP
MODEL_KEYS = ["#####"]              # example: run Qwen only

# -------- Inference settings --------
TEMPERATURE = 0.0
MAX_TOKENS  = 300
SEED        = 42
PILOT_N     = None            # e.g., 500 for a small pilot; None for full run
MAX_WORKERS = 4               # defaults used if model has no override
MAX_RPS     = 3.0            # defaults used if model has no override
SLEEP_JITTER_MAX = 0.03       # small random jitter to decorrelate calls

# -------- No-resume flag (always overwrite & re-run everything) --------
RESUME = False

# -------- OpenRouter API --------
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip() or "sk-000000"
if not API_KEY:
    raise SystemExit("No OPENROUTER_API_KEY set. In Colab: os.environ['OPENROUTER_API_KEY'] = 'sk-or-...'")

API_URL      = "https://openrouter.ai/api/v1/chat/completions"
HTTP_REFERER = "https://colab.research.google.com"
X_TITLE      = "ExportControl Bias Experiment"

# -------- Load input --------
runs = pd.read_csv(INPUT_CSV)
required_cols = {"project_id","iso3","country_name","condition","prompt_text"}
missing = required_cols - set(runs.columns)
if missing:
    raise SystemExit(f"runs_to_do.csv is missing columns: {sorted(missing)}")

# Stable unique id per row (useful for auditing; not used for resume here)
def compute_run_id(row):
    m = hashlib.sha256()
    m.update(str(row["project_id"]).encode())
    m.update(str(row["iso3"]).encode())
    m.update(str(row["condition"]).encode())
    m.update(str(row["prompt_text"]).encode())
    return m.hexdigest()[:16]

if "run_id" not in runs.columns:
    runs["run_id"] = runs.apply(compute_run_id, axis=1)

# Deterministic shuffle + optional pilot
random.seed(SEED)
runs = runs.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
if PILOT_N is not None:
    runs = runs.head(PILOT_N).copy()

# -------- Model selection normalisation --------
if MODEL_KEYS is None:
    keys_to_run = list(MODEL_MAP.keys())
elif isinstance(MODEL_KEYS, str):
    keys_to_run = [MODEL_KEYS.strip()]
else:
    keys_to_run = list(MODEL_KEYS)
unknown = [k for k in keys_to_run if k not in MODEL_MAP]
if unknown:
    raise ValueError(f"Unknown model key(s): {unknown}. Valid: {list(MODEL_MAP.keys())}")
print("Models to run:", keys_to_run)

# -------- Helpers --------
def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()

YESNO_RE = re.compile(r"\b(YES|NO)\b", re.IGNORECASE)
def parse_decision_and_rationale(text: str):
    if not isinstance(text, str) or not text.strip():
        return None, ""
    m = YESNO_RE.search(text)
    decision = m.group(1).upper() if m else None
    m2 = re.search(r"(?is)\bRationale\s*:\s*(.+)", text)
    if m2:
        rationale = m2.group(1).strip()
    else:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        rationale = "\n".join(lines[1:]) if len(lines) > 1 else (lines[0] if lines else "")
    return decision, rationale

def ensure_outfile(path):
    if not os.path.exists(path):
        cols = [
            "run_id","timestamp_utc",
            "project_id","iso3","country_name","condition",
            "baseline_partner_count","bloc","region",
            "model_key","model_id","model_version","latency_ms",
            "decision","rationale","raw_response","error",
            "prompt_tokens","completion_tokens","total_tokens"
        ]
        pd.DataFrame(columns=cols).to_csv(path, index=False)

class SoftRateLimiter:
    def __init__(self, rps):
        self.min_interval = 1.0 / max(rps, 0.001)
        self._lock = threading.Lock()
        self._last = 0.0
    def wait(self):
        with self._lock:
            now = time.time()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.time()

def call_openrouter(session: requests.Session, model_id: str, prompt: str, limiter: SoftRateLimiter,
                    temperature: float = TEMPERATURE, max_tokens: int = MAX_TOKENS, seed: int = SEED,
                    max_retries: int = 8, backoff_base: float = 1.4, backoff_cap: float = 60.0):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": HTTP_REFERER,
        "X-Title": X_TITLE,
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a careful export-control assistant. Be concise and deterministic."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "seed": seed,
    }

    tries = 0
    while True:
        tries += 1
        limiter.wait()
        if SLEEP_JITTER_MAX > 0:
            time.sleep(random.random() * SLEEP_JITTER_MAX)

        t0 = time.time()
        try:
            # Increase timeout: (connect, read). Helps avoid 408s on slower models.
            resp = session.post(API_URL, headers=headers, data=json.dumps(payload),
                                timeout=(15, 240))
            latency_ms = int((time.time() - t0) * 1000)
        except requests.RequestException as e:
            if tries <= max_retries:
                sleep_s = min(backoff_cap, backoff_base ** tries + random.random())
                time.sleep(sleep_s)
                continue
            raise RuntimeError(f"NetworkError after {tries} tries: {e}")

        if resp.status_code == 200:
            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:
                content = json.dumps(data)
            usage = data.get("usage", {}) or {}
            model_version = data.get("model", model_id)
            return {
                "content": content,
                "latency_ms": latency_ms,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
                "model_version": model_version,
            }

        # Treat 408/429/5xx as retryable
        RETRYABLE = (408, 429, 500, 502, 503, 504)
        if resp.status_code in RETRYABLE and tries <= max_retries:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    sleep_s = float(retry_after)
                except ValueError:
                    sleep_s = min(backoff_cap, backoff_base ** tries + random.random())
            else:
                sleep_s = min(backoff_cap, backoff_base ** tries + random.random())
            time.sleep(sleep_s)
            continue

        snippet = resp.text[:400]
        raise RuntimeError(f"HTTP {resp.status_code} (tries={tries}): {snippet}")

# -------- Main loop per model (NO RESUME: overwrite & run ALL rows) --------
def run_model(model_key: str, model_id: str):
    out_csv = f"{OUT_BASE}_{slugify(model_key)}.csv"

    # Overwrite output if exists (no-resume)
    if not RESUME and os.path.exists(out_csv):
        os.remove(out_csv)
    ensure_outfile(out_csv)

    todo = runs.copy()  # run ALL rows
    print(f"\n=== {model_key} -> {model_id} ===")
    print(f"Total rows to run now: {len(todo)} (resume disabled)")

    # Per-model limits
    limits = PER_MODEL_LIMITS.get(model_key, {})
    local_workers = limits.get("workers", MAX_WORKERS)
    local_rps     = limits.get("rps", MAX_RPS)

    limiter = SoftRateLimiter(local_rps)

    # Single writer thread (append-only)
    writer_q: Queue = Queue(maxsize=1000)
    writer_stop = object()
    def writer():
        with open(out_csv, "a", newline="", encoding="utf-8") as f:
            fieldnames = [
                "run_id","timestamp_utc",
                "project_id","iso3","country_name","condition",
                "baseline_partner_count","bloc","region",
                "model_key","model_id","model_version","latency_ms",
                "decision","rationale","raw_response","error",
                "prompt_tokens","completion_tokens","total_tokens"
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            while True:
                item = writer_q.get()
                if item is writer_stop:
                    break
                w.writerow(item)
                f.flush()
                writer_q.task_done()

    wt = threading.Thread(target=writer, daemon=True)
    wt.start()

    # Worker for each row
    session = requests.Session()
    def worker(row_dict):
        prompt = row_dict["prompt_text"]
        error = ""
        decision = rationale = None
        raw = ""
        latency_ms = None
        usage = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        model_version = model_id

        try:
            resp = call_openrouter(session, model_id, prompt, limiter)
            raw = resp["content"]
            latency_ms = resp["latency_ms"]
            usage = resp["usage"]
            model_version = resp["model_version"]
            decision, rationale = parse_decision_and_rationale(raw)
            if decision not in {"YES","NO"}:
                error = "ParseError: decision not found"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        out_row = {
            "run_id": row_dict["run_id"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "project_id": row_dict["project_id"],
            "iso3": row_dict["iso3"],
            "country_name": row_dict["country_name"],
            "condition": row_dict["condition"],
            "baseline_partner_count": row_dict.get("baseline_partner_count"),
            "bloc": row_dict.get("bloc"),
            "region": row_dict.get("region"),
            "model_key": model_key,
            "model_id": model_id,
            "model_version": model_version,
            "latency_ms": latency_ms,
            "decision": decision,
            "rationale": rationale,
            "raw_response": raw,
            "error": error,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        writer_q.put(out_row)

    # Dispatch in parallel (per model)
    rows_iter = (todo.iloc[i].to_dict() for i in range(len(todo)))
    with ThreadPoolExecutor(max_workers=local_workers) as ex:
        futures = [ex.submit(worker, row_dict) for row_dict in rows_iter]
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 200 == 0:
                print(f"{model_key}: {done}/{len(futures)} completed...")

    # Finish writer
    writer_q.put(writer_stop)
    wt.join()
    print(f"Saved results -> {out_csv}")

# -------- Run each selected model (sequential per model; parallel inside) --------
for key in keys_to_run:
    run_model(key, MODEL_MAP[key])

print("All models completed.")


