import os
import requests
import pandas as pd
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

print("啟動【全雲端】最近 5 天可轉債大額交易監控程式...")
result_list = []
today = datetime.now()

for d in range(5):
    target_date = today - timedelta(days=d)
    date_str = target_date.strftime('%Y%m%d')
    print(f"正在檢查 {date_str} 的資料...")
    
    api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        # 攔截 404
        if response.status_code != 200 or b"404" in response.content[:500] or b"<html" in response.content[:500]:
            print(f"⏩ {date_str} 無資料")
            continue
            
        temp_file = f"temp_{date_str}.xls"
        with open(temp_file, 'wb') as f:
            f.write(response.content)
            
        try:
            # 雲端自動調用 xlrd 解析真實 Excel
            temp_df = pd.read_excel(temp_file, engine='xlrd')
            header_mask = temp_df.astype(str).apply(lambda x: x.str.contains('代號|Code')).any(axis=1)
            
            if header_mask.any():
                header_idx = header_mask.idxmax()
                df = temp_df.iloc[header_idx+1:].reset_index(drop=True)
                df = df.iloc[:, :8]
                df.columns = ['標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '最低', '最高', '平均', '契約期間']
                
                df = df[df['標的證券代號'].astype(str).str.replace('=', '').str.replace('"', '').str.strip().str.isnumeric()]
                df['名目本金'] = df['名目本金'].astype(str).str.replace(',', '', regex=False)
                df['成交筆數'] = df['成交筆數'].astype(str).str.replace(',', '', regex=False)
                df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
                df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
                df = df.dropna(subset=['名目本金', '成交筆數'])
                df = df[df['成交筆數'] > 0]
                
                # 計算與篩選
                df['計算結果'] = df['名目本金'] / df['成交筆數'] / 100000
                filtered_df = df[df['計算結果'] > 50].copy()
                
                if not filtered_df.empty:
                    filtered_df['日期'] = date_str
                    filtered_df = filtered_df.rename(columns={'計算結果': '單筆平均規模(十萬)'})
                    final_cols = ['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '單筆平均規模(十萬)']
                    result_list.append(filtered_df[final_cols])
                    print(f"✅ {date_str} 找到 {len(filtered_df)} 筆達標標的！")
        except Exception as e:
            print(f"⚠️ {date_str} 解析失敗: {e}")
            
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    except Exception as e:
        print(f"⚠️ {date_str} 網路請求失敗: {e}")

output_filename = "篩選結果_大額交易標的.xlsx"
if result_list:
    final_result = pd.concat(result_list, ignore_index=True)
    final_result.to_excel(output_filename, index=False)
    print("🎉 處理完成！檔案已生成。")
else:
    pd.DataFrame(columns=['最近 5 天沒有符合條件的資料']).to_excel(output_filename, index=False)
    print("最近 5 天沒有符合條件的資料。")
