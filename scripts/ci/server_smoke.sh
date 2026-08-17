#!/usr/bin/env bash
set -euo pipefail

mkdir -p run
printf '%s\n' 'eula=true' > run/eula.txt

log_file="${RUNNER_TEMP:-/tmp}/immersive-technology-server.log"
command_pipe="${RUNNER_TEMP:-/tmp}/immersive-technology-server-commands"
rm -f "$command_pipe"
mkfifo "$command_pipe"
exec 3<>"$command_pipe"

setsid ./gradlew runServer --stacktrace <"$command_pipe" >"$log_file" 2>&1 &
server_pid=$!

cleanup() {
    kill -- "-$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
    exec 3>&- || true
    rm -f "$command_pipe"
}
trap cleanup EXIT

ready=false
for _ in $(seq 1 180); do
  if grep -Fq 'Done (' "$log_file"; then
    ready=true
    break
  fi

  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Dedicated server exited before reaching the ready state."
    tail -n 200 "$log_file"
    exit 1
  fi

  sleep 1
done

if [[ "$ready" != true ]]; then
  echo "Dedicated server did not reach the ready state within 180 seconds."
  tail -n 200 "$log_file"
  exit 1
fi

echo "Dedicated server reached the ready state; beginning post-ready observation."
for _ in $(seq 1 10); do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Dedicated server crashed during the post-ready observation interval."
    tail -n 200 "$log_file"
    exit 1
  fi
  sleep 1
done

if grep -Eq 'FATAL|ModLoadingException|Crash report saved|Failed to start the minecraft server' "$log_file"; then
  echo "Dedicated server log contains a fatal startup marker."
  tail -n 200 "$log_file"
  exit 1
fi

printf 'stop\n' >&3
exec 3>&-
for _ in $(seq 1 60); do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  sleep 1
done

if kill -0 "$server_pid" 2>/dev/null; then
  echo "Dedicated server did not stop within 60 seconds."
  tail -n 200 "$log_file"
  exit 1
fi

set +e
wait "$server_pid"
server_exit=$?
set -e
trap - EXIT
rm -f "$command_pipe"

if [[ "$server_exit" -ne 0 ]]; then
  echo "Dedicated server returned exit code $server_exit after stop."
  tail -n 200 "$log_file"
  exit 1
fi

echo "Dedicated server completed ready-state observation and clean shutdown."
