#!/bin/bash

# Find the parent process that's spawning new Celery workers
echo "Finding parent processes that spawn Celery workers..."
PARENT_PIDS=$(pgrep -f "celery.*worker" | xargs -I{} ps -o ppid= -p {} | sort -u)

echo "Parent processes: $PARENT_PIDS"

# Kill the parent processes first to prevent respawning
if [ ! -z "$PARENT_PIDS" ]; then
  echo "Stopping parent processes..."
  for PID in $PARENT_PIDS; do
    echo "Stopping process $PID..."
    kill -15 $PID
    sleep 1
  done
fi

# Now kill any remaining Celery workers
echo "Stopping any remaining Celery workers..."
pkill -f "celery.*worker"

# Kill any Celery beat processes
echo "Stopping Celery beat processes..."
pkill -f "celery.*beat"

# Verify all processes are stopped
sleep 2
REMAINING=$(pgrep -f "celery")
if [ ! -z "$REMAINING" ]; then
  echo "Some Celery processes are still running. Using SIGKILL..."
  pkill -9 -f "celery"
fi

echo "Done. Checking for remaining Celery processes..."
pgrep -f "celery" || echo "All Celery processes stopped successfully."