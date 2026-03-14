"""Read and validate CSV uploads containing company names."""

import io

import pandas as pd


def read_companies_csv(uploaded_file) -> tuple[list[str], str | None]:
    """
    Parse and validate a CSV from st.file_uploader.

    uploaded_file: the object from st.file_uploader
    Returns: (list of company name strings, error message or None)

    Validation rules:
    - File must not be empty
    - Must have at least one column
    - The column containing company names must be called 'company' or 'Company' or 'name' or 'Name'
    - Strip leading/trailing whitespace from each company name
    - Skip rows where the company name is blank
    - Return an error string (not an exception) if any rule fails
    """
    if uploaded_file is None:
        return [], "No file uploaded."

    try:
        raw = uploaded_file.read()
    except Exception as e:
        return [], f"Could not read file: {e}"

    if not raw or len(raw.strip()) == 0:
        return [], "File is empty."

    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        return [], f"Invalid CSV: {e}"

    if df.empty:
        return [], "CSV has no rows."

    if len(df.columns) < 1:
        return [], "CSV must have at least one column."

    name_col = None
    allowed = ("company", "Company", "name", "Name")
    for c in df.columns:
        if str(c).strip() in allowed:
            name_col = c
            break

    if name_col is None:
        return [], "CSV must have a column named 'company', 'Company', 'name', or 'Name'."

    companies = (
        df[name_col]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .tolist()
    )
    companies = [c for c in companies if c and not c.isspace()]

    if not companies:
        return [], "No valid company names found (all rows are blank)."

    return companies, None
