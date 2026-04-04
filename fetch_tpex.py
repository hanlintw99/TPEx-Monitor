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
            content = response.content.decode('utf-8', errors='ignore')
            if "404" in content[:500] or "<html" in content[:500]:
                return None
            
            # 💡 改用 StringIO 配合全部讀取，不先 skiprows
            f_io = io.StringIO(content)
            all_rows = pd.read_csv(f_io, header=None, on_bad_lines='skip', engine='python')
            
            # 1. 尋找「標題列」在哪裡 (搜尋包含 "代號" 或 "Code" 的那一行)
            header_idx = -1
            for idx, row in all_rows.iterrows():
                row_str = "".join(row.astype(str))
                if "代號" in row_str or "Code" in row_str:
                    header_idx = idx
                    break
            
            if header_idx == -1: return None
            
            # 2. 重新設定 DataFrame 標題
            df = all_rows.iloc[header_idx+1:].copy()
            df.columns = [c.replace('\n', '').strip() for c in all_rows.iloc[header_idx].astype(str)]
            
            # 3. 💡 動態尋找目標欄位名稱 (不論它在第幾欄)
            col_map = {
                '標的證券代號': ['代號', 'Code'],
                '標的證券名稱': ['名稱', 'Name'],
                '名目本金': ['名目本金', 'Notional'],
                '成交筆數': ['成交筆數', 'Transactions'],
                '當日收盤價': ['收盤', 'Average', '平均'] # 櫃買日報通常叫「平均」或「收盤」
            }
            
            final_cols = {}
            for target, keywords in col_map.items():
                for col in df.columns:
                    if any(key in col for key in keywords):
                        final_cols[target] = col
                        break
            
            # 4. 擷取並清洗
            if len(final_cols) >= 4:
                selected_df = df[list(final_cols.values())].copy()
                selected_df.columns = list(final_cols.keys())
                
                # 清理代號
                selected_df['標的證券代號'] = selected_df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip()
                selected_df = selected_df[selected_df['標的證券代號'].str.isnumeric()]
                
                # 轉數值
                for c in ['名目本金', '成交筆數', '當日收盤價']:
                    if c in selected_df.columns:
                        selected_df[c] = pd.to_numeric(selected_df[c].astype(str).str.replace(',', ''), errors='coerce')
                
                selected_df = selected_df.dropna(subset=['名目本金', '成交筆數'])
                selected_df['日期'] = date_str
                print(f"✅ {date_str} 解析成功，抓到欄位: {list(final_cols.keys())}")
                return selected_df
    except Exception as e:
        print(f"Error: {e}")
    return None

# --- 主程式 ---
new_data_list = []
today = datetime.now()

# 強制抓取最近 10 天
for i in range(10):
    d_str = (today - timedelta(days=i)).strftime('%Y%m%d')
    day_df = fetch_data(d_str)
    if day_df is not None:
        new_data_list.append(day_df)

if new_data_list:
    final_df = pd.concat(new_data_list, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['日期', '標的證券代號'], keep='last')
    final_df = final_df.sort_values('日期', ascending=False)
    final_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    print(f"🎉 資料庫更新完成。")
