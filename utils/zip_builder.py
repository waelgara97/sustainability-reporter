"""Package selected PDFs into a zip for download."""

import io
import os
import zipfile


def build_zip(selected_filenames: list[str], storage_path: str) -> bytes:
    """
    Build a zip containing the selected PDF files from Crawlee storage.

    selected_filenames: list of PDF filenames the user checked
    storage_path: path to where Crawlee saved the PDFs (from config.py)
    Returns: zip file as bytes, ready to pass to st.download_button
    """
    storage_real = os.path.realpath(storage_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in selected_filenames:
            if not name or not name.strip():
                continue
            file_path = os.path.realpath(os.path.join(storage_path, name))
            # Guard against path traversal (e.g. filenames containing ../)
            if not file_path.startswith(storage_real + os.sep):
                continue
            try:
                with open(file_path, "rb") as f:
                    zf.writestr(os.path.basename(file_path), f.read())
            except FileNotFoundError:
                continue
            except OSError:
                continue
    buf.seek(0)
    return buf.read()
