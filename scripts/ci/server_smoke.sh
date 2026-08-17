#!/usr/bin/env bash
set -euo pipefail

mkdir -p run
printf '%s\n' 'eula=true' > run/eula.txt

log_file="${RUNNER_TEMP:-/tmp}/immersive-technology-server.log"
setsid ./gradlew runServer --stacktrace >"$log_file" 2>&1 &
server_pid=$!

cleanup() {
  kill -- "-$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 180); do
  if grep -Fq 'Done (' "$log_file"; then
    echo "Dedicated server reached the ready state."
    exit 0
  fi

  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Dedicated server exited before reaching the ready state."
    tail -n 200 "$log_file"
    exit 1
  fi

  sleep 1
done

echo "Dedicated server did not reach the ready state within 180 seconds."
tail -n 200 "$log_file"
exit 1
