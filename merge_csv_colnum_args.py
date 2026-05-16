from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


# 1-based column ranges from the source CSV layouts.
COMMON_RANGE = (1, 3637)
MAIN_RANGES = {
    "A": (3638, 9971),
    "B": (3638, 7182),
    "C": (3638, 9168),
    "D": (3638, 7256),
}
V_RANGES = {
    "A": (9972, 10233),
    "B": (7183, 7444),
    "C": (9169, 9430),
    "D": (7257, 7518),
}
A_TAIL_RANGE = (10234, 10362)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge NHT2602 A/B/C/D CSV files by fixed column numbers."
    )
    parser.add_argument("--a", required=True, help="Path to category A CSV file.")
    parser.add_argument("--b", required=True, help="Path to category B CSV file.")
    parser.add_argument("--c", required=True, help="Path to category C CSV file.")
    parser.add_argument("--d", required=True, help="Path to category D CSV file.")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output CSV path. Default: csv_merge_MMDDHHMM.csv",
    )
    return parser.parse_args()


def read_header(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return next(csv.reader(f))


def one_based_range(start: int, end: int) -> range:
    if start > end:
        raise ValueError(f"Invalid range: {start} > {end}")
    return range(start - 1, end)


def pick(values: list[str], start: int, end: int) -> list[str]:
    return [values[i] for i in one_based_range(start, end)]


def validate_file(path: Path, category: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Category {category} file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Category {category} path is not a file: {path}")


def validate_columns(headers: dict[str, list[str]]) -> None:
    required_ranges = {
        "A": [COMMON_RANGE, MAIN_RANGES["A"], V_RANGES["A"], A_TAIL_RANGE],
        "B": [COMMON_RANGE, MAIN_RANGES["B"], V_RANGES["B"]],
        "C": [COMMON_RANGE, MAIN_RANGES["C"], V_RANGES["C"]],
        "D": [COMMON_RANGE, MAIN_RANGES["D"], V_RANGES["D"]],
    }

    for category, ranges in required_ranges.items():
        col_count = len(headers[category])
        required_count = max(end for _, end in ranges)
        if col_count < required_count:
            raise ValueError(
                f"Category {category} has {col_count} columns, "
                f"but column {required_count} is required."
            )


def build_header(headers: dict[str, list[str]]) -> list[str]:
    header = pick(headers["A"], *COMMON_RANGE)
    header[0] = "SAMPLENUMBER"

    for category in ("A", "B", "C", "D"):
        header.extend(pick(headers[category], *MAIN_RANGES[category]))

    header.extend(pick(headers["A"], *V_RANGES["A"]))
    header.extend(pick(headers["A"], *A_TAIL_RANGE))
    return header


def source_indexes(category: str) -> list[int]:
    indexes = list(one_based_range(*COMMON_RANGE))
    indexes.extend(one_based_range(*MAIN_RANGES[category]))
    indexes.extend(one_based_range(*V_RANGES[category]))

    if category == "A":
        indexes.extend(one_based_range(*A_TAIL_RANGE))

    return indexes


def destination_indexes(
    category: str,
    main_offsets: dict[str, int],
    v_offset: int,
    a_tail_offset: int,
) -> list[int]:
    indexes = list(range(COMMON_RANGE[1]))
    indexes.extend(
        range(
            main_offsets[category],
            main_offsets[category] + (MAIN_RANGES[category][1] - MAIN_RANGES[category][0] + 1),
        )
    )
    indexes.extend(range(v_offset, v_offset + (V_RANGES[category][1] - V_RANGES[category][0] + 1)))

    if category == "A":
        indexes.extend(range(a_tail_offset, a_tail_offset + (A_TAIL_RANGE[1] - A_TAIL_RANGE[0] + 1)))

    return indexes


def samplenumber_sort_key(row: list[str]) -> tuple[int, float | str]:
    value = row[0].strip()
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def has_single_digit_a_column(row: list[str]) -> bool:
    value = row[0].strip()
    return len(value) == 1 and value.isdigit()


def default_output_file() -> Path:
    return Path(f"csv_merge_{datetime.now():%m%d%H%M}.csv")


def avoid_overwrite(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def merge_csv(files: dict[str, Path], output_file: Path) -> None:
    for category, path in files.items():
        validate_file(path, category)

    headers = {category: read_header(path) for category, path in files.items()}
    validate_columns(headers)
    output_header = build_header(headers)

    main_offsets: dict[str, int] = {}
    cursor = COMMON_RANGE[1]
    for category in ("A", "B", "C", "D"):
        main_offsets[category] = cursor
        cursor += MAIN_RANGES[category][1] - MAIN_RANGES[category][0] + 1

    v_offset = cursor
    cursor += V_RANGES["A"][1] - V_RANGES["A"][0] + 1
    a_tail_offset = cursor
    output_rows: list[list[str]] = []

    for category in ("A", "B", "C", "D"):
        path = files[category]
        src_indexes = source_indexes(category)
        dst_indexes = destination_indexes(category, main_offsets, v_offset, a_tail_offset)

        with path.open("r", newline="", encoding="utf-8-sig") as in_f:
            reader = csv.reader(in_f)
            next(reader)

            for row_number, row in enumerate(reader, start=2):
                if len(row) < max(src_indexes) + 1:
                    raise ValueError(
                        f"Category {category} row {row_number} has {len(row)} columns, "
                        f"but column {max(src_indexes) + 1} is required."
                    )

                out_row = [""] * len(output_header)
                for src, dst in zip(src_indexes, dst_indexes):
                    out_row[dst] = row[src]
                output_rows.append(out_row)

    output_rows.sort(key=samplenumber_sort_key)
    output_rows = [row for row in output_rows if not has_single_digit_a_column(row)]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8-sig") as out_f:
        writer = csv.writer(out_f, lineterminator="\n")
        writer.writerow(output_header)
        writer.writerows(output_rows)


def main() -> None:
    args = parse_args()
    files = {
        "A": Path(args.a).expanduser().resolve(),
        "B": Path(args.b).expanduser().resolve(),
        "C": Path(args.c).expanduser().resolve(),
        "D": Path(args.d).expanduser().resolve(),
    }
    output_file = Path(args.output).expanduser().resolve() if args.output else default_output_file().resolve()
    output_file = avoid_overwrite(output_file)

    merge_csv(files, output_file)
    print(f"created: {output_file}")


if __name__ == "__main__":
    main()
