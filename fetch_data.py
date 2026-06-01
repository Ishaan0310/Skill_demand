"""
fetch_data.py  —  Skill Tracker 

Run: python3 fetch_data.py
"""

import os
import sys
import glob
import ast

import pandas as pd
import kaggle


# ── CONFIG ────────────────────────────────────────────────────────────────────
# Swap datasets: change DATASET_ID + the column-name variables below.
# The processing functions (parse_skills, extract_experience, etc.) may also
# will be needing update depending on how the new dataset structures its data.

DATASET_ID       = "lukebarousse/data-analyst-job-postings-google-search"
DOWNLOAD_DIR     = "./raw_data"
OUTPUT_CSV       = "job_postings.csv"

# Column names in the downloaded CSV
COL_TITLE_SHORT  = "job_title_short"    
COL_TITLE_FULL   = "job_title"          
COL_COMPANY      = "company_name"
COL_LOCATION     = "job_location"       # "City, State" or "Anywhere"
COL_COUNTRY      = "job_country"
COL_SKILLS       = "job_skills"         # stored as Python list literal: ['python', 'sql']
COL_SALARY       = "salary_year_avg"    
COL_SCHEDULE     = "job_schedule_type"  #

# rows with no skills listed aren't useful for analysis — always drop them
DROP_ROWS_NO_SKILLS = True

# set True to keep only rows that have salary data
DROP_ROWS_NO_SALARY = False

# anything below this USD/year is probably a data entry error
MIN_SALARY_USD   = 20_000
# ─────────────────────────────────────────────────────────────────────────────


def download():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"downloading  →  {DATASET_ID}")
    print("this dataset is ~200MB, may take a minute or two on slower connections.")
    kaggle.api.authenticate()
    kaggle.api.dataset_download_files(
        DATASET_ID, path=DOWNLOAD_DIR, unzip=True, quiet=False
    )
    print("download done.\n")


def find_main_csv():
    csvs = glob.glob(os.path.join(DOWNLOAD_DIR, "**/*.csv"), recursive=True)
    if not csvs:
        print("no CSV found after download. check the raw_data/ folder.")
        sys.exit(1)
    # prefer a file with "job_posting" in the name
    for f in csvs:
        if "job_posting" in os.path.basename(f).lower():
            return f
    return max(csvs, key=os.path.getsize)


def check_columns(df):
    needed = [COL_TITLE_SHORT, COL_TITLE_FULL, COL_COMPANY,
              COL_LOCATION, COL_SKILLS, COL_SALARY]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        print(f"column mismatch — expected these but didn't find them: {missing}")
        print(f"columns actually in the file: {list(df.columns)}")
        print("update the COL_* variables in the CONFIG section to match.")
        sys.exit(1)


def parse_skills(val):
    """
    skills column is a Python list literal like: ['python', 'sql', 'excel']
    ast.literal_eval safely converts that string into a real Python list.
    """
    if not val or pd.isna(val):
        return ""
    try:
        items = ast.literal_eval(str(val))
        if isinstance(items, list):
            return ", ".join(s.strip().title() for s in items if s)
    except (ValueError, SyntaxError):
        pass
    # fallback: return as-is if parsing fails
    return str(val).strip()


def extract_experience(full_title):
    """
    reads seniority from job title keywords.
    returns one of: Junior / Mid / Senior / Lead
    """
    t = str(full_title).lower()
    if any(k in t for k in ["lead", "head", "director", "principal", "staff"]):
        return "Lead"
    if any(k in t for k in ["senior", "sr.", " sr ", "sr-"]):
        return "Senior"
    if any(k in t for k in ["junior", "jr.", " jr ", "entry", "associate", "intern"]):
        return "Junior"
    return "Mid"


def extract_city(location, country):
    """
    turns 'Austin, TX' → 'Austin'
    turns 'Anywhere'   → 'Remote'
    """
    loc = str(location).strip()
    if not loc or loc.lower() in ["anywhere", "nan", "remote", ""]:
        return "Remote"
    city = loc.split(",")[0].strip()
    return city if city and city.lower() != "nan" else str(country).strip()


def normalize_schedule(val):
    s = str(val).lower()
    if "full" in s:
        return "Full-time"
    if "part" in s:
        return "Part-time"
    if any(k in s for k in ["contract", "freelance", "temp"]):
        return "Contract"
    return "Full-time"


def process(csv_path):
    print(f"loading {csv_path} ...")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  {len(df):,} rows loaded")

    check_columns(df)

    if DROP_ROWS_NO_SKILLS:
        df = df[df[COL_SKILLS].notna() & (df[COL_SKILLS].astype(str).str.strip() != "")]
        print(f"  {len(df):,} rows after dropping those with no skills")

    if DROP_ROWS_NO_SALARY:
        df = df[df[COL_SALARY].notna()]
        print(f"  {len(df):,} rows after dropping those with no salary")

    out = pd.DataFrame()
    out["job_title"]        = df[COL_TITLE_SHORT].fillna("Unknown").str.strip()
    out["company"]          = df[COL_COMPANY].fillna("Unknown").str.strip()
    out["city"]             = df.apply(
        lambda r: extract_city(r.get(COL_LOCATION, ""), r.get(COL_COUNTRY, "")), axis=1
    )
    out["experience_level"] = df[COL_TITLE_FULL].apply(extract_experience)
    out["employment_type"]  = (
        df[COL_SCHEDULE].apply(normalize_schedule)
        if COL_SCHEDULE in df.columns
        else "Full-time"
    )
    out["skills"]           = df[COL_SKILLS].apply(parse_skills)
    out["salary_usd"]       = pd.to_numeric(df[COL_SALARY], errors="coerce")
    out.loc[out["salary_usd"] < MIN_SALARY_USD, "salary_usd"] = None

    # drop rows where skill parsing produced an empty string
    out = out[out["skills"].str.len() > 0]

    out.to_csv(OUTPUT_CSV, index=False)

    total        = len(out)
    with_salary  = out["salary_usd"].notna().sum()
    print(f"\n{total:,} rows saved  →  {OUTPUT_CSV}")
    print(f"  {with_salary:,} rows have salary data ({with_salary * 100 // total}%)")
    print("next step: python3 load_to_postgres.py")


def main():
    download()
    csv_path = find_main_csv()
    process(csv_path)


if __name__ == "__main__":
    main()
