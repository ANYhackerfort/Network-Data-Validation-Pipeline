import os, re, time
from pathlib import Path
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor, as_completed

# ============ Paths ============
try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd()

OUTPUT_DIR = BASE_DIR / "outputs"

# ============ Parser ============
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

def compute_pair(args):
    i, j, a, b = args
    d = dtw_distance(a, b)
    return (i, j, d)

# ============ Main ============
if __name__ == "__main__":
    output_files = sorted(OUTPUT_DIR.glob("output_*.txt"))
    if not output_files:
        print("⚠️ No Mahimahi output files found.")
        exit(1)

    print(f"🟩 Found {len(output_files)} Mahimahi files.")
    series_list = []
    distance_values = []

    plt.ion()
    fig, ax = plt.subplots(figsize=(8, 6))

    # Use all physical CPU cores
    max_workers = os.cpu_count() or 4

    for idx, file_path in enumerate(output_files, start=1):
        ys = read_mahi_series(file_path)
        series_list.append(ys)
        print(f"Loaded file {idx}: {file_path.name} ({len(ys)} samples)")

        if idx > 1:
            # Prepare comparison tasks (this file vs all previous)
            tasks = [(j + 1, idx, series_list[j], ys) for j in range(idx - 1)]
            results = []

            # Parallel DTW computation
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(compute_pair, t) for t in tasks]
                for future in as_completed(futures):
                    i, j, d = future.result()
                    results.append(d)
                    print(f"DTW({i},{j}) = {d:.3f}")

            # Append new distances
            distance_values.extend(results)

            # ----- Update live histogram -----
            ax.clear()
            ax.hist(distance_values, bins=25, density=True,
                    alpha=0.7, edgecolor='black')
            ax.set_xlabel("Normalized DTW Distance")
            ax.set_ylabel("Density")
            ax.set_title(f"Live Histogram of DTW Distances (Up to file {idx})")
            ax.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.pause(0.1)

    plt.ioff()
    plt.show()
