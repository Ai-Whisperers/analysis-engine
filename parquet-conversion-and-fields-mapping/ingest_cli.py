#!/usr/bin/env python3
"""CLI Interface for Spark Ingestion Pipeline."""
import argparse
import sys
import os
import json

# Add pipeline to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pipeline'))

from profile_input import profile_file
from ingest_pipeline import run_pipeline


def cmd_profile(args):
    """Run Phase 0 profiling."""
    try:
        result = profile_file(
            args.path,
            expect_header=args.expect_header,
            min_rows=args.min_rows
        )
        print(json.dumps(result, indent=2))

        if not result['validation']['passed']:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_run(args):
    """Run full ingestion pipeline."""
    try:
        results = run_pipeline(
            source_path=args.path,
            fmt=args.fmt,
            output_path=args.output,
            use_delta=args.delta
        )

        if args.json:
            print(json.dumps(results, indent=2, default=str))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Spark Ingestion Pipeline - Production-ready data ingestion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Profile a CSV file
  ingest profile --path data/input.csv --expect-header true --min-rows 1

  # Run full pipeline on CSV
  ingest run --path data/input.csv --fmt csv

  # Run with Delta Lake output
  ingest run --path data/input.json --fmt json --delta

  # Custom output path
  ingest run --path data/input.csv --output output/my_data
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Profile command
    profile_parser = subparsers.add_parser('profile', help='Profile input file')
    profile_parser.add_argument('--path', required=True, help='Path to input file')
    profile_parser.add_argument('--expect-header', type=bool, default=True,
                               help='Expect header row (default: True)')
    profile_parser.add_argument('--min-rows', type=int, default=1,
                               help='Minimum number of rows (default: 1)')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run full ingestion pipeline')
    run_parser.add_argument('--path', required=True, help='Path to input file')
    run_parser.add_argument('--fmt', default='csv',
                           help='File format: csv, json, etc. (default: csv)')
    run_parser.add_argument('--output', default='output/cleaned_data',
                           help='Output path (default: output/cleaned_data)')
    run_parser.add_argument('--delta', action='store_true',
                           help='Use Delta Lake format instead of Parquet')
    run_parser.add_argument('--json', action='store_true',
                           help='Output results as JSON')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate command
    if args.command == 'profile':
        cmd_profile(args)
    elif args.command == 'run':
        cmd_run(args)


if __name__ == "__main__":
    main()
