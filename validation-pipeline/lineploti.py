import matplotlib.pyplot as plt
from pathlib import Path

# === Base directory for outputs ===
BASE_DIR = Path(__file__).resolve().parent / "outputs"

def read_queue_data(filename):
    x, y, ms = [], [], 0
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

# === File to plot ===
file_path = BASE_DIR / "output_84.txt"

if not file_path.exists():
    raise FileNotFoundError(f"{file_path} not found.")

x, y = read_queue_data(file_path)

# === Plot ===
plt.figure()
plt.plot(x, y, marker="o", linestyle="-", markersize=3, color="blue", label=file_path.name)
plt.xlabel("Time (ms) | 16 ms per point")
plt.ylabel("Queue Size (bytes)")
plt.title(f"Queue Size Over Time: {file_path.name}")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()
