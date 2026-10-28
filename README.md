# Gender and Radiation Discourse on Xiaohongshu

Analysis code for the manuscript “Hearing Her Concerns: Gender and Radiation Discourse Among Cardiovascular Interventionists in China: Social Media Analysis.”

## Scripts

- `final_stats.py`: descriptive statistics and gender-by-valence analyses.
- `article_analysis.py`: theme-by-gender counts and chi-square comparisons.
- `reviewer_analyses.py`: author-level, radiation-subset, and recode-agreement analyses.
- `commenter_gender_analysis.py`: commenter-gender cross-tabulation.

## Run

Use Python 3.10 or later. Place the de-identified input files under `corpus/` and run the scripts from the project root:

```bash
python scripts/final_stats.py
python scripts/article_analysis.py
python scripts/reviewer_analyses.py
python scripts/commenter_gender_analysis.py
```

Post-, comment-, and profile-level data are not included.
