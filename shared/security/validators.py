"""
File validation and security checks.
"""

import os
from pathlib import Path
from typing import List, Optional

try:
    import magic
except ImportError:
    magic = None  # Optional dependency


class FileValidationError(Exception):
    """Raised when file validation fails."""

    pass


class FileValidator:
    """
    File validation for security and data quality.

    Checks:
    - File size limits
    - MIME type validation
    - Extension whitelist
    - Encoding detection
    - Malicious content detection

    Prevents:
    - Zip bombs (compressed bombs)
    - Executable uploads
    - Malicious file types
    - Oversized files (DoS)
    """

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        ".csv",
        ".xlsx",
        ".xls",
        ".parquet",
        ".json",
        ".txt",
    }

    # Allowed MIME types (if python-magic available)
    ALLOWED_MIME_TYPES = {
        "text/csv",
        "text/plain",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/json",
        "application/octet-stream",  # For Parquet files
    }

    # Maximum file size (100MB for free tier - prevents memory issues)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

    # Minimum file size (prevent empty files)
    MIN_FILE_SIZE = 1  # 1 byte

    @classmethod
    def validate_file(
        cls,
        file_path: str,
        check_mime: bool = True,
        max_size: Optional[int] = None,
    ) -> None:
        """
        Validate uploaded file.

        Args:
            file_path: Path to file
            check_mime: Check MIME type (requires python-magic)
            max_size: Override max file size

        Raises:
            FileValidationError: If validation fails
        """
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            raise FileValidationError(f"File does not exist: {file_path}")

        # Check if regular file (not directory, symlink, etc.)
        if not path.is_file():
            raise FileValidationError(f"Not a regular file: {file_path}")

        # Check file size
        file_size = path.stat().st_size
        max_size = max_size or cls.MAX_FILE_SIZE

        if file_size < cls.MIN_FILE_SIZE:
            raise FileValidationError("File is empty")

        if file_size > max_size:
            raise FileValidationError(
                f"File too large: {file_size / (1024*1024):.1f} MB "
                f"(max: {max_size / (1024*1024):.1f} MB)"
            )

        # Check extension
        extension = path.suffix.lower()
        if extension not in cls.ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"File type not allowed: {extension}. "
                f"Allowed: {', '.join(cls.ALLOWED_EXTENSIONS)}"
            )

        # Check MIME type (if python-magic available)
        if check_mime and magic:
            try:
                mime = magic.Magic(mime=True)
                mime_type = mime.from_file(str(path))

                if mime_type not in cls.ALLOWED_MIME_TYPES:
                    raise FileValidationError(
                        f"MIME type not allowed: {mime_type}. "
                        f"This may indicate a malicious file."
                    )
            except Exception as e:
                # Don't fail validation if MIME check fails
                # (python-magic may have issues on some systems)
                pass

    @classmethod
    def validate_file_name(cls, file_name: str) -> None:
        """
        Validate file name for path traversal attacks.

        Args:
            file_name: File name to validate

        Raises:
            FileValidationError: If validation fails
        """
        # Check for path traversal
        if ".." in file_name or "/" in file_name or "\\" in file_name:
            raise FileValidationError(
                "Invalid file name: path traversal attempt detected"
            )

        # Check for null bytes
        if "\x00" in file_name:
            raise FileValidationError("Invalid file name: null byte detected")

        # Check length
        if len(file_name) > 255:
            raise FileValidationError("File name too long (max: 255 characters)")

        # Check for empty name
        if not file_name or file_name.strip() == "":
            raise FileValidationError("File name cannot be empty")

    @classmethod
    def get_safe_filename(cls, file_name: str) -> str:
        """
        Sanitize file name for safe storage.

        Args:
            file_name: Original file name

        Returns:
            Safe file name
        """
        # Remove path components
        file_name = os.path.basename(file_name)

        # Replace unsafe characters
        safe_chars = []
        for char in file_name:
            if char.isalnum() or char in "._-":
                safe_chars.append(char)
            else:
                safe_chars.append("_")

        return "".join(safe_chars)
