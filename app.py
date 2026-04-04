import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
import os
import csv
import urllib3

# 1. 禁用 SSL 警告 (針對特定網路環境)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 建立本地快取資料夾 ---
DATA_DIR = "TPEx_Data"
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="可轉債監控儀表板", page_icon="📈", layout="wide")

st.title("📈 可轉債大額交易 - 終極雲端網頁版")
st.markdown("當前狀態：**強制安全連線模式已啟動**（解決部分環境無法連線櫃買中心的問題）")

# ==========================================
# 核心引擎：增加 verify=False 與 二進位處理
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_and_parse_data(date_obj):
    date_str = date_obj.strftime('%Y%m%d')
    file_path = os.path.join(DATA_DIR, f"data_{date_str}.csv")
    
    content_text = ""
    
    # 檢查快取
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content_text = f.read()
    else:
        # 網路抓取：加入 verify=False 跳過憑證檢查
        api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        
        try:
            # 💡 關鍵點：verify=False 解決 SSL 問題
            res = requests.get(api_url, headers=headers, timeout=15, verify=False)
            
            if res.status_code == 200:
                # 偵測是否為 404 網頁
                raw_text = res.content.decode('utf-8', errors='ignore')
                if "404" not in raw_text and "<html" not in raw_text:
                    content_text = raw_text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content_text)
        except Exception as e:
            st.error(f"連線失敗 ({date_str}): {str(e)}")
            return pd.DataFrame()
            
    if not content_text:
        return pd.DataFrame()
        
    # 解析 CSV
    f_io = io.StringIO(content_text)
    reader = csv.reader(f_io)
    valid_data = []
    
    for row in reader:
        if not row or len(row) < 4: continue
        
        # 清理代碼 (處理 ="15142" 這種格式)
        code = row[0].replace('=', '').replace('"', '').strip()
        
        if code.isdigit():
            name = row[1].replace('=', '').replace('"', '').strip()
            # 處理金額與筆數中的逗號
            p_str = row[2].replace(',', '').replace('"', '').strip()
            c_str = row[3].replace(',', '').replace('"', '').strip()
            
            valid_data.append([date_str, code, name, p_str, c_str])
            
    if valid_data:
        df = pd.DataFrame(valid_data, columns=['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數'])
        df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
        df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
        df = df.dropna(subset=['名目本金', '成交筆數'])
        df = df[df['成交筆數'] > 0]
        df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
        return df
        
    return pd.DataFrame()

# ==========================================
# 介面設計
# ==========================================
with st.sidebar:
    st.header("⚙️ 篩選設定")
    start_d = st.date_input("起始日期", datetime(2026, 4, 1)) # 預設設定在您有資料的那天
    end_d = st.date_input("結束日期", datetime(2026, 4, 1))
    threshold = st.slider("篩選門檻 (十萬)", 0, 200, 50)
    run_btn = st.button("🔍 執行篩選", use_container_width=True, type="primary")

# ==========================================
# 執行邏輯
# ==========================================
if run_btn:
    all_results = []
    
    # 計算日期區間
    date_range = []
    curr = start_d
    while curr <= end_d:
        date_range.append(curr)
        curr += timedelta(days=1)
        
    progress_text = st.empty()
    bar = st.progress(0)
    
    for i, d in enumerate(date_range):
        progress_text.text(f"正在檢查: {d.strftime('%Y-%m-%d')} ...")
        day_df = fetch_and_parse_data(d)
        if not day_df.empty:
            all_results.append(day_df)
        bar.progress((i + 1) / len(date_range))
        
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        # 過濾門檻
        output_df = final_df[final_df['單筆平均規模(十萬)'] > threshold].copy()
        
        if not output_df.empty:
            st.success(f"✅ 找到 {len(output_df)} 筆達標資料！")
            st.dataframe(output_df.sort_values('日期', ascending=False), use_container_width=True)
            
            # Excel 下載
            towrite = io.BytesIO()
            output_df.to_excel(towrite, index=False, engine='openpyxl')
            st.download_button(
                label="📥 下載 Excel 檔案",
                data=towrite.getvalue(),
                file_name=f"CB_Report_{datetime.now().strftime('%m%d_%H%M')}.xlsx",
                mime="application/vnd.ms-excel"
            )
        else:
            st.warning("⚠️ 此區間有交易資料，但沒有任何一筆符合門檻。請嘗試調低門檻。")
    else:
        st.error("❌ 所選期間完全抓不到櫃買中心資料。請檢查：\n1. 網路是否斷線\n2. 是否選到假日\n3. 嘗試在側邊欄選取 2026-04-01 測試。")
