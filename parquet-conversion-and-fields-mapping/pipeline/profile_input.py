"""Phase 0: Input Profiling - Detect format, encoding, and validate integrity."""
import os
import csv
import chardet
import json
from typing import Dict, Any


def detect_encoding(file_path: str, sample_size: int = 10000) -> str:
    """Detect file encoding."""
    with open(file_path, 'rb') as f:
        raw = f.read(sample_size)
        result = chardet.detect(raw)
        return result['encoding']


def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get basic file information."""
    stat = os.stat(file_path)
    return {
        'size_bytes': stat.st_size,
        'size_mb': round(stat.st_size / (1024 * 1024), 2),
    }


def sample_csv_rows(file_path: str, encoding: str, max_rows: int = 100) -> tuple:
    """Sample CSV rows and detect delimiter."""
    with open(file_path, 'r', encoding=encoding, errors='replace') as f:
        # Detect delimiter
        sample = f.read(8192)
        f.seek(0)
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(sample)
            delimiter = dialect.delimiter
        except:
            delimiter = ','

        # Count rows and detect header
        reader = csv.reader(f, delimiter=delimiter)
        rows = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)

        return delimiter, rows


def profile_file(file_path: str, expect_header: bool = True, min_rows: int = 1) -> Dict[str, Any]:
    """Profile input file before Spark processing."""

    # Check file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_info = get_file_info(file_path)

    # Fail fast on empty files
    if file_info['size_bytes'] == 0:
        raise ValueError("Empty file detected")

    # Detect encoding
    encoding = detect_encoding(file_path)

    # Determine file type and profile
    ext = os.path.splitext(file_path)[1].lower()

    profile = {
        'file_path': file_path,
        'encoding': encoding,
        'file_info': file_info,
        'format': None,
        'delimiter': None,
        'header': None,
        'sample_row_count': 0,
        'validation': {'passed': True, 'errors': []}
    }

    if ext in ['.csv', '.txt']:
        delimiter, rows = sample_csv_rows(file_path, encoding)
        profile['format'] = 'csv'
        profile['delimiter'] = delimiter
        profile['sample_row_count'] = len(rows)

        if len(rows) > 0:
            profile['header'] = rows[0]

            # Validate row length consistency
            if len(rows) > 1:
                header_len = len(rows[0])
                for i, row in enumerate(rows[1:10], 1):  # Check first 10 rows
                    if len(row) != header_len:
                        profile['validation']['errors'].append(
                            f"Row {i} length mismatch: expected {header_len}, got {len(row)}"
                        )

        # Validate minimum rows
        if profile['sample_row_count'] < min_rows:
            profile['validation']['errors'].append(
                f"Insufficient rows: {profile['sample_row_count']} < {min_rows}"
            )

        # Validate header presence
        if expect_header and not profile['header']:
            profile['validation']['errors'].append("Header expected but not found")

    elif ext == '.json':
        profile['format'] = 'json'
        # Basic JSON validation
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                data = json.load(f)
                if isinstance(data, list):
                    profile['sample_row_count'] = len(data)
        except json.JSONDecodeError as e:
            profile['validation']['errors'].append(f"Invalid JSON: {str(e)}")

    else:
        profile['format'] = 'unknown'
        profile['validation']['errors'].append(f"Unsupported file format: {ext}")

    # Set validation status
    profile['validation']['passed'] = len(profile['validation']['errors']) == 0

    return profile


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python profile_input.py <file_path>")
        sys.exit(1)

    result = profile_file(sys.argv[1])
    print(json.dumps(result, indent=2))
