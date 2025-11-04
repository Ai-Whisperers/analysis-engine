"""
Pytest configuration and fixtures for integration tests.
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir():
    """Fixture for test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_csv(test_data_dir, temp_dir):
    """Create sample CSV file for testing."""
    csv_content = """plan,score,outage_flag,comentario,fecha
Basic,9,true,Excellent service!,2024-01-15
Premium,3,false,<script>alert('XSS')</script>,2024/01/16
Basic,7,si,Good overall,15-01-2024
Premium,2,1,=cmd|'/c calc'!A1,2024-01-17 10:30:00
"""
    csv_path = temp_dir / "test_data.csv"
    csv_path.write_text(csv_content)
    return str(csv_path)


@pytest.fixture
def malicious_csv(temp_dir):
    """Create CSV with injection attacks for security testing."""
    csv_content = """comentario,score
<script>alert('XSS')</script>,5
<img src=x onerror=alert('XSS')>,3
=cmd|'/c calc'!A1,7
@SUM(A1:A10),8
+1+1,6
<iframe src=javascript:alert('XSS')>,4
"""
    csv_path = temp_dir / "malicious.csv"
    csv_path.write_text(csv_content)
    return str(csv_path)


@pytest.fixture(scope="session")
def mock_onnx_model(tmp_path_factory):
    """
    Create mock ONNX model for testing.
    Note: This is a placeholder. Real tests should use actual model or mock.
    """
    model_dir = tmp_path_factory.mktemp("models")
    return str(model_dir / "model.onnx")
