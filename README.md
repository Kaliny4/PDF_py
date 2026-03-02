### Multithreaded PDF Downloader (download_pdf_improved.py)
Python script for downloading PDF files in parallel from URLs stored in an Excel file.
This version uses multithreading via ThreadPoolExecutor.

##### Dependencies
pip install pandas PyPDF2 requests openpyxl tqdm


| Library            | Purpose                  |
| ------------------ | ------------------------ |
| pandas             | Read/write Excel         |
| PyPDF2             | Validate downloaded PDFs |
| requests           | HTTP downloads           |
| openpyxl           | Excel writing engine     |
| tqdm               | Progress bar             |
| concurrent.futures | Threading                |

##### Architecture 

| Component                   | Responsibility                    |
| --------------------------- | --------------------------------- |
| `CONFIG`                    | User-editable configuration       |
| `DownloadTask`              | Represents a single download job  |
| `DownloadResult`            | Represents download result        |
| `check_col_for_url()`       | Prepares and validates input data |
| `download_file()`           | Downloads and validates a PDF     |
| `download_multiple_files()` | Executes downloads in parallel    |
| `main()`                    | Orchestrates full workflow        |

##### How It Works

python download_pdf_improved.py

Excel File should contain BRnum, it must be unique; Pdf_URL with http link, if it is empty, the script uses Report HTML Address.

Read Input Excel >>> 
Loads URLs and sets BRnum as index >>> 
clean Data >>> 
fils missing URLs from fallback column >>> 
removes rows without URLs >>> 
skips already downloaded files >>>
Create Download Tasks (Each row becomes a DownloadTask object) >>> 
Parallel Download Execution:
- ThreadPoolExecutor(max_workers=CONFIG["max_workers"])
- Each thread: Downloads PDF in chunks, Saves file Validates, file using PyPDF2, Returns structured result >>>
Save Log: download_log_improved.xlsx, download_log_improved.log




