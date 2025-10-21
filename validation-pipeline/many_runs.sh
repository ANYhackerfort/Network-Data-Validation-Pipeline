#!/bin/bash
# Usage: ./run_many_combined.bash [num_runs] [seconds_per_run]
# Example: ./run_many_combined.bash 3 20

# ========== User Arguments ==========
NUM_RUNS=${1:-1}
SECS=${2:-20}
OUT_DIR="./outputs"
mkdir -p "$OUT_DIR"

# ========== Constants ==========
TRACE_UP="../../traces/Constant.up"
TRACE_DOWN="../../traces/Constant.down"
L4S_TOS=1
CLASSIC_TOS=0
DELAY=0
PKTS=200

# ========== Helper: Clean Up Mahimahi Environment ==========
cleanup_network() {
  echo "[*] Cleaning up any leftover Mahimahi namespaces, qdiscs, and veth links..."

  # Kill any mahimahi or iperf processes
  sudo pkill -9 mahimahi 2>/dev/null || true
  sudo pkill -9 mm-link 2>/dev/null || true
  sudo pkill -9 mm-delay 2>/dev/null || true
  sudo pkill -9 mm-meter 2>/dev/null || true
  sudo pkill -9 iperf3 2>/dev/null || true

  # Remove stale network namespaces
  for ns in $(sudo ip netns list | awk '{print $1}'); do
    echo "    [-] Deleting namespace: $ns"
    sudo ip netns delete "$ns" 2>/dev/null || true
  done

  # Delete any veth pairs left behind by Mahimahi
  for v in $(ip link show | grep -oE 'veth[^:@ ]+'); do
    echo "    [-] Deleting leftover veth: $v"
    sudo ip link delete "$v" 2>/dev/null || true
  done

  # Flush qdiscs on common interfaces (eth0, lo, etc.)
  for dev in $(ip -o link show | awk -F': ' '{print $2}'); do
    sudo tc qdisc del dev "$dev" root 2>/dev/null || true
  done
}

# ========== Run Loop ==========
RUNS_LEFT=$NUM_RUNS
NEXT_IDX=0

while [[ $RUNS_LEFT -gt 0 ]]; do
  OUT_FILE="$OUT_DIR/output_${NEXT_IDX}.txt"
  FLOW_FILE="/tmp/iperf_flow_${NEXT_IDX}.txt"

  if [[ -e "$OUT_FILE" ]]; then
    ((NEXT_IDX++))
    continue
  fi

  echo ""
  echo "[*] === RUN $((NUM_RUNS - RUNS_LEFT + 1))/$NUM_RUNS ==="

  cleanup_network

  echo "[*] Output log: $OUT_FILE"
  echo "[*] Flow log  : $FLOW_FILE"

  echo "[*] Stopping any existing iperf3 servers..."
  sudo pkill -9 iperf3 2>/dev/null || true
  sleep 2

  echo "[*] Starting iperf3 server on port 5300..."
  iperf3 -s -p 5300 > /dev/null 2>&1 &
  IPERF_SERVER_PID=$!

  echo "[*] Starting DualPI2 L4S test in 1 second..."
  sleep 1

  mm-delay $DELAY mm-link --meter-all \
    --uplink-queue=dualPI2 \
    --uplink-queue-args="\
      packets=${PKTS},\
      target=1,\
      tupdate=16,\
      alpha=0.15625,\
      beta=3.195312" \
    "$TRACE_UP" "$TRACE_DOWN" -- bash -c "
      echo '[+] Starting constant UDP iperf3 flow (port 5300)...'
      iperf3 -c 10.0.0.1 -p 5300 -u -b 12M -l 1200 -t $SECS --tos $CLASSIC_TOS --interval 1 \
        2>&1 | tee \"$FLOW_FILE\"
    " >> "$OUT_FILE" 2>&1

  echo "[*] FINISHED DualPI2 test. Cleaning up iperf3 server..."
  kill $IPERF_SERVER_PID 2>/dev/null || true

  echo "[*] Completed run $((NUM_RUNS - RUNS_LEFT + 1))/$NUM_RUNS"
  echo "[*] Cooling down 5s before next run..."
  sleep 5

  ((RUNS_LEFT--))
  ((NEXT_IDX++))
done

cleanup_network

echo ""
echo "[*] All $NUM_RUNS run(s) complete. Logs saved in: $OUT_DIR/"
