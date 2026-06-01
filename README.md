# Skill_demand
analysis W.R.T to skill sets and their worth in current market  
skill_tracker/             ← Project 2: Skill Demand Intelligence Tracker  
├── requirements.txt       – Python libraries to install  
├── fetch_data.py          – downloads Kaggle dataset, writes job_postings.csv  
├── load_to_postgres.py    – creates PostgreSQL tables, loads job_postings.csv  
├── analyze.py             – runs 5 SQL analyses, saves skill_analysis.xlsx  
├── queries.sql            – standalone SQL queries (run directly in psql or pgAdmin)  
└── README.md              – setup guide  


How to run
1. python fetch_data.py
2. python load_to_postgres.py
3. python analyze.py
