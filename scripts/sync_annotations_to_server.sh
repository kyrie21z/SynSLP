#!/usr/bin/env bash
# SynSLP Explicit Annotation Synchronization Utility
# Syncs local character annotations to server-zyx:/mnt/data/zyx/SynSLP/annotations/

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_ANNOTATIONS_DIR="$ROOT_DIR/annotations"
SERVER_HOST="server-zyx"
SERVER_DIR="/mnt/data/zyx/SynSLP/annotations"
DRY_RUN=0

for arg in "$@"; do
  if [[ "$arg" == "--dry-run" || "$arg" == "-n" ]]; then
    DRY_RUN=1
  fi
done

echo "============================================================"
echo "SynSLP Local -> Server Annotation Sync"
echo "============================================================"
echo "Local Source:     $LOCAL_ANNOTATIONS_DIR"
echo "Server Target:    $SERVER_HOST:$SERVER_DIR"

if [[ ! -d "$LOCAL_ANNOTATIONS_DIR" ]]; then
  echo "ERROR: Local annotations directory does not exist: $LOCAL_ANNOTATIONS_DIR"
  exit 1
fi

FILES_TO_SYNC=$(find "$LOCAL_ANNOTATIONS_DIR" -maxdepth 2 -type f -name "*.jsonl")
if [[ -z "$FILES_TO_SYNC" ]]; then
  echo "WARNING: No .jsonl annotation files found in $LOCAL_ANNOTATIONS_DIR."
  exit 0
fi

echo "Files to synchronize:"
echo "$FILES_TO_SYNC" | sed 's/^/  - /'
echo

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[DRY RUN] Would execute:"
  echo "  ssh -o ClearAllForwardings=yes $SERVER_HOST \"mkdir -p $SERVER_DIR\""
  echo "  scp -o ClearAllForwardings=yes $LOCAL_ANNOTATIONS_DIR/*.jsonl $SERVER_HOST:$SERVER_DIR/"
  echo "[DRY RUN] No files transferred."
  exit 0
fi

echo "Creating destination directory on $SERVER_HOST..."
ssh -o ClearAllForwardings=yes "$SERVER_HOST" "mkdir -p $SERVER_DIR"

echo "Transferring annotation artifacts..."
scp -o ClearAllForwardings=yes "$LOCAL_ANNOTATIONS_DIR"/*.jsonl "$SERVER_HOST:$SERVER_DIR/"

echo
echo "Verifying transferred files on $SERVER_HOST:"
ssh -o ClearAllForwardings=yes "$SERVER_HOST" "ls -la $SERVER_DIR/*.jsonl"

echo "============================================================"
echo "SUCCESS: Annotation synchronization completed."
echo "============================================================"
