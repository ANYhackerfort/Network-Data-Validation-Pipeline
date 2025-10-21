#!/bin/bash
# Usage: ./run_many_qdisc.bash <seconds_per_run> <num_runs>

set -euo pipefail

# ---- Args ----
SECS=${1:-20}
NUM_RUNS=${2:-1}

# ---- Config ----
IPROUTE2_PATH="../tc/tc"
NS_S="ns_s"
NS_R="ns_r"
VETH_DEV="veth-s"
DST_IP="172.20.1.2"
PORT=5202
RATE="12mbit"
BURST="10k"
LOG_DIR="./tmp"
SAMPLE_SEC="0.01"
TIMEOUT_EXTRA=12
LOG_TIME=$((SECS + TIMEOUT_EXTRA))

mkdir -p "$LOG_DIR"

next_free_idx() {
  local i=0
  while [[ -e "$LOG_DIR/qdisc_${i}.log" || -e "$LOG_DIR/ss_${i}.log" ]]; do
    ((i++))
  done
  echo "$i"
}

cleanup_run() {
  local pids=("$@")
  for pid in "${pids[@]}"; do
    [[ -n "${pid:-}" ]] && kill "$pid" 2>/dev/null || true
  done
  sudo ip netns exec "$NS_S" pkill -9 iperf3 2>/dev/null || true
  sudo ip netns exec "$NS_R" pkill -9 iperf3 2>/dev/null || true
}

run_once() {
  local IDX=$1
  local QDISC_LOG="$LOG_DIR/qdisc_${IDX}.log"
  local SS_LOG="$LOG_DIR/ss_${IDX}.log"

  echo
  echo "[*] === Run #$IDX for ${SECS}s ==="
  echo "[*] Logs: $QDISC_LOG  |  $SS_LOG"

  echo "🔁 Resetting qdisc on $VETH_DEV..."
  sudo ip netns exec "$NS_S" $IPROUTE2_PATH qdisc del dev "$VETH_DEV" root 2>/dev/null || true
  sudo ip netns exec "$NS_S" $IPROUTE2_PATH qdisc add dev "$VETH_DEV" root handle 1: htb default 10
  sudo ip netns exec "$NS_S" $IPROUTE2_PATH class add \
    dev "$VETH_DEV" parent 1: classid 1:10 htb \
    rate "$RATE" ceil "$RATE" burst "$BURST"

  sudo ip netns exec "$NS_S" $IPROUTE2_PATH qdisc add dev "$VETH_DEV" parent 1:10 handle 2: dualpi2 \
    target 1ms tupdate 16 limit 15040000 \
    alpha 0.15625 beta 3.195312

  echo "📡 Starting iperf3 server in $NS_R..."
  sudo ip netns exec "$NS_R" iperf3 -s -p "$PORT" >/dev/null 2>&1 &
  SERVER_PID=$!

  sleep 1

  echo "🚀 Starting iperf3 client in $NS_S (UDP) for ${SECS}s..."
  sudo ip netns exec "$NS_S" iperf3 -c "$DST_IP" -p "$PORT" -u -b 12M -l 1200 -t "$SECS" --tos 0 >/dev/null 2>&1 &
  CLIENT_PID=$!

  echo "📥 Logging TCP socket info to $SS_LOG ..."
  (
    timeout "${LOG_TIME}s" bash -c "
      while sleep $SAMPLE_SEC; do
        {
          echo \"------ \$(date) ------\"
          sudo ip netns exec $NS_S ss -tin dst $DST_IP
        } >> \"$SS_LOG\"
      done
    "
  ) & SS_PID=$!

  echo "📊 Logging qdisc stats to $QDISC_LOG ..."
  (
    timeout "${LOG_TIME}s" bash -c "
      while sleep $SAMPLE_SEC; do
        {
          echo \"------ \$(date) ------\"
          sudo ip netns exec $NS_S $IPROUTE2_PATH -s qdisc show dev $VETH_DEV
        } >> \"$QDISC_LOG\"
      done
    "
  ) & QDISC_PID=$!

  wait "$CLIENT_PID" 2>/dev/null || true
  sleep 2

  echo "🛑 Stopping loggers and iperf3..."
  cleanup_run "$SS_PID" "$QDISC_PID" "$SERVER_PID"
  echo "✅ Saved: $QDISC_LOG"
}

# --- Run Loop ---
for ((run=0; run<NUM_RUNS; run++)); do
  IDX=$(next_free_idx)
  sudo ip netns exec "$NS_S" pkill -9 iperf3 2>/dev/null || true
  sudo ip netns exec "$NS_R" pkill -9 iperf3 2>/dev/null || true
  sleep 1
  run_once "$IDX"
  echo "[*] Cooling down 3s..."
  sleep 3
done

echo "[*] All runs complete."
