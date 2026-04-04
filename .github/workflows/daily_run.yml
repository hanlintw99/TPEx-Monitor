name: Daily Update Database

on:
  schedule:
    - cron: '30 8 * * *' # 每天台灣時間 16:30
  workflow_dispatch: # 允許手動執行

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    
    steps:
    - name: Checkout Code
      uses: actions/checkout@v4  # 升級至 v4

    - name: Set up Python
      uses: actions/setup-python@v5 # 升級至 v5
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pandas requests xlrd openpyxl

    - name: Run Scraper
      run: python fetch_tpex.py

    - name: Commit and Push
      run: |
        git config --global user.name "GitHub Action"
        git config --global user.email "action@github.com"
        git add tpex_database.csv
        # 只有當檔案有變動時才 commit，避免無意義報錯
        git diff --quiet && git diff --staged --quiet || (git commit -m "Update TPEx data" && git push)
