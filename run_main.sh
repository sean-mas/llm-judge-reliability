#!/usr/bin/env bash
# Main run launcher. Started 08.08.2026, immediately after the rubric freeze
# (v0.2 / 3b14635aa1c3eecd).
#
#   ./run_main.sh
#
# Safe to re-run at any time. The runner caches on (item, judge, model version,
# prompt hash), so a second invocation requests only what is missing. That is
# what makes a killed process, a closed lid or an exhausted quota cost nothing
# but time.
#
# The three arms run concurrently because they contend for nothing: tier 3 is the
# local GPU, tiers 1 and 2 are two unrelated network endpoints. Wall clock is
# therefore the slowest single arm (tier 3, roughly 9 hours) rather than the sum
# of all three (roughly 15).
#
# caffeinate holds off idle and system sleep for the duration. It does NOT
# override closing the lid: on a closed lid the machine still suspends and the
# local arm stops. It resumes on the next invocation.
set -u
cd "$(dirname "$0")"

DB=data/main.sqlite
mkdir -p logs

run_tier () {
    # Declared one per line on purpose: a single `local a=$1 b="$a"` cannot
    # expand `a` in the same statement, which under `set -u` aborts the whole
    # function silently in the background and leaves no log to explain it.
    local tier=$1
    local split=$2
    local repeats=$3
    local log="logs/${tier}.log"
    local rc=0
    local wait=0
    # Progressive backoff. The first launch used a flat 120s x 10, which covers
    # 20 minutes and was useless against the two failures that actually
    # happened: an Ollama Cloud *session* usage limit lasting roughly two hours,
    # and repeated read timeouts on tier 1. This schedule spans about nine
    # hours, so a quota wall is waited out rather than given up on.
    for attempt in $(seq 1 24); do
        echo "[$(date '+%F %T')] tier=$tier split=$split repeats=$repeats attempt=$attempt" >>"$log"
        caffeinate -is .venv/bin/python src/runner.py \
            --tier "$tier" --split "$split" --repeats "$repeats" --db "$DB" >>"$log" 2>&1
        rc=$?
        if [ $rc -eq 0 ]; then
            echo "[$(date '+%F %T')] tier=$tier COMPLETE after $attempt attempt(s)" >>"$log"
            return 0
        fi
        if   [ "$attempt" -le 4  ]; then wait=120
        elif [ "$attempt" -le 10 ]; then wait=600
        else                             wait=1800
        fi
        echo "[$(date '+%F %T')] tier=$tier exit=$rc, retry in ${wait}s" >>"$log"
        sleep "$wait"
    done
    echo "[$(date '+%F %T')] tier=$tier GAVE UP after 24 attempts" >>"$log"
    return 1
}

# Arms: the full corpus, three repeats each. 750 x 3 = 2250 judgments per arm.
run_tier local  all 3 &
run_tier hosted all 3 &
run_tier paid   all 3 &

# Auxiliary: dev split, single pass. Not an arm, never pooled with the three
# above. One repeat is enough for what it is asked to establish.
run_tier free dev 1 &

wait
echo "[$(date '+%F %T')] all jobs returned" >>logs/_launcher.log
