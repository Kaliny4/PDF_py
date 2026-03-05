# -*- coding: utf-8 -*-


from dataclasses import dataclass
from typing import Optional


@dataclass
class DownloadTask:
    """All information needed to attempt a single PDF download."""
    brnum: str
    url_column: str
    other_url_column: Optional[str]
    output_dir: str
    timeout: int
    max_retries: int = 5


@dataclass
class DownloadResult:
    """Outcome of a single download attempt."""
    brnum: str
    status: str           # "Downloaded" | "Ikke downloaded"
    url_used: str         # the URL that ultimately succeeded (or last tried)
    error: Optional[str]  # last error message, if any
