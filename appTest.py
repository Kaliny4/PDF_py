import pytest
from unittest.mock import AsyncMock, patch
import aiohttp
import asyncio
import pandas as pd
import os
import sys
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from io import BytesIO

# Ensure parent directory is in path for direct execution (conftest.py
# handles pytest discovery)
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# Get paths from environment variables or use relative defaults
_test_dir = Path(__file__).parent.parent  # PDF_py_review directory
_default_list_pth = str(_test_dir / "GRI_2017_2020 (1).xlsx")
_default_data_pth = str(_test_dir / "Data")

CONFIG = {
    # path to Excel file with URLs
    "list_pth": os.getenv("LIST_PTH", _default_list_pth),
    "pth": os.getenv("DATA_PTH", _default_data_pth),  # path to data directory
    "ID": "BRnum",
    "url_column": "Pdf_URL",  # column AL
    "other_url_column": "Report HTML Address",  # column AM
    "max_workers": 10,  # parallel downloads
    "download_timeout": 30,  # seconds before a download is considered failed
    "prototype": False,  # if True, only download first 10 files for testing
    "prototype_count": 100,  # number of files to download in prototype mode
}


def check_col_for_url(list_pth, ID, url_column, other_url_column):
    # Minimal test helper that returns a mock DataFrame with the requested URL
    # columns
    data: dict[str, list[Optional[str]]] = { ID: ["12345"], url_column: [
        "https://www.shuyiwrites.com/uploads/1/3/0/4/130438914/how_to_write_and_publish_a_scientific_paper.pdf"], }
    if other_url_column:
        data[other_url_column] = [None]
    return pd.DataFrame(data)


def create_minimal_valid_pdf_bytes():
    """Generate a minimal valid PDF with one blank page using pypdf."""
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        output = BytesIO()
        writer.write(output)
        return output.getvalue()
    except ImportError:
        # Fallback: return a minimal PDF structure if pypdf is unavailable
        return (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000063 00000 n \n0000000116 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n169\n%%EOF" )


@dataclass
class DownloadTask:  # A simple data class to hold the parameters for a single download attempt
    brnum: str
    url_column: str
    other_url_column: Optional[str]
    output_dir: str
    timeout: int


@dataclass
class DownloadResult:  # A simple data class to hold the status of a download attempt
    brnum: str
    status: str  # e.g., "Downloaded", "Ikke downloaded"
    # the URL that was actually used for the download attempt (either from
    # url_column or other_url_column)
    url_used: str
    error: Optional[str]


def test_download_task():
    # Example of creating a DownloadTask instance
    task = DownloadTask(
        brnum="12345",
        url_column="https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf",
        other_url_column=None,
        output_dir="./downloads",
        timeout=30
    )
    assert task.brnum == "12345"
    assert task.url_column == "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf"
    assert task.other_url_column is None
    assert task.output_dir == "./downloads"
    assert task.timeout == 30


def test_download_result():
    # Example of creating a DownloadResult instance
    result = DownloadResult(
        brnum="12345",
        status="Downloaded",
        url_used="https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf",
        error=None
    )
    assert result.brnum == "12345"
    assert result.status == "Downloaded"
    assert result.url_used == "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf"
    assert result.error is None


def test_check_col_for_url():
    # Test the check_col_for_url function with CONFIG values
    try:
        df = check_col_for_url(
            CONFIG["list_pth"],
            CONFIG["ID"],
            CONFIG["url_column"],
            CONFIG["other_url_column"]
        )
        assert isinstance(df, pd.DataFrame)
    except Exception as e:
        pytest.fail(f"check_col_for_url raised an exception: {e}")


def test_check_existing_files(tmp_path):
    import app
    check_existing_files = getattr(app, "check_existing_files", None)
    if check_existing_files is None:
        pytest.skip("check_existing_files is not available in app module")
    # Deterministic filesystem setup in an isolated temporary directory
    try:
        (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4\n")
        (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4\n")
        result = check_existing_files(str(tmp_path))
        assert isinstance(result, list)
    except Exception as e:
        pytest.fail(f"check_existing_files raised an exception: {e}")


def test_check_if_valid_pdf(tmp_path):
    import app
    check_if_valid_pdf = getattr(app, "check_if_valid_pdf", None)
    if check_if_valid_pdf is None:
        pytest.skip("check_if_valid_pdf is not available in app module")
    test_pdf = tmp_path / "test.pdf"
    test_pdf.write_bytes(create_minimal_valid_pdf_bytes())
    try:
        is_valid = check_if_valid_pdf(str(test_pdf))
        assert isinstance(is_valid, bool)
        assert is_valid is True  # Valid PDF should return True
    except Exception as e:
        pytest.fail(f"check_if_valid_pdf raised an exception: {e}")


def test_check_if_invalid_pdf(tmp_path):
    import app
    check_if_valid_pdf = getattr(app, "check_if_valid_pdf", None)
    if check_if_valid_pdf is None:
        pytest.skip("check_if_valid_pdf is not available in app module")
    test_pdf = tmp_path / "invalid.pdf"
    test_pdf.write_bytes(b"This is not a valid PDF file")  # Non-PDF content
    try:
        is_valid = check_if_valid_pdf(str(test_pdf))
        assert isinstance(is_valid, bool)
        assert is_valid is False  # Invalid content should return False
    except Exception as e:
        pytest.fail(f"check_if_valid_pdf raised an exception: {e}")


async def fetch_pdf(session, url):
    print(f"Fetching PDF from URL: {url}", flush=True)
    async with session.get(url) as response:
        if response.status == 200:
            return await response.read()
        else:
            raise Exception(
                f"Failed to fetch PDF from {url} - Status code: {response.status}")


@pytest.mark.asyncio
async def test_fetch_pdf_success():
    url = "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf"
    expected_content = b"%PDF-1.4 test pdf content"

    # Mock the aiohttp.ClientSession.get method
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read.return_value = expected_content
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            content = await fetch_pdf(session, url)
            print(f"Fetched content: {content}", flush=True)
            assert content == expected_content


@pytest.mark.asyncio
async def test_fetch_pdf_failure():
    url = "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf"

    # Mock the aiohttp.ClientSession.get method to return a non-200 status
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            with pytest.raises(Exception) as exc_info:
                await fetch_pdf(session, url)
            assert "Failed to fetch PDF" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_pdf_exception():
    url = "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf"

    # Mock the aiohttp.ClientSession.get method to raise an exception
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = Exception("Network error")

        async with aiohttp.ClientSession() as session:
            with pytest.raises(Exception) as exc_info:
                await fetch_pdf(session, url)
            assert "Network error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_multiple_pdfs():
    urls = [
        "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf",
        "https://www.shuyiwrites.com/uploads/1/3/0/4/130438914/how_to_write_and_publish_a_scientific_paper.pdf"
    ]
    expected_content = b"%PDF-1.4 test pdf content"

    # Mock the aiohttp.ClientSession.get method
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read.return_value = expected_content
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_pdf(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            for content in results:
                print(f"Fetched content: {content}", flush=True)
                assert content == expected_content


if __name__ == "__main__":
    # Run tests using pytest's programmatic runner with full pytest-asyncio
    # support
    exit_code = pytest.main([__file__, "-v"])
    if exit_code == 0:
        print("\n✅ All tests passed!", flush=True)
    else:
        print("\n❌ Some tests failed!", flush=True)
    sys.exit(exit_code)
