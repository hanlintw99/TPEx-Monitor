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
            
            # 跳過前 4 行標題，抓取前 4 欄
            df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
            
            if len(df.columns) >= 4:
                df = df.iloc[:, :4]
                df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                
                # 清理代號格式
                df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                df = df[df['標的證券代號'].str.isnumeric()]
                
                # 轉數值
                df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                
                df = df.dropna(subset=['名目本金', '成交筆數'])
                df = df[df['成交筆數'] > 0]
                
                # 💡 將日期放在第一欄
                df.insert(0, '日期', date_str)
                return df
    except:
        pass
    return None

# --- 主程式：合併並存檔 ---
new_data_list = []
today = datetime.now()

# 抓取最近 10 天確保資料完整
for i in range(10):
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    day_df = fetch_data(d_str)
    if day_df is not None:
        new_data_list.append(day_df)

if new_data_list:
    final_df = pd.concat(new_data_list, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    final_df = final_df.sort_values('日期', ascending=False)
    
    # 存檔
    final_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"✅ 資料庫已重新生成，日期已置於第一欄。")
