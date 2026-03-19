"""CLI entry point for KNN regression tool."""

import argparse
import sys

from knn_cli.commands import add_csv, create, query_csv


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="knn",
        description="KNN Regression CLI - A tool for dataset-based numeric prediction",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new dataset with specified dimensionality",
    )
    create_parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the dataset to create",
    )
    create_parser.add_argument(
        "--dimension",
        type=int,
        required=True,
        help="Number of feature dimensions",
    )
    create_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing dataset if it exists",
    )

    # add-csv command
    add_parser = subparsers.add_parser(
        "add-csv",
        help="Add training observations from a CSV file",
    )
    add_parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the dataset to add data to",
    )
    add_parser.add_argument(
        "--file",
        required=True,
        help="Path to the training CSV file",
    )

    # query-csv command
    query_parser = subparsers.add_parser(
        "query-csv",
        help="Generate predictions for query observations",
    )
    query_parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the dataset to query",
    )
    query_parser.add_argument(
        "--file",
        required=True,
        help="Path to the query CSV file",
    )
    query_parser.add_argument(
        "--output",
        required=True,
        help="Path to write the predictions CSV",
    )

    return parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    try:
        if args.command == "create":
            create(args.dataset, args.dimension, overwrite=args.overwrite)
        elif args.command == "add-csv":
            add_csv(args.dataset, args.file)
        elif args.command == "query-csv":
            query_csv(args.dataset, args.file, args.output)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
