#!/usr/bin/env bash

set -euo pipefail

# This script runs the max-endurance simulation with different endurance_seconds values.

declare -a MINUTES=(720 480 240 120 60 30)
declare -a ZONE_INPUT=("inputs/nl/zone.jsonl")
declare -a QUERY_INPUT=("inputs/nl/resolver_5.jsonl")

for minutes in "${MINUTES[@]}"; do
    seconds=$(( minutes * 60 ))

    echo "Running simulation for ${QUERY_INPUT[0]} with endurance_seconds=$seconds (minutes=$minutes)"

    mtlsim simulate \
        --zone-input "${ZONE_INPUT[0]}" \
        --query-input "${QUERY_INPUT[0]}" \
        --strategy single_maxtime \
        --strategy-param "endurance_seconds=$seconds" \
        --tag "singlemaxtime_5_${minutes}m"
done
