import os
import requests
import pandas as pd
import io
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = "tpex_database.csv"

def fetch_data(date_str):
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(api_url, headers=headers, timeout=20, verify=False)
        if response.status_code == 200:
            content = response.content
            if len(content) < 100 or b"html" in content[:500]: return None
            
            df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
            if len(df.columns) >= 4:
                df = df.iloc[:, :4]
                df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                df = df[df['標的證券代號'].str.isnumeric()]
                df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                df = df.dropna(subset=['名目本金', '成交筆數'])
                df.insert(0, '日期', date_str)
                return df
    except: pass
    return None

# --- 強制執行並列印狀態 ---
new_data_list = []
today = datetime.now()
print(f"🚀 開始執行抓取任務，今日日期: {today.strftime('%Y-%m-%d')}")

for i in range(14): # 抓14天確保一定有資料
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    day_df = fetch_data(d_str)
    if day_df is not None:
        print(f"✅ 成功抓取 {d_str}，資料筆數: {len(day_df)}")
        new_data_list.append(day_df)

if new_data_list:
    final_df = pd.concat(new_data_list, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    final_df = final_df.sort_values('日期', ascending=False)
    # 💡 檢查是否有資料才存檔
    final_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 成功寫入 {DB_FILE}，總筆數: {len(final_df)}")
else:
    print("❌ 錯誤：所有日期都沒有抓到資料，請檢查櫃買中心網址。")
    # 強制產生一個帶標題的空檔案，避免 Action 報錯
    pd.DataFrame(columns=['日期','標的證券代號','標的證券名稱','名目本金','成交筆數']).to_csv(DB_FILE, index=False)
