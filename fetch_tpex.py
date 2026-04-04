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
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=30, verify=False)
        
        if response.status_code == 200:
            content = response.content
            if len(content) < 500 or b"<html" in content[:500]:
                print(f"⏩ {date_str}: 非交易日或無資料。")
                return None
            
            # 💡 關鍵修正：嘗試用 xlrd (Excel) 讀取，如果失敗再嘗試 CSV
            try:
                # 櫃買中心很多檔案其實是二進位 Excel
                df = pd.read_excel(io.BytesIO(content), engine='xlrd')
            except Exception:
                try:
                    # 嘗試用 CSV 讀取 (處理可能的編碼問題)
                    df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
                except Exception:
                    return None
            
            # 統一清理資料邏輯 (不管是 Excel 還是 CSV 讀進來)
            if df is not None and len(df.columns) >= 4:
                # 找出含有代號的那一行，通常是第一個欄位是數字的開始
                df.columns = [f"col_{i}" for i in range(len(df.columns))]
                
                # 清理代號：去掉 ="1234" 這種 Excel 格式
                df['col_0'] = df['col_0'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                
                # 篩選出代號是數字的行
                mask = df['col_0'].str.isnumeric()
                df = df[mask].copy()
                
                if not df.empty:
                    df = df.iloc[:, :4]
                    df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                    
                    # 轉數值
                    df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                    df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    df = df.dropna(subset=['名目本金', '成交筆數'])
                    df.insert(0, '日期', date_str)
                    return df
    except Exception as e:
        print(f"⚠️ {date_str} 發生錯誤: {e}")
    return None

# --- 主執行區 ---
new_data_list = []
today = datetime.now()
print(f"🚀 啟動 2026 支援 Excel 格式抓取 | 今日: {today.strftime('%Y-%m-%d')}")

for i in range(20):
    target_date = (today - timedelta(days=i)).strftime('%Y%m%d')
    day_df = fetch_data(target_date)
    if day_df is not None:
        print(f"✅ 成功解析 {target_date} 資料，筆數: {len(day_df)}")
        new_data_list.append(day_df)

if new_data_list:
    final_df = pd.concat(new_data_list, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    final_df = final_df.sort_values('日期', ascending=False)
    final_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 任務完成！已更新 {DB_FILE}")
else:
    print("❌ 依然無法解析任何資料。")
