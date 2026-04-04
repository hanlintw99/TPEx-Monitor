import os
import requests
import pandas as pd
import io
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = "tpex_database.csv"

def fetch_data(date_str):
    # 💡 2026 最新櫃買中心 CSV 資料下載網址格式
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Referer': 'https://www.tpex.org.tw/'
    }

    try:
        # 增加 timeout 確保不會因為伺服器慢而斷線
        response = requests.get(api_url, headers=headers, timeout=30, verify=False)
        
        if response.status_code == 200:
            content = response.content
            # 如果回傳的是 HTML (通常是錯誤頁面) 或長度太短，代表當天沒開盤
            if b"<html" in content[:500] or len(content) < 500:
                print(f"⏩ {date_str}: 非交易日或無資料。")
                return None
            
            # 讀取 CSV
            df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
            
            if len(df.columns) >= 4:
                df = df.iloc[:, :4]
                df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                
                # 清理代號格式
                df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                # 過濾非數字列
                df = df[df['標的證券代號'].str.isnumeric()]
                
                # 轉數值
                df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                
                df = df.dropna(subset=['名目本金', '成交筆數'])
                df = df[df['成交筆數'] > 0]
                
                # 插入日期在第一欄
                df.insert(0, '日期', date_str)
                return df
    except Exception as e:
        print(f"⚠️ {date_str} 連線異常: {e}")
    return None

# --- 主執行區 ---
new_data_list = []
today = datetime.now()
print(f"🚀 啟動 2026 雲端抓取任務 | 今日: {today.strftime('%Y-%m-%d')}")

# 回溯抓取過去 20 天 (涵蓋整個長假)
for i in range(20):
    target_date = (today - timedelta(days=i)).strftime('%Y%m%d')
    day_df = fetch_data(target_date)
    if day_df is not None:
        print(f"✅ 成功獲取 {target_date} 資料，筆數: {len(day_df)}")
        new_data_list.append(day_df)

if new_data_list:
    final_df = pd.concat(new_data_list, ignore_index=True)
    # 以日期+代號去重
    final_df = final_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    final_df = final_df.sort_values('日期', ascending=False)
    
    # 強制寫入檔案
    final_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 任務完成！已更新 {DB_FILE}，目前存檔總筆數: {len(final_df)}")
else:
    print("❌ 警報：過去 20 天均無資料。請檢查櫃買中心 API 網址是否變更。")
    # 如果沒資料，為了不讓之後的網頁當掉，產生一個帶標題的空 CSV
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=['日期','標的證券代號','標的證券名稱','名目本金','成交筆數']).to_csv(DB_FILE, index=False)
