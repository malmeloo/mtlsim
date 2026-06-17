#!/bin/bash

# Bash script that runs the simulate command for all resolver_*.jsonl files in the inputs/nl directory, using the zone.jsonl file as input.
# You will probably want to adjust this script for your needs, but it should be a good starting point.

set -euo pipefail

for f in inputs/nl/resolver_*.jsonl; do
    # Extract the numeric suffix (e.g. "0.05" from "resolver_0.05.jsonl")
    num="${f##*/resolver_}"
    num="${num%.jsonl}"

    echo "Running simulation for $f with numeric suffix $num"

    mtlsim simulate \
        --zone-input inputs/nl/zone.jsonl \
        --query-input "$f" \
        --strategy single_inf \
        --tag "singleinf_${num}"
done
