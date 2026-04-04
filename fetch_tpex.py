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
    # 櫃買中心成交簡表 API
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=20, verify=False)
        if response.status_code == 200:
            content = response.content
            if b"404" in content[:500] or b"<html" in content[:500] or len(content) < 100:
                return None
            
            # 櫃買 CSV 格式：第 5 行開始是資料
            # 欄位順序通常是：代號, 名稱, 名目本金, 成交筆數, 權利金, 最高, 最低, 收盤價...
            try:
                df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
                
                if len(df.columns) >= 8:
                    # 擷取關鍵欄位：0:代號, 1:名稱, 2:名目本金, 3:成交筆數, 7:收盤價
                    df = df.iloc[:, [0, 1, 2, 3, 7]]
                    df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '當日收盤價']
                    
                    # 清理代號
                    df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                    df = df[df['標的證券代號'].str.isnumeric()]
                    
                    # 數值轉換
                    df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                    df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                    df['當日收盤價'] = pd.to_numeric(df['當日收盤價'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    df = df.dropna(subset=['名目本金', '成交筆數'])
                    df = df[df['成交筆數'] > 0]
                    df['日期'] = date_str
                    
                    print(f"✅ {date_str}：抓取成功，包含收盤價。")
                    return df
            except Exception as e:
                print(f"❌ {date_str} 解析失敗: {e}")
    except Exception as e:
        print(f"❌ {date_str} 連線失敗: {e}")
    return None

# --- 主程式 ---
if os.path.exists(DB_FILE):
    db_df = pd.read_csv(DB_FILE)
    db_df['日期'] = db_df['日期'].astype(str)
else:
    db_df = pd.DataFrame()

today = datetime.now()
new_data_list = []

# 檢查最近 7 天
for i in range(7):
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    # 如果資料庫已存在該日資料且含有「當日收盤價」欄位，則跳過
    if not db_df.empty and '當日收盤價' in db_df.columns and d_str in db_df['日期'].values.tolist():
        continue
    
    day_df = fetch_data(d_str)
    if day_df is not None:
        new_data_list.append(day_df)

if new_data_list:
    combined_df = pd.concat([db_df] + new_data_list, ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    combined_df = combined_df.sort_values('日期', ascending=False)
    combined_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 資料庫已更新並儲存收盤價。")
else:
    print("ℹ️ 無新資料。")
