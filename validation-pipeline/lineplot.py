import matplotlib.pyplot as plt
from pathlib import Path

# === Base directory for outputs ===
BASE_DIR = Path(__file__).resolve().parent / "outputs"

def read_queue_data(filename):
    x = []
    y = []
    ms = 0
    with open(filename, "r") as f:
        for line in f:
            if "queue size in bytes:" in line:
                parts = line.strip().split(":")
                if len(parts) == 2:
                    try:
                        value = int(parts[1].strip())
                        x.append(ms)
                        y.append(value)
                        ms += 16
                    except ValueError:
                        pass
    return x, y

# === Read both files ===
i = 1
while True:
    file1 = BASE_DIR / f"output_{i}.txt"
    file2 = BASE_DIR / f"output_{i+1}.txt"

    # stop if we don’t have both files
    if not file1.exists() or not file2.exists():
        print(f"Stopping: missing {file1.name if not file1.exists() else file2.name}")
        break

    x1, y1 = read_queue_data(file1)
    x2, y2 = read_queue_data(file2)

    plt.figure()
    plt.plot(x1, y1, marker="o", linestyle="-", markersize=3, color="blue", label=file1.name)
    plt.plot(x2, y2, marker="s", linestyle="-", markersize=3, color="orange", label=file2.name)

    plt.xlabel("Time (ms) | 16 ms per point")
    plt.ylabel("Queue Size (bytes)")
    plt.title(f"Queue Size Comparison: {file1.name} vs {file2.name}")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    i += 1
