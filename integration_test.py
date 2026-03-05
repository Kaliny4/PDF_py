import sys
from pathlib import Path
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

# Ensure parent directory is in path for direct execution (conftest.py
# handles pytest discovery)
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from download_pdf_improved import (
    download_file,
    download_multiple_files,
    check_existing_files,
    DownloadTask,
)


def create_minimal_valid_pdf_bytes():
    """Generate a minimal valid PDF with one blank page."""
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        output = BytesIO()
        writer.write(output)
        return output.getvalue()
    except ImportError:
        return (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000063 00000 n \n0000000116 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n169\n%%EOF" )


@pytest.mark.integration
def test_integration_download_valid_pdf(tmp_path):
    """
    Integration test: Download a single valid PDF and verify file creation.
    Core end-to-end workflow: network request → file write → PDF validation.
    """
    dwn_pth = tmp_path / "dwn"
    dwn_pth.mkdir()

    with patch("download_pdf_improved.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [
            create_minimal_valid_pdf_bytes()]
        mock_get.return_value = mock_response

        task = DownloadTask(
            brnum="BR001",
            url_column="https://example.com/test.pdf",
            other_url_column=None,
            output_dir=str(dwn_pth),
            timeout=30
        )

        result = download_file(task)

        assert result.brnum == "BR001"
        assert result.status == "Downloaded"
        assert result.error is None
        assert (dwn_pth / "BR001.pdf").exists()
        assert (dwn_pth / "BR001.pdf").stat().st_size > 0


@pytest.mark.integration
def test_integration_skip_existing_files(tmp_path):
    """
    Integration test: Verify that already-downloaded files are not re-downloaded.
    Simulates the main() workflow: filters existing files and only downloads new ones.
    Prevents accidental overwriting and reduces network traffic.
    """
    dwn_pth = tmp_path / "dwn"
    dwn_pth.mkdir()

    # Create pre-existing PDF for BR001
    existing_pdf = dwn_pth / "BR001.pdf"
    original_content = create_minimal_valid_pdf_bytes()
    existing_pdf.write_bytes(original_content)
    original_size = existing_pdf.stat().st_size

    # Create DataFrame with two rows (one existing, one new)
    df2 = pd.DataFrame({
        "BRnum": ["BR001", "BR002"],
        "Pdf_URL": [
            "https://example.com/existing.pdf",
            "https://example.com/new.pdf"
        ]
    }).set_index("BRnum")
    df2["pdf_downloaded"] = None
    df2["download_error"] = None

    with patch("download_pdf_improved.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        # Return valid PDF (not the original content) to prove it's a new
        # download
        mock_response.iter_content.return_value = [
            create_minimal_valid_pdf_bytes()]
        mock_get.return_value = mock_response

        # Simulate main() logic: filter out existing files before creating
        # tasks
        existing = check_existing_files(str(dwn_pth))
        df_to_download = df2[~df2.index.isin(existing)]  # Only BR002

        # Verify filtering worked
        assert "BR001" in existing
        assert len(df_to_download) == 1
        assert "BR002" in df_to_download.index

        # Create tasks only for non-existing files
        tasks = [
            DownloadTask(
                brnum=brnum,
                url_column=str(df_to_download.at[brnum, "Pdf_URL"]),
                other_url_column=None,
                output_dir=str(dwn_pth),
                timeout=30
            )
            for brnum in df_to_download.index
        ]

        # Execute download for filtered list (only BR002)
        df2 = download_multiple_files(tasks, df2, max_workers=1)

        # Verify existing file (BR001) was NOT modified
        assert existing_pdf.exists()
        assert existing_pdf.stat().st_size == original_size  # Size unchanged
        assert existing_pdf.read_bytes() == original_content  # Content unchanged

        # Verify BR001's DataFrame status columns were NOT updated (file was
        # skipped)
        assert df2.at["BR001", "pdf_downloaded"] is None
        assert df2.at["BR001", "download_error"] is None

        # Verify new file (BR002) WAS downloaded
        new_pdf = dwn_pth / "BR002.pdf"
        assert new_pdf.exists()
        assert df2.at["BR002", "pdf_downloaded"] == "Downloaded"

        # Verify requests.get was only called once (for BR002, not BR001)
        assert mock_get.call_count == 1


@pytest.mark.integration
def test_integration_batch_download_mixed_results(tmp_path):
    """
    Integration test: Download multiple files with mixed success/failure scenarios.
    Tests the main production workflow: batch processing with error handling and DataFrame updates.
    """
    dwn_pth = tmp_path / "dwn"
    dwn_pth.mkdir()

    df2 = pd.DataFrame({
        "BRnum": ["BR001", "BR002", "BR003"],
        "Pdf_URL": [
            "https://example.com/valid1.pdf",
            "https://example.com/valid2.pdf",
            "https://example.com/error.pdf"
        ]
    }).set_index("BRnum")

    df2["pdf_downloaded"] = None
    df2["download_error"] = None

    def mock_get_side_effect(url, **kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        if "error" in url:
            error = Exception("404 Not Found")
            mock_response.raise_for_status.side_effect = error
            # Also configure iter_content to prevent it from returning an
            # unconfigured MagicMock
            mock_response.iter_content.side_effect = error
        else:
            mock_response.iter_content.return_value = [
                create_minimal_valid_pdf_bytes()]

        return mock_response

    with patch("download_pdf_improved.requests.get", side_effect=mock_get_side_effect):
        tasks = [
            DownloadTask(
                brnum=brnum,
                url_column=str(df2.at[brnum, "Pdf_URL"]),
                other_url_column=None,
                output_dir=str(dwn_pth),
                timeout=30
            )
            for brnum in df2.index
        ]

        df2 = download_multiple_files(tasks, df2, max_workers=2)

        # Verify results
        assert df2.at["BR001", "pdf_downloaded"] == "Downloaded"
        assert df2.at["BR002", "pdf_downloaded"] == "Downloaded"
        assert df2.at["BR003", "pdf_downloaded"] == "Ikke downloaded"

        # Verify files
        assert (dwn_pth / "BR001.pdf").exists()
        assert (dwn_pth / "BR002.pdf").exists()
        assert not (dwn_pth / "BR003.pdf").exists()

        # Verify error recorded
        assert df2.at["BR003", "download_error"] is not None

if __name__ == "__main__":
    pytest.main([__file__])
