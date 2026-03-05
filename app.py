# -*- coding: utf-8 -*-

import os
import glob
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pypdf                     
import requests

from tqdm import tqdm

from config  import CONFIG
from classes  import DownloadTask, DownloadResult

# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
     handlers=[
        logging.FileHandler(os.path.join("download_log_improved.log")),  # Log to file
        logging.StreamHandler(),  # Log to console
    ],
)

logger = logging.getLogger(__name__)
socket.setdefaulttimeout(CONFIG["download_timeout"])

def load_url(list_pth, ID, url_column, other_url_column):
    """Load the Excel file and prepare a DataFrame with URLs."""    
    df = pd.read_excel(list_pth, sheet_name=0, index_col=ID)

    if url_column not in df.columns:
        df[url_column] = None

    if other_url_column in df.columns:
        df[url_column] = df[url_column].fillna(df[other_url_column])

    return df


def already_downloaded(dwn_pth):
    """Return a list of BRnums for PDFs that already exist on disk."""
    dwn_files = glob.glob(os.path.join(dwn_pth, "*.pdf"))
    exist = [os.path.basename(f)[:-4] for f in dwn_files]
    return exist

def is_valid_pdf(savefile):
    """Return True if savefile is a readable, non-empty PDF."""
    try:
        with open(savefile, "rb") as f:
            reader = pypdf.PdfReader(f)
            return len(reader.pages) > 0
    except Exception:
        return False


def download_file(task):
    """Attempt to download a single PDF. Returns a DownloadResult with the outcome."""
    savefile  = os.path.join(task.output_dir, f"{task.brnum}.pdf")
    urls_to_try = [task.url_column]
    if task.other_url_column:
        urls_to_try.append(task.other_url_column)

    last_error = None

    for url in urls_to_try:
        for attempt in range(1, task.max_retries + 1): # Try each URL with retries
            try:
                response = requests.get(url, stream=True, timeout=task.timeout)
                response.raise_for_status()

                with open(savefile, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            fh.write(chunk) # chunked writing to handle large files
                # PDF validation
                if is_valid_pdf(savefile):
                    return DownloadResult(
                        brnum=task.brnum,
                        status="Downloaded",
                        url_used=url,
                        error=None,
                    )
                else:
                    last_error = f"Downloaded - but PDF is invalid: {savefile}"
                    logger.warning(f"[attempt {attempt}/{task.max_retries}] "
                                   f"{task.brnum} – {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[attempt {attempt}/{task.max_retries}] "
                               f"{task.brnum} from {url} – {last_error}")

            # Brief back-off before retrying
            if attempt < task.max_retries:
                time.sleep(2 ** (attempt - 1))   # 1 s, 2 s, 4 s, 8 s …

    return DownloadResult(
        brnum=task.brnum,
        status="Ikke downloaded",
        url_used=urls_to_try[-1],
        error=last_error,
    )


def download_all(tasks, df2, max_workers):
    """Run all *tasks* in parallel and write results back into *df*. Returns the updated DataFrame.
    Uses a ThreadPoolExecutor to manage concurrent downloads, and tqdm for progress tracking.
    Each task is a DownloadTask dataclass instance containing all necessary info for the download."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_brnum = {
            executor.submit(download_file, task): task.brnum
            for task in tasks
        }
        progress = tqdm(
            as_completed(future_to_brnum),
            total=len(future_to_brnum),
            desc="Downloading PDFs",
            unit="file",
            leave=True,
        )
        for i, future in enumerate(progress, 1):
            brnum = future_to_brnum[future]
            try:
                result: DownloadResult = future.result(timeout=60)
            except Exception as e:
                result = DownloadResult(
                    brnum=brnum,
                    status="Ikke downloaded",
                    url_used="",
                    error=str(e),
                )

            df2.loc[brnum, "pdf_downloaded"]  = result.status
            df2.loc[brnum, "url_used"]        = result.url_used
            if result.error:
                df2.loc[result.brnum, "download_error"] = result.error

            progress.set_postfix_str(f"{result.brnum}: {result.status}")
            logger.info(f"[{i}/{len(tasks)}] {result.brnum}: {result.status}")

    return df2


def main():
    pth = CONFIG.get("pth")

    dwn_pth = os.path.join(pth, "dwn")
    os.makedirs(dwn_pth, exist_ok=True)

    logger.info("Starting PDF download process")
    logger.info(
        f"Prototype mode – downloading first {CONFIG.get('Prototype_count')} files"
        if CONFIG.get("Prototype") else "Downloading all files"
    )
    logger.info(f"Using {CONFIG.get('max_workers')} worker threads "
                f"(= CPU count on this machine)")

    # Load URLs
    df = load_url(
        list_pth    = CONFIG.get("list_pth"),
        ID      = CONFIG.get("ID"),
        url_column     = CONFIG.get("url_column"),
        other_url_column = CONFIG.get("other_url_column"),
    )
    df = df[df[CONFIG.get("url_column")].notnull()]
    if df.empty:
        logger.error("No valid URLs found – aborting.")
        return
    df2 = df.copy()  # This will hold the download status for each brnum

    # Skip already-downloaded files
    exist = already_downloaded(dwn_pth)
    df2 = df2[
        ~df2.index.astype(str).isin(exist)
    ]  # Filter out rows where the file already exists
    logger.info(f"Skipping {len(exist)} already-downloaded files")

    # Prototype 
    if CONFIG.get("Prototype"):
            df2 = df2.head(CONFIG.get("Prototype_count"))
            logger.info(f"Prototype mode: only downloading first {CONFIG.get('Prototype_count')} files for testing")

    # Build task list
    tasks = [
        DownloadTask(
            brnum             = brnum,
            url_column        = df2.at[brnum, CONFIG.get("url_column")],
            other_url_column  = (
                df2.at[brnum, CONFIG.get("other_url_column")]
                if CONFIG.get("other_url_column") in df2.columns else None
            ),
            output_dir        = dwn_pth,
            timeout           = CONFIG.get("download_timeout"),
            max_retries       = CONFIG.get("max_retries"),
        )
        for brnum in df2.index
    ]

    df2 = download_all(tasks, df2, max_workers=CONFIG.get("max_workers"))

    # Summary
    downloaded     = (df2["pdf_downloaded"] == "Downloaded").sum()
    not_downloaded = (df2["pdf_downloaded"] != "Downloaded").sum()
    print(f"\nDownloaded:     {downloaded}")
    print(f"Not downloaded: {not_downloaded}")

    # Save log
    log_path = os.path.join(CONFIG.get("pth"), "download_log.xlsx")
    df2.to_excel(log_path)
    logger.info(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()
