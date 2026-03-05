import os
import pytest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
import sys
from pathlib import Path
import requests
from pypdf.errors import PdfReadError

# Ensure parent directory is in path for direct execution (conftest.py
# handles pytest discovery)
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from download_files import download_file, download_multiple_files


def test_download_file():
    # Mock test with sample arguments
    args = ("12345", "https://example.com/test.pdf", "./downloads", 30)

    with patch('download_files.requests.get') as mock_get:
        mock_response = mock_get.return_value
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'%PDF-1.4 test content']

        with patch('download_files.open', mock_open()) as mock_file:
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.return_value.pages = [1]  # Mock 1 page

                brnum, status, error = download_file(args)

                assert brnum == "12345"
                assert status == "Downloaded"
                assert error is None
                mock_get.assert_called_once()

                # Verify file was opened for writing with correct filename and
                # mode
                expected_filename = os.path.join("./downloads", "12345.pdf")
                # Check that open was called with the write mode (first call)
                call_args_list = mock_file.call_args_list
                assert len(call_args_list) >= 1
                assert call_args_list[0][0] == (expected_filename, "wb")

                # Verify file write was called with the PDF content
                mock_file().write.assert_called_with(b'%PDF-1.4 test content')


def test_download_file_http_error():
    # Test HTTPError scenario: network request fails
    args = ("12345", "https://example.com/not-found.pdf", "./downloads", 30)

    with patch('download_files.requests.get') as mock_get:
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError(
            "404 Not Found")

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader'):
                brnum, status, error = download_file(args)

                assert brnum == "12345"
                assert status == "Ikke downloaded"
                assert error is not None
                assert "404" in error or "HTTPError" in error


def test_download_file_timeout():
    # Test Timeout scenario: request times out
    args = ("12345", "https://example.com/slow.pdf", "./downloads", 5)

    with patch('download_files.requests.get') as mock_get:
        mock_get.side_effect = requests.Timeout("Connection timed out")

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader'):
                brnum, status, error = download_file(args)

                assert brnum == "12345"
                assert status == "Ikke downloaded"
                assert error is not None
                assert "Timeout" in error or "timed out" in error


def test_download_file_pdf_read_error():
    # Test PdfReadError scenario: PDF validation fails
    args = ("12345", "https://example.com/corrupt.pdf", "./downloads", 30)

    with patch('download_files.requests.get') as mock_get:
        mock_response = mock_get.return_value
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'invalid pdf data']

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.side_effect = PdfReadError("Invalid PDF structure")
                with patch('download_files.os.path.exists', return_value=True):
                    with patch('download_files.os.remove'):
                        brnum, status, error = download_file(args)

                        assert brnum == "12345"
                        assert status == "Ikke downloaded"
                        assert error is not None
                        assert "Invalid" in error or "PDF" in error


def test_download_file_invalid_pdf_no_pages():
    # Test invalid PDF: PDF has no pages
    args = ("12345", "https://example.com/empty.pdf", "./downloads", 30)

    with patch('download_files.requests.get') as mock_get:
        mock_response = mock_get.return_value
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'%PDF-1.4 empty']

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.return_value.pages = []  # Empty pages list
                with patch('download_files.os.path.exists', return_value=True):
                    with patch('download_files.os.remove'):
                        brnum, status, error = download_file(args)

                        assert brnum == "12345"
                        assert status == "Ikke downloaded"
                        assert error == "PDF has no pages"


def test_download_multiple_files():
    # Create mock DataFrame
    df2 = pd.DataFrame(
    {
        'pdf_downloaded': [
            None,
            None],
            'Pdf_URL': [
                "https://www.shuyiwrites.com/uploads/1/3/0/4/130438914/how_to_write_and_publish_a_scientific_paper.pdf",
                "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf"] },
                index=[
                    "BR001",
                     "BR002"])

    args_list = [
    ("BR001",
    "https://www.shuyiwrites.com/uploads/1/3/0/4/130438914/how_to_write_and_publish_a_scientific_paper.pdf",
    "./downloads",
    30),
    ("BR002",
    "https://bcuathletics.com/documents/2026/3/1/BGSU3126.pdf",
    "./downloads",
     30) ]

    # Mock network and file I/O, but let download_file run real logic
    with patch('download_files.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'%PDF-1.4 test']
        mock_get.return_value = mock_response

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.return_value.pages = [1, 2]  # Mock pages

                # Actually call the orchestration function
                download_multiple_files(args_list, df2)

                # Verify results were written to DataFrame
                assert df2.at["BR001", "pdf_downloaded"] == "Downloaded"
                assert df2.at["BR002", "pdf_downloaded"] == "Downloaded"
                # Verify requests.get was called for each file
                assert mock_get.call_count == 2


def test_download_multiple_files_with_network_timeout():
    # Test download_multiple_files with network timeout scenarios
    df2 = pd.DataFrame({
        'pdf_downloaded': [None, None],
    }, index=["BR001", "BR002"])

    args_list = [
        ("BR001", "https://example.com/timeout.pdf", "./downloads", 5),
        ("BR002", "https://example.com/valid.pdf", "./downloads", 5)
    ]

    with patch('download_files.requests.get') as mock_get:
        # First call times out, second succeeds
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'%PDF-1.4 test']

        mock_get.side_effect = [
            requests.Timeout("Connection timed out"),
            mock_response
        ]

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.return_value.pages = [1]

                download_multiple_files(args_list, df2)

                # Verify timeout result in DataFrame
                assert df2.at["BR001", "pdf_downloaded"] == "Ikke downloaded"
                assert df2.at["BR002", "pdf_downloaded"] == "Downloaded"
                # Verify requests.get was called for both
                assert mock_get.call_count == 2


def test_download_multiple_files_with_http_error():
    # Test download_multiple_files with HTTP 4xx/5xx errors
    df2 = pd.DataFrame({
        'pdf_downloaded': [None, None],
    }, index=["BR001", "BR002"])

    args_list = [
        ("BR001", "https://example.com/notfound.pdf", "./downloads", 30),
        ("BR002", "https://example.com/valid.pdf", "./downloads", 30)
    ]

    with patch('download_files.requests.get') as mock_get:
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = requests.HTTPError(
            "404 Not Found")

        mock_response_ok = MagicMock()
        mock_response_ok.raise_for_status = MagicMock()
        mock_response_ok.iter_content.return_value = [b'%PDF-1.4 test']

        mock_get.side_effect = [mock_response_fail, mock_response_ok]

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.return_value.pages = [1]

                download_multiple_files(args_list, df2)

                # Verify HTTP error result in DataFrame
                assert df2.at["BR001", "pdf_downloaded"] == "Ikke downloaded"
                assert df2.at["BR002", "pdf_downloaded"] == "Downloaded"
                assert mock_get.call_count == 2


def test_download_multiple_files_with_corrupt_pdf():
    # Test download_multiple_files with corrupt PDF content
    df2 = pd.DataFrame({
        'pdf_downloaded': [None, None],
    }, index=["BR001", "BR002"])

    args_list = [
        ("BR001", "https://example.com/corrupt.pdf", "./downloads", 30),
        ("BR002", "https://example.com/valid.pdf", "./downloads", 30)
    ]

    with patch('download_files.requests.get') as mock_get:
        # Both HTTP requests succeed, but first PDF read fails (corrupt)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'invalid data']
        mock_get.return_value = mock_response

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader') as mock_pdf:
                # First raises exception, second succeeds
                mock_pdf.side_effect = [
                    Exception("PDF is corrupted"),
                    MagicMock(pages=[1])
                ]
                with patch('download_files.os.path.exists', return_value=True):
                    with patch('download_files.os.remove'):
                        download_multiple_files(args_list, df2)

                        # Verify corrupt PDF result in DataFrame
                        assert df2.at["BR001",
     "pdf_downloaded"] == "Ikke downloaded"
                        assert df2.at["BR002",
     "pdf_downloaded"] == "Downloaded"
                        # Verify requests.get was called for both
                        assert mock_get.call_count == 2


def test_download_multiple_files_with_file_write_error():
    # Test download_multiple_files with file write failures
    df2 = pd.DataFrame({
        'pdf_downloaded': [None, None],
    }, index=["BR001", "BR002"])

    args_list = [
        ("BR001", "https://example.com/noperm.pdf", "./downloads", 30),
        ("BR002", "https://example.com/valid.pdf", "./downloads", 30)
    ]

    with patch('download_files.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b'%PDF-1.4 test']
        mock_get.return_value = mock_response

        # Create mock_open for successful case; IOError raised directly for
        # failure case
        open_succeed = mock_open()

        def mock_open_side_effect(*args, **kwargs):
            if args[0].endswith("BR001.pdf"):
                raise IOError("Permission denied")
            else:
                return open_succeed(*args, **kwargs)

        with patch('download_files.open', side_effect=mock_open_side_effect):
            with patch('download_files.PdfReader') as mock_pdf:
                mock_pdf.return_value.pages = [1]

                download_multiple_files(args_list, df2)

                # Verify file write error result in DataFrame
                assert df2.at["BR001", "pdf_downloaded"] == "Ikke downloaded"
                assert df2.at["BR002", "pdf_downloaded"] == "Downloaded"


def test_download_multiple_files_all_failures():
    # Test download_multiple_files where all downloads fail
    df2 = pd.DataFrame({
        'pdf_downloaded': [None, None],
    }, index=["BR001", "BR002"])

    args_list = [
        ("BR001", "https://example.com/bad1.pdf", "./downloads", 30),
        ("BR002", "https://example.com/bad2.pdf", "./downloads", 30)
    ]

    with patch('download_files.requests.get') as mock_get:
        mock_get.side_effect = requests.Timeout("All timeouts")

        with patch('download_files.open', mock_open()):
            with patch('download_files.PdfReader'):
                download_multiple_files(args_list, df2)

                # Verify all failures in DataFrame
                assert df2.at["BR001", "pdf_downloaded"] == "Ikke downloaded"
                assert df2.at["BR002", "pdf_downloaded"] == "Ikke downloaded"
                # Verify requests.get was called twice
                assert mock_get.call_count == 2


if __name__ == "__main__":
    exit_code = pytest.main([__file__, "-v"])
    if exit_code == 0:
        print("\n✅ All tests passed!", flush=True)
    else:
        print("\n❌ Some tests failed!", flush=True)
    exit(exit_code)
