import os, re
from pathlib import Path
from itertools import combinations
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

# ============ Paths ============
try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd()

QDISC_DIR = BASE_DIR / "tmp"
OUTPUT_DIR = BASE_DIR / "outputs"

# Use separate cache files for each mode
CACHE_FILE_QDISC = BASE_DIR / "dtw_cache_qdisc.txt"
CACHE_FILE_MAHI = BASE_DIR / "dtw_cache_mahi.txt"

# ============ Configuration ============
COMPARE_QDISC = True  # Set to False to compare mahi_*.txt instead
CACHE_FILE = CACHE_FILE_QDISC if COMPARE_QDISC else CACHE_FILE_MAHI

# ============ Parsers ============
def read_qdisc_series(path: str | Path):
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

def read_mahi_series(path: str | Path):
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
    return prev[m] / max(n, m)

def compute_dtw_for_pair(pair, series_dict):
    i, j = pair
    a, b = series_dict[i], series_dict[j]
    if not a or not b:
        return (i, j, None)
    d = dtw_distance(a, b)
    return (i, j, d)

# ============ Cache Utilities ============
def load_cache(path: Path):
    cache = {}
    if not path.exists():
        return cache
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != 3:
                continue
            i, j, d = int(parts[0]), int(parts[1]), float(parts[2])
            cache[(i, j)] = d
            cache[(j, i)] = d
    return cache

def append_to_cache(path: Path, i, j, d):
    with open(path, "a") as f:
        f.write(f"{i},{j},{d:.6f}\n")

# ============ Main ============
if __name__ == "__main__":
    qdisc_files = sorted(QDISC_DIR.glob("qdisc_*.log"))
    output_files = sorted(OUTPUT_DIR.glob("output_*.txt"))
    series_dict = {}

    if COMPARE_QDISC:
        print("🟦 Mode: QDISC (using tmp/qdisc_*.log files)")
        for f in qdisc_files:
            idx = int(f.stem.split("_")[1])
            series_dict[idx] = read_qdisc_series(f)
    else:
        print("🟩 Mode: MAHIMAHI (using outputs/output_*.txt files)")
        for f in output_files:
            idx = int(f.stem.split("_")[1])
            series_dict[idx] = read_mahi_series(f)

    if not series_dict:
        print("⚠️ No files found for this mode. Check your directory paths.")
        exit(1)

    keys = list(series_dict.keys())
    pairs = list(combinations(keys, 2))

    cache = load_cache(CACHE_FILE)
    distances = dict(cache)
    distance_values = [d for (i, j), d in cache.items() if i < j]

    # Filter out pairs already cached
    pairs_to_compute = [pair for pair in pairs if pair not in cache]

    print(f"Loaded {len(series_dict)} series.")
    print(f"Found {len(cache)} cached DTWs.")
    print(f"Computing {len(pairs_to_compute)} new pairs...")

    # ---------- Parallelized DTW ----------
    if pairs_to_compute:
        with ProcessPoolExecutor() as executor:
            futures = {executor.submit(compute_dtw_for_pair, pair, series_dict): pair for pair in pairs_to_compute}
            for future in as_completed(futures):
                i, j, d = future.result()
                if d is not None:
                    print(f"DTW({i},{j}) = {d:.3f}")
                    distances[(i, j)] = d
                    distances[(j, i)] = d
                    distance_values.append(d)
                    append_to_cache(CACHE_FILE, i, j, d)

    # ---------- Distance Matrix ----------
    if distances:
        all_indices = sorted(series_dict.keys())
        matrix_df = pd.DataFrame(index=all_indices, columns=all_indices, dtype=float)
        for (i, j), d in distances.items():
            matrix_df.at[i, j] = d

        plt.figure(figsize=(10, 8))
        sns.heatmap(matrix_df, annot=True, fmt=".2f", cmap="coolwarm", cbar_kws={"label": "Normalized DTW"})
        plt.title("Pairwise Normalized DTW Matrix" + (" (QDISC)" if COMPARE_QDISC else " (MAHIMAHI)"))
        plt.xlabel("Index")
        plt.ylabel("Index")
        plt.tight_layout()
        plt.show()

    # ---------- CDF Plot ----------
    if distance_values:
        sorted_vals = sorted(distance_values)
        cdf = [i / len(sorted_vals) for i in range(len(sorted_vals))]

        plt.figure(figsize=(8, 6))
        plt.plot(sorted_vals, cdf, linewidth=2)
        plt.xlabel("Normalized DTW Distance")
        plt.ylabel("CDF")
        plt.title("CDF of Normalized DTW Distances")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    # ---------- PDF Plot ----------
    if distance_values:
        plt.figure(figsize=(8, 6))
        plt.hist(distance_values, bins=30, density=True, alpha=0.7, edgecolor='black')
        plt.xlabel("Normalized DTW Distance")
        plt.ylabel("Probability Density")
        plt.title("PDF of Normalized DTW Distances")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    # ---------- Boxplot ----------
    if distance_values:
        plt.figure(figsize=(8, 5))
        box = plt.boxplot(distance_values, patch_artist=True, showmeans=True)
        for patch in box['boxes']:
            patch.set_facecolor('#a2cffe')

        plt.xticks([])
        plt.ylabel("Normalized DTW Distance")
        plt.title("Boxplot of Normalized DTW Distances (with Mean)")
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()
