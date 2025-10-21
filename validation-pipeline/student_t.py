import numpy as np
from pathlib import Path
from scipy.stats import ttest_ind
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
FILES = {
    "mahi": BASE_DIR / "dtw_cache_mahi.txt",
    "qdisc": BASE_DIR / "dtw_cache_qdisc.txt",
    "both": BASE_DIR / "dtw_cache_differences.txt"
}

# ---------- Step 1: Load DTW data ----------
def load_dtw_dict(files):
    dtw_dict = {}

    # ---------- Mahi-Mahi ----------
    if files["mahi"].exists():
        with open(files["mahi"], "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    i, j, d = int(parts[0]), int(parts[1]), float(parts[2])
                    dtw_dict[(f"{i}_m", f"{j}_m")] = d

    # ---------- Qdisc ----------
    if files["qdisc"].exists():
        with open(files["qdisc"], "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    i, j, d = int(parts[0]), int(parts[1]), float(parts[2])
                    dtw_dict[(f"{i}_q", f"{j}_q")] = d

    # ---------- Differences (cross qdisc × mahi) ----------
    if files["both"].exists():  # ✅ fixed key name
        with open(files["both"], "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    qi, oi, d = int(parts[0]), int(parts[1]), float(parts[2])
                    dtw_dict[(f"{qi}_q", f"{oi}_m")] = d

    return dtw_dict

# ---------- Step 2: Build arrays ----------
# def build_distance_array(dtw_dict, tag):
#     """Flatten all pairwise distances for the specified tag."""
#     dists = []
#     for (a, b), d in dtw_dict.items():
#         if a.endswith(tag) and b.endswith(tag):
#             dists.append(d)
#     return np.array(dists)

# def build_distance_array_differences(dtw_dict):
#     """Flatten all cross-system (qdisc × mahimahi) DTW distances."""
#     dists = []
#     for (a, b), d in dtw_dict.items():
#         if a.endswith("_q") and b.endswith("_m"):
#             dists.append(d)
#     return np.array(dists)

# ---------- Step 3: Compare groups ----------
if __name__ == "__main__":
    dtw_data = load_dtw_dict(FILES) # the inner 2 group 
    # q_dists = build_distance_array(dtw_data, "_q")
    # m_dists = build_distance_array(dtw_data, "_m")
    # d_dists = build_distance_array_differences(dtw_data)
    
    # print(q_dists)

    # print(f"Loaded {len(q_dists)} Qdisc distances and {len(m_dists)} Mahi distances.")
    
    # min_len = min(len(q_dists), len(m_dists))
    
    # Extract all unique Qdisc and Mahi labels from dtw_dict keys
    q_labels = sorted({a for (a, b) in dtw_data.keys() if a.endswith("_q")} |
                    {b for (a, b) in dtw_data.keys() if b.endswith("_q")})

    m_labels = sorted({a for (a, b) in dtw_data.keys() if a.endswith("_m")} |
                    {b for (a, b) in dtw_data.keys() if b.endswith("_m")})

    print("Unique Qdisc labels:", q_labels)
    print("Unique Mahi labels:", m_labels)
    
    print(f"Found {len(q_labels)} Qdisc traces and {len(m_labels)} Mahi traces.")
    
    group_a = q_labels  # Qdisc
    group_b = m_labels  # Mahi

    # Find all pairwise comparisons
    comparisons = len(group_a) * len(group_b)
    distances = np.array([])  # start as numpy array

    print(f"Performing {comparisons} pairwise comparisons (Qdisc × Mahi)...")

    for qa in group_a:
        for mb in group_b:
            # Get the DTW distance (either direction)
            distance = dtw_data.get((qa, mb)) or dtw_data.get((mb, qa))
            if distance is not None:
                distances = np.append(distances, distance)

    print(f"Collected {len(distances)} valid DTW distances across groups.")

    plt.figure(figsize=(8, 6))
    plt.hist(distances, bins=30, edgecolor='black', alpha=0.7)
    plt.title("Cross-System DTW Distance Distribution (Qdisc × Mahi)")
    plt.xlabel("Normalized DTW Distance")
    plt.ylabel("Frequency")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.show()
    
    # ---------- Permutation Testing ----------
    permutations = 20
    
    all_labels = np.array(group_a + group_b)
    group_size = len(all_labels) // 2  # keep groups equal size

    print(f"\nRunning {permutations} random permutations...")

    for p in range(permutations):
        shuffled = np.random.permutation(all_labels)
        new_group_a = shuffled[:group_size]
        new_group_b = shuffled[group_size:]
        perm_dists = np.array([])

        for qa in new_group_a:
            for mb in new_group_b:
                distance = dtw_data.get((qa, mb)) or dtw_data.get((mb, qa))
                if distance is not None:
                    perm_dists = np.append(perm_dists, distance)

        print(f"Permutation {p + 1}: {len(perm_dists)} valid distances")

        # Plot for this permutation
        plt.figure(figsize=(8, 6))
        plt.hist(perm_dists, bins=30, edgecolor='black', alpha=0.7)
        plt.title(f"Permutation {p + 1} — Randomized DTW Distribution")
        plt.xlabel("Normalized DTW Distance")
        plt.ylabel("Frequency")
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.show()
