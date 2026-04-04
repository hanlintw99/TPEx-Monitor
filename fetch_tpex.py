import os
import requests
import pandas as pd
from datetime import datetime, timedelta

# 設定檔案路徑
DB_FILE = "tpex_database.csv"

def fetch_data(date_str):
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(api_url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200 and b"404" not in res.content[:500] and b"<html" not in res.content[:500]:
            # 讀取 CSV (略過前 4 行標題)
            df = pd.read_csv(io.BytesIO(res.content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
            if len(df.columns) >= 4:
                df = df.iloc[:, :4]
                df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').strip()
                df = df[df['標的證券代號'].str.isnumeric()]
                df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                df = df.dropna(subset=['名目本金', '成交筆數'])
                df['日期'] = date_str
                return df
    except:
        pass
    return None

# 讀取現有資料庫
if os.path.exists(DB_FILE):
    db_df = pd.read_csv(DB_FILE)
else:
    db_df = pd.DataFrame()

# 抓取最近 3 天 (補破網機制)
import io
today = datetime.now()
for i in range(3):
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    new_df = fetch_data(d_str)
    if new_df is not None:
        db_df = pd.concat([db_df, new_df]).drop_duplicates(subset=['日期', '標的證券代號'])

# 存回資料庫
db_df.to_csv(DB_FILE, index=False)
print(f"資料庫更新完成，目前共有 {len(db_df)} 筆紀錄。")
