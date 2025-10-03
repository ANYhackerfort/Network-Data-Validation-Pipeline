import os
import re
from pathlib import Path
from itertools import product
from multiprocessing import Pool, cpu_count
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# ============ Paths ============
BASE_DIR = Path(__file__).resolve().parent
QDISC_DIR = BASE_DIR / "tmp"
OUTPUT_DIR = BASE_DIR / "outputs"
CACHE_FILE = BASE_DIR / "dtw_cache.txt"
CACHE_TAG = "B"

# ============ Config ============
NUM_PROCESSES = max(1, cpu_count() - 1)

# ============ Parsers ============
def read_qdisc_series(path: Path):
    ys = []
    pending = False
    with open(path, "r") as f:
        for line in f:
            if re.match(r"^------ .+ ------\s*$", line):
                pending = True
                continue
            if pending:
                m = re.search(r"backlog\s+(\d+)b\s+\d+p", line)
                if m:
                    ys.append(int(m.group(1)))
                    pending = False
    return ys

def read_mahi_series(path: Path):
    ys = []
    with open(path, "r") as f:
        for line in f:
            if "queue size in bytes:" in line:
                try:
                    ys.append(int(line.strip().split(":")[-1].strip()))
                except ValueError:
                    pass
    return ys

# ============ DTW ============
def dtw_distance(a, b):
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return float(abs(sum(a) - sum(b)))
    INF = float("inf")
    prev = [INF] * (m + 1)
    curr = [INF] * (m + 1)
    prev[0] = 0.0
    for i in range(1, n + 1):
        curr[0] = INF
        ai = a[i - 1]
        for j in range(1, m + 1):
            bj = b[j - 1]
            cost = abs(ai - bj)
            curr[j] = cost + min(prev[j], curr[j - 1], prev[j - 1])
        prev, curr = curr, prev
    return prev[m]

# ============ Cache I/O ============
def load_cache(path: Path, tag="B"):
    cache = {}
    if not path.exists():
        return cache
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 4 and parts[3] == tag:
                i, j = int(parts[0]), int(parts[1])
                d = float(parts[2])
                cache[(i, j)] = d
    return cache

def append_to_cache(path: Path, i: int, j: int, d: float, tag="B"):
    with open(path, "a") as f:
        f.write(f"{i},{j},{d:.6f},{tag}\n")

# ============ Worker ============
def compute_pair(pair):
    qi, qf, oi, of = pair
    q_series = read_qdisc_series(qf)
    o_series = read_mahi_series(of)
    if not q_series or not o_series:
        return None
    d = dtw_distance(q_series, o_series)
    d /= max(len(q_series), len(o_series))  # normalize
    return (qi, oi, d)

# ============ Main ============
if __name__ == "__main__":
    qdisc_files = sorted([f for f in QDISC_DIR.glob("qdisc_*.log")])
    output_files = sorted([f for f in OUTPUT_DIR.glob("output_*.txt")])
    qdisc_pairs = [(int(f.stem.split("_")[1]), f) for f in qdisc_files]
    mahi_pairs = [(int(f.stem.split("_")[1]), f) for f in output_files]

    cache = load_cache(CACHE_FILE, tag="B")
    jobs = []

    for (qi, qf), (oi, of) in product(qdisc_pairs, mahi_pairs):
        if (qi, oi) not in cache:
            jobs.append((qi, qf, oi, of))

    print(f"Computing {len(jobs)} new DTW pairs (qdisc × mahimahi)...")

    results = []
    if jobs:
        with Pool(processes=NUM_PROCESSES) as pool:
            for result in pool.imap_unordered(compute_pair, jobs):
                if result:
                    qi, oi, d = result
                    print(f"DTW({qi}, {oi}) = {d:.3f}")
                    append_to_cache(CACHE_FILE, qi, oi, d, tag="B")
                    cache[(qi, oi)] = d
                    results.append(d)
    else:
        results = list(cache.values())

    # ========== Plotting ==========
    print(f"Loaded {len(cache)} total DTW distances with tag B")

    if results:
        sorted_d = sorted(results)
        cdf = [i / len(sorted_d) for i in range(len(sorted_d))]

        # CDF
        plt.figure(figsize=(8, 6))
        plt.plot(sorted_d, cdf, linewidth=2)
        plt.xlabel("Normalized DTW Distance")
        plt.ylabel("CDF")
        plt.title("CDF — Normalized DTW (qdisc × mahimahi)")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        # PDF
        plt.figure(figsize=(8, 6))
        sns.histplot(results, bins=30, kde=True, stat="density", edgecolor='black', alpha=0.7)
        plt.xlabel("Normalized DTW Distance")
        plt.ylabel("Density")
        plt.title("PDF — Normalized DTW (qdisc × mahimahi)")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        # Boxplot
        plt.figure(figsize=(8, 5))
        box = plt.boxplot(results, patch_artist=True, showmeans=True)
        for patch in box['boxes']:
            patch.set_facecolor('#a2cffe')
        plt.xticks([])
        plt.ylabel("Normalized DTW Distance")
        plt.title("Box Plot — Normalized DTW Distances (qdisc × mahimahi)")
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()

        # Heatmap
        matrix_df = pd.DataFrame(index=sorted(set(qi for qi, _ in cache)),
                                 columns=sorted(set(oi for _, oi in cache)),
                                 dtype=float)
        for (qi, oi), d in cache.items():
            matrix_df.at[qi, oi] = d

        plt.figure(figsize=(10, 8))
        sns.heatmap(matrix_df, annot=True, fmt=".3f", cmap="YlGnBu", cbar_kws={"label": "Normalized DTW Distance"})
        plt.xlabel("Output_Y Index (mahimahi)")
        plt.ylabel("Qdisc_X Index (qdisc)")
        plt.title("DTW Distance Matrix — qdisc vs mahimahi")
        plt.tight_layout()
        plt.show()