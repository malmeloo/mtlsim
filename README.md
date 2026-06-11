# MTLsim

```
python3 start.py simulate --zone-input inputs/zone_updates.jsonl --query-input inputs/queries.jsonl --strategy single_inf --output hey
```

SIDN diff data:
- start: `2026-03-11T14:00:00`
- end: `2026-04-07T19:00:00`

## Zone diffs
`mtlsim ingest-zone-diffs input_files/combined_diffs.parquet --out-file inputs/nl/zone.jsonl`

## Zone files
`mtlsim ingest-zone input_files/root.zone --origin . --out-file inputs/root/zone.jsonl --cycles 10`

## Query data
`mtlsim generate-queries --start 2026-03-11T14:00:00 --end 2026-04-07T19:00:00 --exp-rate 10 --query-type DS --out-file inputs/nl/resolver_10_dsonly.jsonl`
For rates:
  - 0.01
  - 1
  - 5
  - 10


## Simulation

`./result/bin/mtlsim simulate --zone-input inputs/nl/zone.jsonl --query-input inputs/nl/resolver_1.jsonl --strategy single_inf --tag nl-singleinf-1`

