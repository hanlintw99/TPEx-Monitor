import os
import requests
import pandas as pd
import io
from datetime import datetime, timedelta

# 設定資料庫檔案路徑
DB_FILE = "tpex_database.csv"

def fetch_data(date_str):
    # 櫃買中心 API 網址
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    
    # 模擬更真實的瀏覽器行為
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no143/otc_quotes_no143.php'
    }

    try:
        # 增加 timeout 並禁用 SSL 驗證以防萬一
        response = requests.get(api_url, headers=headers, timeout=20, verify=False)
        
        if response.status_code == 200:
            content = response.content
            # 檢查是否為 404 或 HTML 錯誤頁面
            if b"404" in content[:500] or b"<html" in content[:500]:
                print(f"⏩ {date_str}：櫃買中心無資料或阻擋請求。")
                return None
            
            # 使用二進位讀取，處理編碼問題
            try:
                # 櫃買中心資料通常前 4 行是標題備註，我們從第 5 行開始抓資料
                df = pd.read_csv(io.BytesIO(content), skiprows=4, header=None, on_bad_lines='skip', engine='python')
                
                if len(df.columns) >= 4:
                    # 只取前四欄：代號、名稱、名目本金、成交筆數
                    df = df.iloc[:, :4]
                    df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數']
                    
                    # 清理代號欄位 (處理 ="15142" 格式)
                    df['標的證券代號'] = df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                    
                    # 篩選掉非數字的行（如合計列）
                    df = df[df['標的證券代號'].str.isnumeric()]
                    
                    # 轉換數值並清理逗號
                    df['名目本金'] = pd.to_numeric(df['名目本金'].astype(str).str.replace(',', ''), errors='coerce')
                    df['成交筆數'] = pd.to_numeric(df['成交筆數'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    df = df.dropna(subset=['名目本金', '成交筆數'])
                    df = df[df['成交筆數'] > 0]
                    df['日期'] = date_str
                    
                    print(f"✅ {date_str}：成功解析 {len(df)} 筆資料。")
                    return df
            except Exception as parse_e:
                print(f"❌ {date_str}：解析 CSV 失敗 - {parse_e}")
        else:
            print(f"❌ {date_str}：連線失敗，Status Code: {response.status_code}")
    except Exception as e:
        print(f"❌ {date_str}：網路連線異常 - {e}")
    
    return None

# --- 主程式邏輯 ---

# 1. 讀取現有資料庫
if os.path.exists(DB_FILE):
    db_df = pd.read_csv(DB_FILE)
    db_df['日期'] = db_df['日期'].astype(str)
else:
    db_df = pd.DataFrame()

# 2. 抓取最近 5 天 (確保不漏掉周末後的更新)
today = datetime.now()
new_data_list = []

for i in range(5):
    target_date = (today - timedelta(days=i)).strftime('%Y%m%d')
    # 檢查是否已經抓過這天了
    if not db_df.empty and target_date in db_df['日期'].values:
        continue
        
    day_df = fetch_data(target_date)
    if day_df is not None:
        new_data_list.append(day_df)

# 3. 合併並存檔
if new_data_list:
    combined_df = pd.concat([db_df] + new_data_list, ignore_index=True)
    # 確保不會有重複行 (以日期+代號為準)
    combined_df = combined_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    # 依照日期排序
    combined_df = combined_df.sort_values('日期', ascending=False)
    combined_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 資料庫更新成功！目前共儲存 {len(combined_df)} 筆紀錄。")
else:
    print("ℹ️ 本次檢查無新資料需要存檔。")
