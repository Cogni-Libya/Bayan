#!/usr/bin/env bash
# On-box deadline guard for a vast.ai instance: after N minutes, stop the pipeline and the model servers,
# flush to disk, and put THIS instance into the "stopped" state, using the scoped key vast.ai injects into
# every container (CONTAINER_API_KEY / CONTAINER_ID in PID 1's environment). It runs on the box itself, so
# it holds even if the machine that rented it loses power or network.
# Stopped, not destroyed: GPU billing ends but the disk (and the checkpoint on it) is kept -- start the
# instance again to pull results, then destroy it.
#   nohup bash scripts/remote/self_stop.sh 120 > self_stop.log 2>&1 &
set -u
MINUTES=${1:?minutes until stop}
eval "$(tr '\0' '\n' < /proc/1/environ | grep -E '^(CONTAINER_ID|CONTAINER_API_KEY)=' | sed 's/^/export /')"
echo "$(date -u +%FT%TZ) armed: instance $CONTAINER_ID stops in $MINUTES min"
sleep $((MINUTES * 60))
echo "$(date -u +%FT%TZ) deadline reached: stopping jobs"
pkill -f '[b]arec_simplification_pipeline'
pkill -f '[v]llm serve'
sleep 10
sync
curl -s -m 60 -X PUT "https://console.vast.ai/api/v0/instances/$CONTAINER_ID/" \
  -H "Authorization: Bearer $CONTAINER_API_KEY" -H "Content-Type: application/json" -d '{"state": "stopped"}'
echo
echo "$(date -u +%FT%TZ) stop requested"
