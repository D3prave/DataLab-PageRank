import json
import time
import atexit
import argparse
import signal
import threading
from collections import deque

import redis
import requests
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import execute_values
from psycopg2 import errors as pg_errors
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

DB_CONFIG = {
    "dbname":   "DB_NAME",
    "user":     "USERNAME",
    "password": "PASSWORD",
    "host":     "localhost",
    "port":     "5432",
}
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_QUEUE = "paper_queue"
BLOOM_NAME = "processed_bloom"
BLOOM_CAP = 100_000_000
BLOOM_FP_RATE = 0.000001
QUEUE_BLOOM_NAME = "queued_bloom"
QUEUE_BLOOM_CAP = 100_000_000
QUEUE_BLOOM_FP_RATE = 0.00001

API_ROOT = "https://api.semanticscholar.org/graph/v1"
API_BATCH_LIMIT = 100
REQUEST_TIMEOUT = 30
MAX_REQUEST_ATTEMPTS = 5
API_KEY = "API_KEY"

BATCH_SIZE = API_BATCH_LIMIT
REF_PAGE_LIMIT = 99
MAX_INSERT_RETRIES = 3
INSERT_BACKOFF = 1.0
MAX_MARK_RETRIES = 3
COMMIT_EVERY = 5

DB_POOL = SimpleConnectionPool(minconn=1, maxconn=10, **DB_CONFIG)
atexit.register(DB_POOL.closeall)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
for name, cap, fp in [
    (BLOOM_NAME, BLOOM_CAP, BLOOM_FP_RATE),
    (QUEUE_BLOOM_NAME, QUEUE_BLOOM_CAP, QUEUE_BLOOM_FP_RATE),
]:
    try:
        r.execute_command("BF.RESERVE", name, fp, cap)
    except redis.ResponseError as e:
        if "exists" not in str(e).lower():
            raise

shutdown_event = threading.Event()
def _handle_signal(signum, frame):
    shutdown_event.set()
signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

class RateLimiter:
    def __init__(self, max_calls, period=1.0):
        self.calls = deque()
        self.lock = threading.Lock()
        self.max_calls = max_calls
        self.period = period
    def acquire(self):
        with self.lock:
            now = time.time()
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()
            if len(self.calls) >= self.max_calls:
                time.sleep(self.period - (now - self.calls[0]))
                now = time.time()
                while self.calls and self.calls[0] <= now - self.period:
                    self.calls.popleft()
            self.calls.append(now)

limiter = RateLimiter(1)

@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(MAX_REQUEST_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True
)
def send_request(sess, method, url, **kwargs):
    limiter.acquire()
    resp = sess.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
    if resp.status_code in {429, 500}:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                wait_time = int(retry_after)
                print(f"[WARN] 429 received. Sleeping for {wait_time}s per Retry-After header")
                time.sleep(wait_time)
            except ValueError:
                pass
        raise requests.RequestException(f"API error {resp.status_code}")
    resp.raise_for_status()
    return resp

def init_db(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_papers (
            paper_id TEXT PRIMARY KEY,
            fields_of_study TEXT[]
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS citations (
            citing_id TEXT,
            cited_id  TEXT,
            PRIMARY KEY (citing_id, cited_id)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cited ON citations(cited_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_citing ON citations(citing_id);")

def safe_insert_citations(cur, conn, rows):
    for attempt in range(1, MAX_INSERT_RETRIES + 1):
        try:
            execute_values(
                cur,
                "INSERT INTO citations (citing_id, cited_id) VALUES %s ON CONFLICT DO NOTHING",
                rows
            )
            conn.commit()
            return
        except pg_errors.DeadlockDetected:
            conn.rollback()
            if attempt == MAX_INSERT_RETRIES:
                raise
            time.sleep(INSERT_BACKOFF * (2 ** (attempt - 1)))

def mark_processed(cur, conn, fos_map):
    if not fos_map:
        return
    for attempt in range(1, MAX_MARK_RETRIES + 1):
        try:
            rows = [(pid, fos_map[pid]) for pid in fos_map]
            execute_values(
                cur,
                "INSERT INTO processed_papers (paper_id, fields_of_study) VALUES %s ON CONFLICT DO NOTHING",
                rows, template="(%s, %s)"
            )
            conn.commit()
            r.execute_command("BF.MADD", BLOOM_NAME, *fos_map.keys())
            return
        except pg_errors.DeadlockDetected:
            conn.rollback()
            if attempt == MAX_MARK_RETRIES:
                raise
            time.sleep(INSERT_BACKOFF * (2 ** (attempt - 1)))

def filter_new_ids(cur, candidate_ids):
    if not candidate_ids:
        return []
    flags = r.execute_command("BF.MEXISTS", BLOOM_NAME, *candidate_ids)
    maybe_seen = [pid for pid, f in zip(candidate_ids, flags) if f]
    new_ids = [pid for pid, f in zip(candidate_ids, flags) if not f]
    if maybe_seen:
        cur.execute("SELECT paper_id FROM processed_papers WHERE paper_id = ANY(%s)", (maybe_seen,))
        seen = {row[0] for row in cur.fetchall()}
        r.execute_command("BF.MADD", BLOOM_NAME, *seen)
        for pid in maybe_seen:
            if pid not in seen:
                new_ids.append(pid)
    return new_ids

def chunked(it, size):
    for i in range(0, len(it), size):
        yield it[i:i+size]

def reset_bloom_filters():
    r.delete(REDIS_QUEUE)
    r.delete(BLOOM_NAME)
    r.delete(QUEUE_BLOOM_NAME)
    r.execute_command("BF.RESERVE", BLOOM_NAME, BLOOM_FP_RATE, BLOOM_CAP)
    r.execute_command("BF.RESERVE", QUEUE_BLOOM_NAME, QUEUE_BLOOM_FP_RATE, QUEUE_BLOOM_CAP)
    print("[INFO] Redis queue and Bloom filters reset.")

def fetch_pages(pid, start_offset, total_refs, sess):
    MAX_OFFSET = 9999
    rows = []
    offset = start_offset
    while offset < total_refs and offset <= MAX_OFFSET:
        if shutdown_event.is_set():
            break
        end_offset = min(offset + REF_PAGE_LIMIT, total_refs, MAX_OFFSET + 1)
        print(f"[LOG] pid={pid} paginating refs {offset}→{end_offset}")
        try:
            resp = send_request(
                sess, "GET",
                f"{API_ROOT}/paper/{pid}/references",
                params={"fields": "paperId", "limit": REF_PAGE_LIMIT, "offset": offset}
            )
        except requests.RequestException as e:
            print(f"[WARN] Pagination failed for pid={pid}, offset={offset}: {e}")
            break

        data = resp.json().get("data", [])
        if not data:
            break

        for entry in data:
            rid = entry.get("paperId")
            if rid:
                rows.append((pid, rid))

        nxt = resp.json().get("next")
        if not isinstance(nxt, int) or nxt <= offset or nxt > MAX_OFFSET:
            break
        offset = nxt

    return pid, rows

def main(seeds=None, fresh=False, resume=False):
    sess = requests.Session()
    sess.headers.update({"x-api-key": API_KEY})

    # Create tables before any operation
    with DB_POOL.getconn() as conn:
        cur = conn.cursor()
        init_db(cur)
        conn.commit()
        cur.close()
        DB_POOL.putconn(conn)

    if fresh:
        reset_bloom_filters()
        with DB_POOL.getconn() as conn:
            cur = conn.cursor()
            cur.execute("TRUNCATE processed_papers, citations;")
            conn.commit()
            cur.close()
            DB_POOL.putconn(conn)
        print("[INFO] Fresh start: cleared SQL & Redis")
    elif resume:
        length = r.llen(REDIS_QUEUE)
        if length == 0:
            print("[ERROR] Resume with empty queue; use --fresh")
            return
        print(f"[INFO] Resuming crawl; queue length={length}")

    if fresh and seeds:
        r.execute_command("BF.MADD", QUEUE_BLOOM_NAME, *seeds)
        entries = [json.dumps({"id": pid}) for pid in seeds]
        r.rpush(REDIS_QUEUE, *entries)
        print(f"[INFO] Seeded {len(seeds)} IDs")

    batch_count = total = 0
    while not shutdown_event.is_set():
        batch_start = time.time()
        items = [r.lpop(REDIS_QUEUE) for _ in range(BATCH_SIZE)]
        items = [i for i in items if i]
        if not items:
            time.sleep(1)
            continue
        pids = [json.loads(i)["id"] for i in items]
        batch_count += 1
        print(f"[INFO] Batch {batch_count}: popped {len(pids)} IDs")

        conn = DB_POOL.getconn()
        cur = conn.cursor()
        try:
            to_fetch = filter_new_ids(cur, pids)
            if not to_fetch:
                continue

            fos_map = {}
            ref_rows = []

            for chunk in chunked(to_fetch, API_BATCH_LIMIT):
                if shutdown_event.is_set():
                    return
                try:
                    resp = send_request(
                        sess, "POST",
                        f"{API_ROOT}/paper/batch?fields=paperId,referenceCount,fieldsOfStudy,references.paperId",
                        json={"ids": chunk}
                    )
                except requests.RequestException as e:
                    print(f"[ERROR] Failed to fetch chunk {chunk} after retries: {e}")
                    continue

                data = resp.json()
                if not isinstance(data, list):
                    print("[ERROR] Unexpected API response:", data)
                    continue
                for rec in data:
                    if not isinstance(rec, dict):
                        print("[WARN] Skipping invalid record:", rec)
                        continue
                    pid = rec.get("paperId")
                    if not pid:
                        continue
                    total_refs = rec.get("referenceCount", 0)
                    nested = rec.get("references") or []
                    fos_map[pid] = rec.get("fieldsOfStudy") or []
                    for ref in nested:
                        rid = ref.get("paperId")
                        if rid:
                            ref_rows.append((pid, rid))
                    if total_refs > REF_PAGE_LIMIT and len(nested) > 98:
                        try:
                            pid_done, extra = fetch_pages(pid, REF_PAGE_LIMIT, total_refs, sess)
                            ref_rows.extend(extra)
                            print(f"[LOG] pid={pid_done} fetched overflow {len(extra)} refs via pagination")
                        except requests.RequestException as e:
                            print(f"[WARN] Pagination failed for pid={pid}: {e}")

            safe_insert_citations(cur, conn, ref_rows)
            mark_processed(cur, conn, fos_map)

            cited_ids = [c for _, c in ref_rows]
            new_ids = filter_new_ids(cur, cited_ids)
            if new_ids:
                flags = r.execute_command("BF.MADD", QUEUE_BLOOM_NAME, *new_ids)
                truly_new = [pid for pid, a in zip(new_ids, flags) if a]
                if truly_new:
                    entries = [json.dumps({"id": pid}) for pid in truly_new]
                    r.rpush(REDIS_QUEUE, *entries)
                    print(f"[INFO] Enqueued {len(truly_new)} new papers")

            if batch_count % COMMIT_EVERY == 0:
                conn.commit()

            total += len(to_fetch)
            batch_time = time.time() - batch_start
            print(f"[STATS] processed={total}; queue length={r.llen(REDIS_QUEUE)}; batch_time={batch_time:.2f}s")
        finally:
            cur.close()
            DB_POOL.putconn(conn)

    print("[INFO] Shutdown complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fresh", action="store_true")
    group.add_argument("--resume", action="store_true")
    parser.add_argument("seeds", nargs="*")
    args = parser.parse_args()
    main(seeds=args.seeds, fresh=args.fresh, resume=args.resume)
