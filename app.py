import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
import os
import csv

# --- 建立本地快取資料夾 (硬碟快取) ---
DATA_DIR = "TPEx_Data"
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="可轉債大額交易篩選", page_icon="📈", layout="wide")

st.title("📈 可轉債選擇權端 - 大額交易動態篩選器")
st.markdown("⚡ **專業解析版**：採用 CSV 嚴格解析引擎，支援跨行標題與特殊編碼。")

# ==========================================
# 核心引擎：使用 csv 模組精準解析
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_and_parse_data(date_str):
    file_path = os.path.join(DATA_DIR, f"資產交換選擇權端_{date_str}.csv")
    content = ""
    
    # 1. 檢查硬碟是否有快取
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        # 2. 網路抓取
        api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200 and "404" not in res.text and "<html" not in res.text:
                # 轉為 utf-8 存檔
                content = res.text
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        except:
            pass
            
    if not content:
        return pd.DataFrame()
        
    # 3. 使用 csv.reader 解析 (重要：處理標題內的換行符號)
    f_io = io.StringIO(content)
    reader = csv.reader(f_io)
    valid_data = []
    
    for row in reader:
        if not row or len(row) < 4: continue
        
        # 清除 Excel 常見的 ="代碼" 格式與空白
        code = row[0].replace('=', '').replace('"', '').strip()
        
        # 關鍵：只要第一欄是純數字(代號)，就是我們要的資料行
        if code.isdigit():
            # 取得名稱、名目本金(row[2])、成交筆數(row[3])
            name = row[1].replace('=', '').replace('"', '').strip()
            principal = row[2].replace(',', '').strip()
            count = row[3].replace(',', '').strip()
            
            valid_data.append([date_str, code, name, principal, count])
            
    if valid_data:
        df = pd.DataFrame(valid_data, columns=['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數'])
        # 轉換數值型態
        df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
        df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
        df = df.dropna(subset=['名目本金', '成交筆數'])
        df = df[df['成交筆數'] > 0]
        
        # 計算結果
        df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
        return df
    return pd.DataFrame()

# ==========================================
# UI 介面
# ==========================================
col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("📅 起始日期", datetime.now() - timedelta(days=5))
with col2:
    end_date = st.date_input("📅 結束日期", datetime.now())
with col3:
    threshold = st.number_input("🎯 篩選門檻 (單筆平均規模 > X 十萬)", value=50.0, step=5.0)

st.markdown("---")

# ==========================================
# 按鈕與邏輯
# ==========================================
if st.button("🚀 開始抓取與篩選", type="primary"):
    if start_date > end_date:
        st.error("❌ 起始日期不能晚於結束日期喔！")
    else:
        with st.spinner("正在精準解析每一天資料..."):
            all_dfs = []
            delta = end_date - start_date
            dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
            
            p_bar = st.progress(0)
            for i, d in enumerate(dates):
                d_str = d.strftime('%Y%m%d')
                day_df = fetch_and_parse_data(d_str)
                if not day_df.empty:
                    all_dfs.append(day_df)
                p_bar.progress((i + 1) / len(dates))
            
            if all_dfs:
                full_df = pd.concat(all_dfs, ignore_index=True)
                # 動態篩選
                final_result = full_df[full_df['單筆平均規模(十萬)'] > threshold].copy()
                
                if not final_result.empty:
                    st.success(f"🎉 成功！在 {len(dates)} 天中找到 {len(final_result)} 筆達標資料。")
                    
                    # 調整欄位順序美化顯示
                    display_cols = ['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '單筆平均規模(十萬)']
                    st.dataframe(final_result[display_cols], use_container_width=True)
                    
                    # 下載按鈕
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        final_result[display_cols].to_excel(writer, index=False)
                    st.download_button(
                        label="📥 下載 Excel 報表",
                        data=output.getvalue(),
                        file_name=f"CB_Filter_{datetime.now().strftime('%H%M%S')}.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                else:
                    st.info(f"這幾天有資料，但沒有任何一項超過您的門檻 {threshold}。請試著調低門檻。")
            else:
                st.warning("⚠️ 所選期間櫃買中心無資料 (可能全是假日)。")
