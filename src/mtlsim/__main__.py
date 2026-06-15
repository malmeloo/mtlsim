import logging
from datetime import datetime
from pathlib import Path

import click

from mtlsim import (
    DNSQueryEvent,
    DNSQueryIngester,
    DNSResolver,
    DNSZone,
    DNSZoneUpdateEvent,
    DNSZoneUpdateIngester,
    EventLogger,
    analyze_log,
    get_strategies,
    get_strategy_by_id,
    ingest_multiple,
)

logging.basicConfig(level=logging.WARN)


@click.group()
def cli():
    pass


@cli.command()
def strategies():
    """
    List available ladder strategies.
    """

    print("Available ladder strategies:")
    for strat_id, strat_cls in get_strategies().items():
        strat_str = f"- {strat_id}"
        for strat_param, param_type in strat_cls.STRATEGY_PARAMS.items():
            strat_str += f"\n    - {strat_param}: {param_type.__name__}"
        print(strat_str)


@cli.command()
@click.option(
    "--query-input",
    type=Path,
    required=True,
    help="Path to the DNS query events file.",
)
@click.option(
    "--zone-input",
    type=Path,
    required=True,
    help="Path to the DNS zone update events file.",
)
@click.option("--strategy", type=str, required=True, help="Ladder strategy to use.")
@click.option(
    "-p", "--strategy-param", multiple=True, help="Parameters for the ladder strategy."
)
@click.option(
    "--live",
    is_flag=True,
    help="Whether to run the simulator in live mode, where it will wait for new events to be added to the input files and process them in real-time.",
)
@click.option(
    "--out-dir",
    type=Path,
    default=Path("logs"),
    help="Directory where the simulation results will be saved.",
)
@click.option(
    "--tag",
    type=str,
    required=False,
    help="Tag to identify the simulation run.",
)
def simulate(
    query_input: Path,
    zone_input: Path,
    live: bool,
    strategy: str,
    strategy_param: list[str],
    out_dir: Path,
    tag: str | None = None,
):
    """
    Run the simulator.
    """
    query_ingester = DNSQueryIngester(query_input)
    zone_ingester = DNSZoneUpdateIngester(zone_input)

    params = dict(param.split("=", 1) for param in strategy_param)
    strat = get_strategy_by_id(strategy, params)
    if not strat:
        print(f"Error: Strategy '{strategy}' not found.")
        return

    if tag is None:
        tag = strategy

    logger = EventLogger.new(out_dir, tag)

    zone = DNSZone(strat, logger)
    resolver = DNSResolver(zone, logger)
    i = 0

    print("Simulator is running!")
    for i, event in enumerate(
        ingest_multiple(
            query_ingester,
            zone_ingester,
            allow_missing_timestamps=live,
        )
    ):
        if i > 0 and i % 100 == 0:
            print(f"Processed {i} events (current timestamp: {event.timestamp})...")

        if isinstance(event, DNSZoneUpdateEvent):
            removed_rrsets = event.get_removed_rrsets()
            zone.delete_rrsets(list(removed_rrsets))

            added_rrsets = event.get_added_rrsets()
            zone.update_rrsets(list(added_rrsets), event.timestamp)
        elif isinstance(event, DNSQueryEvent):  # pyright: ignore[reportUnnecessaryIsInstance]
            if event.type == "given":
                assert event.query_name is not None and event.query_type is not None
                _resp = resolver.query(
                    event.query_type, event.query_name, event.timestamp
                )
            elif event.type == "random":
                _resp = resolver.query_random(
                    event.timestamp, query_type=event.query_type
                )
        else:
            print(f"Unknown event type: {type(event)}")
            continue

    print(f"Simulator done, processed {i} events.")
    print("Waiting for logger buffer to flush...")
    logger.wait()

    print("Done.")


@cli.command()
@click.argument(
    "zone-file",
    type=Path,
    required=True,
)
@click.option(
    "--origin",
    type=str,
    required=True,
    help="The origin to use when parsing the zone file. For example, use '.' for the root zone.",
)
@click.option(
    "--cycles",
    type=int,
    default=1,
    help="Number of times to cycle through the zone file. This can be used to simulate a longer time period by simulating RRSIG re-signing operations.",
)
@click.option(
    "--out-file",
    type=Path,
    required=True,
    help="Path to the output file where the extracted events will be saved.",
)
def ingest_zone(zone_file: Path, origin: str, cycles: int, out_file: Path):
    """
    Ingest a DNS zone file. Will generate a series of zone update events:
      - one event for the initial state of the zone
      - subsequent events for RRSIG expirations

    It is assumed that when an RRSIG expires, a new RRSIG is generated in the zone, replacing it.
    """
    from mtlsim.ingest import extract_rrsets_from_zone

    with out_file.open("w") as f:
        for event in extract_rrsets_from_zone(zone_file, origin, cycles):
            _ = f.write(event.model_dump_json() + "\n")


@cli.command()
@click.argument(
    "diff-file",
    type=Path,
    required=True,
)
@click.option(
    "--out-file",
    type=Path,
    required=True,
    help="Path to the output file where the extracted events will be saved.",
)
def ingest_zone_diffs(diff_file: Path, out_file: Path) -> None:
    """
    Ingest DNS zone diffs in custom parquet format and generate zone update events.
    """
    from mtlsim.ingest import extract_rrsets_from_zone_diffs

    i = 0
    with out_file.open("w") as f:
        for event in extract_rrsets_from_zone_diffs(diff_file):
            _ = f.write(event.model_dump_json() + "\n")

            if i > 0 and i % 100 == 0:
                print(f"Processed {i} events...")
            i += 1

    print(f"Done, ingested {i} events.")


@cli.command()
@click.option(
    "--start",
    type=click.DateTime(),
    required=True,
)
@click.option(
    "--end",
    type=click.DateTime(),
    required=True,
)
@click.option(
    "--exp-rate",
    type=float,
    required=True,
    help="Average number of queries per second to generate (exponentially distributed).",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    required=False,
    help="Random seed for query generation. Default is 42.",
)
@click.option(
    "--query-type",
    type=str,
    default=None,
    required=False,
    help="If specified, all generated queries will be of this type. If not specified, query types will be randomly generated based on the active rrsets in the zone.",
)
@click.option(
    "--out-file",
    type=Path,
    required=True,
    help="Path to the output file where the generated queries will be saved.",
)
def generate_queries(
    start: datetime,
    end: datetime,
    exp_rate: float,
    seed: int,
    query_type: str | None,
    out_file: Path,
):
    """
    Generate synthetic DNS query events based on zone update events. This can be used to create input data for the simulator.
    """
    from mtlsim.ingest import generate_resolver_queries

    i = 0
    with out_file.open("w") as f:
        for event in generate_resolver_queries(start, end, exp_rate, seed, query_type):
            _ = f.write(event.model_dump_json() + "\n")

            if i > 0 and i % 10000 == 0:
                print(f"Generated {i} queries (current time: {event.timestamp})...")
            i += 1

    print(f"Done, generated {i} queries.")


@cli.command()
@click.argument(
    "log-files",
    nargs=-1,
    type=Path,
)
@click.option(
    "--out-dir",
    type=Path,
    default=Path("output"),
    help="Directory where the analysis results will be saved. Existing files with the same name will be overwritten.",
)
def analyze(log_files: list[Path], out_dir: Path):
    """
    Analyze the raw logs generated by the simulator and compute statistics about the run(s), such as time between full signature fetches, etc.

    File names are expected to be in the format: name[_timestamp].<ext>, where timestamp is optional and in the format YYYYMMDD-HHMMSS.
    Timestamps are used to disambiguate different runs with the same name. Only the latest run for each name will be processed.
    """
    if not log_files:
        raise click.UsageError("At least one log file must be provided.")

    process_files: dict[str, tuple[Path, datetime | None]] = {}
    for file in log_files:
        if not file.exists():
            print(f"Warning: File does not exist, skipping: {file}")
            continue

        if file.is_dir():
            print(f"Warning: Expected a file but got a directory, skipping: {file}")
            continue

        fname_parts = file.stem.split("_")
        timestamp_str = fname_parts[-1] if len(fname_parts) > 1 else ""
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")
        except ValueError:
            timestamp = None
        run_name = "_".join(fname_parts[:-1] if timestamp is not None else fname_parts)

        if run_name in process_files and timestamp is None:
            print(
                f"Warning: Multiple files with same run name '{run_name}' and no timestamps, skipping file: {file}"
            )
            continue

        process_files[run_name] = (file, timestamp)

    for run_name, (file, timestamp) in sorted(process_files.items()):
        print(f"Analyzing run '{run_name}' (timestamp: {timestamp})...")

        analysis = analyze_log(file, run_name, timestamp)
        output = out_dir / f"{run_name}.json"

        print(f"  - Analysis complete, saving results to {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        _ = output.write_text(analysis.model_dump_json(indent=2))

        fullsig_time_avg = (
            sum(analysis.time_between_fullsig) / len(analysis.time_between_fullsig)
            if analysis.time_between_fullsig
            else 0
        )
        fullsig_query_avg = (
            sum(analysis.queries_between_fullsig)
            / len(analysis.queries_between_fullsig)
            if analysis.queries_between_fullsig
            else 0
        )
        print(
            f"  - Average time between full signature fetches: {fullsig_time_avg:.2f} seconds"
        )
        print(
            f"  - Average queries between full signature fetches: {fullsig_query_avg:.2f} queries"
        )


if __name__ == "__main__":
    cli()
