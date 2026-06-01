-- Skill Demand Intelligence Tracker — SQL Queries
-- Run in psql:  psql -d skill_tracker
-- Or paste into pgAdmin4 Query Tool
-- Or run the whole file:  \i queries.sql


-- ──────────────────────────────────────────────────────────────────────────────
-- 1. Top 15 most in-demand skills across all postings
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    s.skill_name                                  AS skill,
    COUNT(*)                                      AS job_count,
    ROUND(AVG(j.salary_usd)::numeric, 0)          AS avg_salary_usd,
    COUNT(j.salary_usd)                           AS listings_with_salary
FROM job_skills js
JOIN skills s ON js.skill_id = s.id
JOIN jobs   j ON js.job_id   = j.id
GROUP BY s.skill_name
ORDER BY job_count DESC
LIMIT 15;


-- ──────────────────────────────────────────────────────────────────────────────
-- 2. Skill pairs that co-occur most in the same posting
--    (js1.skill_id < js2.skill_id avoids counting each pair twice)
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    s1.skill_name                                 AS skill_1,
    s2.skill_name                                 AS skill_2,
    COUNT(*)                                      AS jobs_with_both,
    ROUND(AVG(j.salary_usd)::numeric, 0)          AS avg_salary_usd
FROM job_skills js1
JOIN job_skills js2 ON js1.job_id = js2.job_id
                   AND js1.skill_id < js2.skill_id
JOIN skills s1 ON js1.skill_id = s1.id
JOIN skills s2 ON js2.skill_id = s2.id
JOIN jobs   j  ON js1.job_id   = j.id
GROUP BY s1.skill_name, s2.skill_name
HAVING COUNT(*) >= 10
ORDER BY jobs_with_both DESC
LIMIT 20;


-- ──────────────────────────────────────────────────────────────────────────────
-- 3. Same pairs — sorted by avg salary instead (which combos pay more?)
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    s1.skill_name                                 AS skill_1,
    s2.skill_name                                 AS skill_2,
    COUNT(*)                                      AS jobs_with_both,
    ROUND(AVG(j.salary_usd)::numeric, 0)          AS avg_salary_usd
FROM job_skills js1
JOIN job_skills js2 ON js1.job_id = js2.job_id
                   AND js1.skill_id < js2.skill_id
JOIN skills s1 ON js1.skill_id = s1.id
JOIN skills s2 ON js2.skill_id = s2.id
JOIN jobs   j  ON js1.job_id   = j.id
WHERE j.salary_usd IS NOT NULL
GROUP BY s1.skill_name, s2.skill_name
HAVING COUNT(*) >= 8
ORDER BY avg_salary_usd DESC
LIMIT 15;


-- ──────────────────────────────────────────────────────────────────────────────
-- 4. City-wise top 5 skills using a window function (ROW_NUMBER + PARTITION BY)
-- ──────────────────────────────────────────────────────────────────────────────

WITH ranked AS (
    SELECT
        j.city,
        s.skill_name,
        COUNT(*)                                  AS job_count,
        ROUND(AVG(j.salary_usd)::numeric, 0)      AS avg_salary_usd,
        ROW_NUMBER() OVER (
            PARTITION BY j.city ORDER BY COUNT(*) DESC
        ) AS rn
    FROM job_skills js
    JOIN jobs   j ON js.job_id   = j.id
    JOIN skills s ON js.skill_id = s.id
    GROUP BY j.city, s.skill_name
)
SELECT city, skill_name, job_count, avg_salary_usd
FROM ranked
WHERE rn <= 5
ORDER BY city, rn;


-- ──────────────────────────────────────────────────────────────────────────────
-- 5. Salary distribution by experience level and employment type
-- ──────────────────────────────────────────────────────────────────────────────

SELECT
    experience_level,
    employment_type,
    COUNT(*)                                                   AS job_count,
    ROUND(AVG(salary_usd)::numeric, 0)                        AS avg_salary_usd,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_usd)::numeric, 0
    )                                                          AS median_salary_usd
FROM jobs
WHERE salary_usd IS NOT NULL
GROUP BY experience_level, employment_type
ORDER BY
    CASE experience_level
        WHEN 'Junior' THEN 1 WHEN 'Mid'    THEN 2
        WHEN 'Senior' THEN 3 WHEN 'Lead'   THEN 4
    END,
    employment_type;


-- ──────────────────────────────────────────────────────────────────────────────
-- 6. Bonus — highest-paying role in each city
-- ──────────────────────────────────────────────────────────────────────────────

SELECT DISTINCT ON (city)
    city,
    job_title,
    ROUND(AVG(salary_usd)::numeric, 0) AS avg_salary_usd,
    COUNT(*)                           AS job_count
FROM jobs
WHERE salary_usd IS NOT NULL
GROUP BY city, job_title
ORDER BY city, avg_salary_usd DESC;
