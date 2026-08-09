#!/usr/bin/env bash
# Resume only the arms that are not already running. Safe to run repeatedly.
set -u
cd "$(dirname "$0")"
source /dev/stdin <<< "$(sed -n '/^run_tier ()/,/^}/p' run_main.sh)"
DB=data/main.sqlite
mkdir -p logs
for spec in "local all 3" "hosted all 3" "paid all 3" "free dev 1"; do
    set -- $spec
    if pgrep -f "runner.py --tier $1 " >/dev/null; then
        echo "tier=$1 already running, left alone"
    else
        echo "tier=$1 starting"
        run_tier "$1" "$2" "$3" &
    fi
done
wait
