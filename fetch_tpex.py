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
            if b"404" in content[:500] or b"<html" in content[:500] or len(content) < 100:
                return None
            
            try:
                df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
                
                # 確保欄位足夠抓取收盤價 (第 8 欄，索引 7)
                if len(df.columns) >= 8:
                    df = df.iloc[:, [0, 1, 2, 3, 7]]
                    df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '當日收盤價']
                    
                    df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                    df = df[df['標的證券代號'].str.isnumeric()]
                    
                    df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                    df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                    df['當日收盤價'] = pd.to_numeric(df['當日收盤價'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    df = df.dropna(subset=['名目本金', '成交筆數'])
                    df = df[df['成交筆數'] > 0]
                    df['日期'] = date_str
                    return df
            except:
                pass
    except:
        pass
    return None

# --- 主程式：修正覆蓋邏輯 ---
if os.path.exists(DB_FILE):
    try:
        db_df = pd.read_csv(DB_FILE)
        db_df['日期'] = db_df['日期'].astype(str)
        # 👇 關鍵修正：檢查現有資料庫是否有「當日收盤價」欄位
        has_close_col = '當日收盤價' in db_df.columns
    except:
        db_df = pd.DataFrame()
        has_close_col = False
else:
    db_df = pd.DataFrame()
    has_close_col = False

today = datetime.now()
new_data_list = []

# 檢查最近 100 天 (稍微拉長一點，確保把沒收盤價的舊資料洗掉)
for i in range(100):
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    
    # 💡 修改判斷條件：
    # 如果 (日期不在資料庫中) OR (資料庫缺少收盤價欄位)，就強制重新抓取
    if not db_df.empty and has_close_col and d_str in db_df['日期'].values.tolist():
        continue
    
    print(f"正在更新/重新抓取: {d_str}")
    day_df = fetch_data(d_str)
    if day_df is not None:
        new_data_list.append(day_df)

if new_data_list:
    # 如果原本沒有收盤價欄位，我們就以新抓到的資料為主，重新建立資料庫
    if not has_close_col:
        combined_df = pd.concat(new_data_list, ignore_index=True)
    else:
        combined_df = pd.concat([db_df] + new_data_list, ignore_index=True)
        
    combined_df = combined_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    combined_df = combined_df.sort_values('日期', ascending=False)
    combined_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 資料庫已強制更新。")
else:
    print("ℹ️ 資料已是最新且含有收盤價欄位。")
