#!/usr/bin/env python3
"""
load_test.py — Stress-test the sample app to trigger auto-scaling.
Usage: python3 load_test.py [--host HOST] [--workers N] [--duration SECS]
"""
import argparse
import threading
import time
import urllib.request

def worker(host: str, duration: int, results: list) -> None:
    end = time.time() + duration
    success = errors = 0
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://{host}:8000/load", timeout=5) as r:
                r.read()
                success += 1
        except Exception:
            errors += 1
    results.append((success, errors))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",     default="localhost")
    parser.add_argument("--workers",  type=int, default=8)
    parser.add_argument("--duration", type=int, default=120)
    args = parser.parse_args()

    print(f"Load test: {args.workers} workers × {args.duration}s → {args.host}")
    results: list = []
    threads = [
        threading.Thread(target=worker, args=(args.host, args.duration, results))
        for _ in range(args.workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_ok  = sum(r[0] for r in results)
    total_err = sum(r[1] for r in results)
    print(f"Done. Requests OK={total_ok}  Errors={total_err}")

if __name__ == "__main__":
    main()
