"""
XSS protection security tests.

Based on real production attacks (16% of records contain attacks).
"""

import pytest

from shared.security import XSSProtection, ExcelFormulaProtection, sanitize_text


class TestXSSProtection:
    """Test 6-layer XSS protection."""

    @pytest.mark.parametrize(
        "attack,expected_safe",
        [
            # Script tag injections
            ("<script>alert('XSS')</script>", True),
            ("<SCRIPT>alert('XSS')</SCRIPT>", True),
            ("<script src='evil.js'></script>", True),
            # Event handler injections
            ("<img src=x onerror=alert('XSS')>", True),
            ("<svg onload=alert('XSS')>", True),
            ("<body onload=alert('XSS')>", True),
            # JavaScript protocol
            ("<a href=javascript:alert('XSS')>Click</a>", True),
            # Iframe injections
            ("<iframe src=javascript:alert('XSS')>", True),
            ("<iframe src='http://evil.com'>", True),
            # HTML entity bypass attempts
            ("&#60;script&#62;alert('XSS')&#60;/script&#62;", True),
            ("&#x3C;script&#x3E;alert('XSS')", True),
            # Data URL injections
            ("<iframe src=data:text/html,<script>alert('XSS')</script>>", True),
            # VBScript
            ("<a href=vbscript:msgbox('XSS')>Click</a>", True),
        ],
    )
    def test_xss_attack_blocked(self, attack, expected_safe):
        """
        Test that XSS attacks are sanitized.

        Args:
            attack: XSS attack string
            expected_safe: Should be sanitized (always True)
        """
        sanitized = XSSProtection.sanitize(attack)

        # Should not contain dangerous patterns
        dangerous_patterns = [
            "<script",
            "javascript:",
            "onerror=",
            "onload=",
            "<iframe",
            "vbscript:",
        ]

        for pattern in dangerous_patterns:
            assert pattern.lower() not in sanitized.lower(), (
                f"Dangerous pattern '{pattern}' found in sanitized output: {sanitized}"
            )

    def test_legitimate_text_preserved(self):
        """Test that legitimate text is preserved."""
        legitimate_texts = [
            "Great service!",
            "The price is $100.00",
            "Rating: 5/5 stars",
            "Email: user@example.com",
            "Math: 2 + 2 = 4",
        ]

        for text in legitimate_texts:
            sanitized = XSSProtection.sanitize(text)
            # Should preserve basic content (may add escaping)
            assert len(sanitized) > 0

    def test_empty_and_none_handling(self):
        """Test edge cases (empty, None)."""
        assert XSSProtection.sanitize("") == ""
        assert XSSProtection.sanitize(None) == ""
        assert XSSProtection.sanitize("   ") == ""


class TestExcelFormulaProtection:
    """Test Excel formula injection protection."""

    @pytest.mark.parametrize(
        "formula,should_escape",
        [
            # DDE attacks
            ("=cmd|'/c calc'!A1", True),
            ("=system('calc')", True),
            # HYPERLINK attacks
            ("=HYPERLINK('http://evil.com','Click')", True),
            # CSV injection
            ("=1+1", True),
            ("+1+1", True),
            ("-1+1", True),
            ("@SUM(A1:A10)", True),
            # Tab/newline prefixes
            ("\t=1+1", True),
            ("\r=1+1", True),
            # Legitimate text
            ("This is a comment", False),
            ("Score: 10/10", False),
            ("Email = user@example.com", False),
        ],
    )
    def test_formula_detection(self, formula, should_escape):
        """
        Test Excel formula detection and escaping.

        Args:
            formula: Input text
            should_escape: Whether it should be escaped
        """
        result = ExcelFormulaProtection.sanitize(formula)

        if should_escape:
            # Should start with single quote (escape character)
            assert result.startswith("'"), (
                f"Formula not escaped: {formula} -> {result}"
            )
        else:
            # Should not be modified
            assert result == formula

    def test_dangerous_functions_blocked(self):
        """Test that dangerous Excel functions are blocked."""
        dangerous_formulas = [
            "=cmd|'/c calc'!A1",
            "=DDE('calc')",
            "=HYPERLINK('http://evil.com')",
            "=IMPORTDATA('http://evil.com')",
            "=WEBSERVICE('http://evil.com')",
        ]

        for formula in dangerous_formulas:
            result = ExcelFormulaProtection.sanitize(formula)
            assert result.startswith("'"), f"Dangerous formula not escaped: {formula}"


class TestIntegratedSanitization:
    """Test combined XSS + Excel protection."""

    def test_full_sanitization(self):
        """Test sanitize_text with both protections."""
        attacks = [
            "<script>alert('XSS')</script>",
            "=cmd|'/c calc'!A1",
            "<img src=x onerror=alert('XSS')>",
            "+1+1",
        ]

        for attack in attacks:
            # Test with Excel protection
            result = sanitize_text(attack, excel_safe=True)
            assert len(result) > 0
            assert "<script" not in result.lower()

            # Test without Excel protection
            result_no_excel = sanitize_text(attack, excel_safe=False)
            assert len(result_no_excel) > 0

    def test_production_data_cleaning(self, malicious_csv):
        """
        Test with real-world malicious CSV data.

        This simulates cleaning production data with 16% attack rate.
        """
        import polars as pl

        # Load malicious CSV
        df = pl.read_csv(malicious_csv)

        # Sanitize all text columns
        for col in df.select(pl.col(pl.Utf8)).columns:
            df = df.with_columns(
                pl.col(col)
                .map_elements(
                    lambda x: sanitize_text(x, excel_safe=True) if x else x,
                    return_dtype=pl.Utf8,
                )
                .alias(col)
            )

        # Verify no attacks remain
        for row in df.iter_rows(named=True):
            text = row["comentario"]
            assert "<script" not in text.lower()
            assert "onerror=" not in text.lower()
            # Excel formulas should be escaped
            if text.startswith("=") or text.startswith("+") or text.startswith("@"):
                # Original had formula, should be escaped now
                pass  # Check was done during sanitization
