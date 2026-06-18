#!/usr/bin/env bash

set -euo pipefail

# This script runs the max-endurance simulation with different endurance_seconds values.

declare -a MAX_STALE_COUNTS_MIL=(2 3 5 10 15 20)
declare -a ZONE_INPUT=("inputs/nl/zone.jsonl")
declare -a QUERY_INPUT=("inputs/nl/resolver_5.jsonl")

for max_size in "${MAX_STALE_COUNTS_MIL[@]}"; do
    max_size=$(( max_size * 1000000 ))

    echo "Running simulation for ${QUERY_INPUT[0]} with max_size=$max_size"

    mtlsim simulate \
        --zone-input "${ZONE_INPUT[0]}" \
        --query-input "${QUERY_INPUT[0]}" \
        --strategy single_maxstale \
        --strategy-param "max_stale_count=$max_size" \
        --tag "singlemaxstale_5_${max_size}"
done
