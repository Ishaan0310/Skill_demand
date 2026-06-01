"""
load_to_postgres.py  —  Skill Tracker 

Run: python3 load_to_postgres.py
"""

import os
import sys
import csv
import ast
import psycopg2
from psycopg2.extras import execute_values


# ── CONFIG ─────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "database": "skill_tracker",
    "user":     "postgres",        # your PostgreSQL username
    "password": "",       # your PostgreSQL password
}

CSV_FILE = "./raw_data/gsearch_jobs.csv"
# ───────────────────────────────────────────────────────────────────────────────

KNOWN_SKILLS = {
    # Languages
    "python", "r", "sql", "java", "scala", "julia", "c++",
    "javascript", "typescript", "bash", "shell", "go",
    # BI & Visualization
    "excel", "tableau", "power bi", "powerbi", "looker", "qlik",
    "qlikview", "qliksense", "sas", "spss", "stata", "matlab",
    "google sheets", "sheets",
    # Cloud Platforms
    "aws", "azure", "gcp", "google cloud", "snowflake", "databricks",
    # Databases
    "postgresql", "mysql", "oracle", "mongodb", "cassandra", "sqlite",
    "bigquery", "redshift", "synapse", "teradata",
    # Big Data & Pipelines
    "spark", "hadoop", "kafka", "airflow", "dbt", "hive", "nifi", "flink",
    # ML / AI
    "machine learning", "deep learning", "tensorflow", "pytorch", "keras",
    "scikit-learn", "sklearn", "xgboost", "lightgbm", "nlp",
    "computer vision", "mlflow", "sagemaker",
    # Python Libraries
    "pandas", "numpy", "matplotlib", "seaborn", "plotly", "scipy",
    # DevOps & Tools
    "docker", "kubernetes", "git", "github", "gitlab", "linux", "unix",
    # Concepts
    "statistics", "regression", "etl", "bi", "a/b testing", "ab testing",
    "data modeling", "data warehousing",
}

# Special capitalization for specific skills
DISPLAY_NAMES = {
    "power bi":    "Power BI",
    "powerbi":     "Power BI",
    "aws":         "AWS",
    "gcp":         "GCP",
    "sql":         "SQL",
    "r":           "R",
    "etl":         "ETL",
    "bi":          "BI",
    "nlp":         "NLP",
    "a/b testing": "A/B Testing",
    "ab testing":  "A/B Testing",
    "scikit-learn":"scikit-learn",
    "sklearn":     "scikit-learn",
    "sas":         "SAS",
    "spss":        "SPSS",
}


CREATE_TABLES_SQL = """
DROP TABLE IF EXISTS job_skills;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS jobs;

CREATE TABLE jobs (
    id               SERIAL PRIMARY KEY,
    job_title        VARCHAR(200),
    company          VARCHAR(200),
    city             VARCHAR(100),
    experience_level VARCHAR(20),
    employment_type  VARCHAR(30),
    salary_usd       NUMERIC(12, 2),
    raw_skills       TEXT
);

CREATE TABLE skills (
    id         SERIAL PRIMARY KEY,
    skill_name VARCHAR(80) UNIQUE NOT NULL
);

CREATE TABLE job_skills (
    job_id   INTEGER REFERENCES jobs(id)   ON DELETE CASCADE,
    skill_id INTEGER REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);
"""


def get_conn():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"postgres connection failed: {e}")
        print("check DB_CONFIG credentials at the top of this file.")
        sys.exit(1)


def parse_skills(val):
    """
    description_tokens is stored as a Python list string:
      ['python', 'sql', 'excel', 'communication', 'detail-oriented']

    We parse the list and keep only tokens that are in KNOWN_SKILLS,
    so the resulting skills column contains only tech/data skills.
    """
    if not val or str(val).strip() in ("", "nan", "None", "[]"):
        return ""
    try:
        tokens = ast.literal_eval(str(val))
    except (ValueError, SyntaxError):
        return ""

    if not isinstance(tokens, list):
        return ""

    seen = set()
    result = []
    for token in tokens:
        t = str(token).lower().strip()
        # normalize sklearn → scikit-learn before deduplication
        canonical = "scikit-learn" if t == "sklearn" else t
        if canonical in KNOWN_SKILLS and canonical not in seen:
            seen.add(canonical)
            result.append(DISPLAY_NAMES.get(canonical, canonical.title()))

    return ", ".join(result)


def extract_experience(title):
    """infers Junior / Mid / Senior / Lead from the job title"""
    t = str(title).lower()
    if any(k in t for k in ["lead", "head", "director", "principal", "staff", "vp"]):
        return "Lead"
    if any(k in t for k in ["senior", " sr ", "sr.", "sr-", "level iii", "level 3"]):
        return "Senior"
    if any(k in t for k in ["junior", "jr.", "entry", "associate", "intern", "level i ", "level 1"]):
        return "Junior"
    return "Mid"


def extract_city(location):
    """'Austin, TX, United States' → 'Austin' | 'Anywhere' → 'Remote'"""
    loc = str(location).strip()
    if not loc or loc.lower() in ("anywhere", "nan", "remote", ""):
        return "Remote"
    city = loc.split(",")[0].strip()
    return city if city and city.lower() not in ("nan", "") else "Unknown"


def normalize_schedule(val):
    s = str(val).lower()
    if "full" in s:  return "Full-time"
    if "part" in s:  return "Part-time"
    if any(k in s for k in ["contract", "freelance", "temp", "contractor"]):
        return "Contract"
    return "Full-time"


def parse_salary(val):
    """returns float or None — salary_standardized is yearly USD"""
    try:
        f = float(val)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def load_csv():
    if not os.path.exists(CSV_FILE):
        print(f"file not found: {CSV_FILE}")
        print("make sure gsearch_jobs.csv is inside the raw_data/ folder.")
        sys.exit(1)
    rows = []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"read {len(rows):,} rows from {CSV_FILE}")
    return rows


def insert_jobs(cur, rows):
    data    = []
    skipped = 0

    for r in rows:
        skills = parse_skills(r.get("description_tokens", ""))
        if not skills:
            skipped += 1
            continue
        data.append((
            r.get("title",        "Unknown")[:200].strip(),
            r.get("company_name", "Unknown")[:200].strip(),
            extract_city(r.get("location",   "")),
            extract_experience(r.get("title", "")),
            normalize_schedule(r.get("schedule_type", "")),
            parse_salary(r.get("salary_standardized")),
            skills,
        ))

    if skipped > 0:
        print(f"skipped {skipped:,} rows — no recognizable skills in description_tokens")

    execute_values(
        cur,
        """
        INSERT INTO jobs (job_title, company, city, experience_level,
                          employment_type, salary_usd, raw_skills)
        VALUES %s
        RETURNING id, raw_skills
        """,
        data,
        page_size=1000
    )
    result = cur.fetchall()
    print(f"inserted {len(result):,} job records")
    return result


def build_skill_index(cur, job_rows):
    all_skills = set()
    for _, raw in job_rows:
        for skill in raw.split(","):
            s = skill.strip()
            if s:
                all_skills.add(s)

    execute_values(
        cur,
        "INSERT INTO skills (skill_name) VALUES %s ON CONFLICT DO NOTHING",
        [(s,) for s in sorted(all_skills)]
    )
    cur.execute("SELECT skill_name, id FROM skills")
    skill_map = {name: sid for name, sid in cur.fetchall()}
    print(f"found {len(skill_map)} unique skills")
    return skill_map


def insert_job_skills(cur, job_rows, skill_map):
    pairs = []
    for job_id, raw_skills in job_rows:
        for skill in raw_skills.split(","):
            s = skill.strip()
            if s in skill_map:
                pairs.append((job_id, skill_map[s]))

    execute_values(
        cur,
        "INSERT INTO job_skills (job_id, skill_id) VALUES %s ON CONFLICT DO NOTHING",
        pairs,
        page_size=5000
    )
    print(f"inserted {len(pairs):,} job–skill links")


def main():
    print("connecting to postgres...")
    conn = get_conn()
    cur  = conn.cursor()

    print("creating tables...")
    cur.execute(CREATE_TABLES_SQL)
    conn.commit()

    rows = load_csv()

    print("inserting jobs...")
    job_rows = insert_jobs(cur, rows)

    if not job_rows:
        print("nothing was loaded — check that description_tokens has data in the CSV.")
        conn.close()
        sys.exit(1)

    print("building skill index...")
    skill_map = build_skill_index(cur, job_rows)

    print("linking jobs to skills...")
    insert_job_skills(cur, job_rows, skill_map)

    conn.commit()
    cur.close()
    conn.close()

    print("\nall done.  run analyze.py to see results.")


if __name__ == "__main__":
    main()
