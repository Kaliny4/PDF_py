"""
Pytest configuration file to set up the Python path for test discovery.
This allows tests to import modules from the parent directory without
manually manipulating sys.path in each test file.
"""
import sys
from pathlib import Path

# Add the parent directory (PDF_py_review) to the Python path
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
    "markers",
     "integration: marks tests as integration tests (deselect with '-m \"not integration\"')" )
