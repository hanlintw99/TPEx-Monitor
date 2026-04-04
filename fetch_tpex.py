import os
import requests
import pandas as pd
import io
from datetime import datetime, timedelta
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = "tpex_database.csv"

def fetch_data(date_str):
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=20, verify=False)
        if response.status_code == 200:
            content = response.content
            if b"404" in content[:500] or b"<html" in content[:500] or len(content) < 100:
                print(f"⏩ {date_str}：查無資料。")
                return None
            
            # 嘗試兩種讀取方式：先嘗試當作真實 Excel，失敗再當作 CSV
            try:
                # 策略 A: 真實 Excel (.xls)
                df = pd.read_excel(io.BytesIO(content), engine='xlrd')
            except:
                try:
                    # 策略 B: CSV 格式
                    df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
                except:
                    return None

            # 資料清洗邏輯
            if df is not None and len(df.columns) >= 4:
                # 找出含有「代號」或「Code」的那一行或是直接找第一列數字
                # 為了穩定，我們尋找第一欄是數字的行
                df.columns = [f'col_{i}' for i in range(len(df.columns))]
                
                # 清理代號欄位
                df['col_0'] = df['col_0'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                mask = df['col_0'].str.isnumeric()
                df = df[mask].copy()
                
                if not df.empty:
                    df = df.iloc[:, :4]
                    df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                    df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                    df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                    df = df.dropna(subset=['名目本金', '成交筆數'])
                    df['日期'] = date_str
                    print(f"✅ {date_str}：解析成功。")
                    return df
    except Exception as e:
        print(f"❌ {date_str}：連線或解析異常 - {e}")
    return None

# --- 主程式 ---
if os.path.exists(DB_FILE):
    try:
        db_df = pd.read_csv(DB_FILE)
        db_df['日期'] = db_df['日期'].astype(str)
    except:
        db_df = pd.DataFrame()
else:
    db_df = pd.DataFrame()

today = datetime.now()
new_data_list = []

# 檢查最近 7 天，確保周末也不漏掉
for i in range(7):
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    if not db_df.empty and d_str in db_df['日期'].values.tolist():
        continue
    
    day_df = fetch_data(d_str)
    if day_df is not None:
        new_data_list.append(day_df)

if new_data_list:
    combined_df = pd.concat([db_df] + new_data_list, ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    combined_df = combined_df.sort_values('日期', ascending=False)
    combined_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 資料庫已更新，總筆數：{len(combined_df)}")
else:
    print("ℹ️ 無新資料。")
