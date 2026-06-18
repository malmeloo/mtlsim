#!/usr/bin/env bash

set -euo pipefail

# This script runs the max-endurance simulation with different endurance_seconds values.

declare -a DAYS=(1 2 4 7 14 21 28)
declare -a ZONE_INPUT=("inputs/nl/zone.jsonl")
declare -a QUERY_INPUT=("inputs/nl/resolver_5.jsonl")

for days in "${DAYS[@]}"; do
    seconds=$(( days * 24 * 60 * 60 ))

    echo "Running simulation for ${QUERY_INPUT[0]} with endurance_seconds=$seconds (days=$days)"

    mtlsim simulate \
        --zone-input "${ZONE_INPUT[0]}" \
        --query-input "${QUERY_INPUT[0]}" \
        --strategy single_maxtime \
        --strategy-param "endurance_seconds=$seconds" \
        --tag "singlemaxtime_5_${days}d"
done
