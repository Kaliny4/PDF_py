# -*- coding: utf-8 -*-
#Configuration settings for the PDF Downloader project.  Paths are loaded

import os
import multiprocessing
#from dotenv import load_dotenv

# Load .env file from the same directory as this config.py file
#load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIST_PTH=os.path.join(BASE_DIR, "GRI_2017_2020.xlsx")

CONFIG = {
    # --- Paths (loaded from .env) ---
    #"list_pth": os.getenv("LIST_PTH"),   # Excel file with URLs
    #"pth":      os.getenv("BASE_PTH"),   # Base output directory
    "list_pth": LIST_PTH,   # Excel file with URLs
    "pth":      BASE_DIR,   # Base output directory
    "ID":                "BRnum",
    "url_column":        "Pdf_URL",           # primary URL column
    "other_url_column":  "Report HTML Address",  # fallback URL column

    # --- Download behaviour ---
    "max_workers":       multiprocessing.cpu_count(),  # dynamic core allocation
    "download_timeout":  30,     # seconds per request
    "max_retries":       5,      # retry attempts before marking as failed

    "Prototype":         True,   # set False to download everything
    "Prototype_count":   100,    # files to download in prototype mode
}
