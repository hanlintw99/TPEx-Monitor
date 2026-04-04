import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
import os

# --- 建立本地快取資料夾 (硬碟快取) ---
DATA_DIR = "TPEx_Data"
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="可轉債大額交易篩選", page_icon="📈", layout="wide")

st.title("📈 可轉債選擇權端 - 大額交易動態篩選器")
st.markdown("⚡ **極速體驗**：內建記憶體與硬碟雙重快取。只要抓取過一次，後續更改條件完全「秒速」顯示！")

# ==========================================
# 核心引擎：獨立的資料獲取函數 + Streamlit 記憶體快取
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_and_parse_data(date_str):
    """這個函數只要執行過一次，結果就會被保存在記憶體中"""
    file_path = os.path.join(DATA_DIR, f"資產交換選擇權端_{date_str}.csv")
    file_content_text = ""
    
    # 1. 檢查硬碟快取
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content_text = f.read()
    else:
        # 2. 網路抓取
        api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200 and "404" not in res.text and "<html" not in res.text:
                file_content_text = res.text
                # 下載成功後存入硬碟
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(file_content_text)
        except Exception:
            pass
            
    # 3. 解析並回傳 DataFrame (不包含動態篩選條件)
    if not file_content_text:
        return pd.DataFrame()
        
    valid_data = []
    for line in file_content_text.split('\n'):
        line = line.strip()
        if not line: continue
        sep = '\t' if '\t' in line else ','
        parts = [p.replace('"', '').replace('=', '').strip() for p in line.split(sep)]
        if len(parts) >= 8 and parts[0].isdigit():
            valid_data.append(parts[:8])
            
    if valid_data:
        df = pd.DataFrame(valid_data, columns=['標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '最低', '最高', '平均', '契約期間'])
        df['名目本金'] = df['名目本金'].astype(str).str.replace(',', '', regex=False)
        df['成交筆數'] = df['成交筆數'].astype(str).str.replace(',', '', regex=False)
        df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
        df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
        df = df.dropna(subset=['名目本金', '成交筆數'])
        df = df[df['成交筆數'] > 0]
        
        # 預先算好數值，並加上日期
        df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
        df['日期'] = date_str
        return df
    else:
        return pd.DataFrame()

# ==========================================
# UI 介面設定
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
# 執行按鈕邏輯
# ==========================================
if st.button("🚀 開始抓取與篩選", type="primary"):
    if start_date > end_date:
        st.error("❌ 起始日期不能晚於結束日期喔！")
    else:
        with st.spinner("正在處理資料（只要抓過一次，二次篩選即為秒殺速度）..."):
            all_data_list = []
            
            delta = end_date - start_date
            dates_to_fetch = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
            progress_bar = st.progress(0)
            
            # 1. 將指定區間的每一天丟進快取函數
            for i, target_date in enumerate(dates_to_fetch):
                date_str = target_date.strftime('%Y%m%d')
                
                # 這裡會被秒殺，因為有 @st.cache_data 的保護
                df_daily = fetch_and_parse_data(date_str)
                if not df_daily.empty:
                    all_data_list.append(df_daily)
                    
                progress_bar.progress((i + 1) / len(dates_to_fetch))
                
            # 2. 整合與動態篩選
            if all_data_list:
                big_df = pd.concat(all_data_list, ignore_index=True)
                
                # 這裡才是套用您輸入的 threshold (門檻) 的地方！
                filtered_df = big_df[big_df['單筆平均規模(十萬)'] > threshold]
                
                if not filtered_df.empty:
                    final_cols = ['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '單筆平均規模(十萬)']
                    final_result = filtered_df[final_cols]
                    
                    st.success(f"🎉 處理完成！共找到 {len(final_result)} 筆單筆規模大於 {threshold} 的資料。")
                    st.dataframe(final_result, use_container_width=True)
                    
                    # 準備 Excel 下載
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        final_result.to_excel(writer, index=False, sheet_name='篩選結果')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 下載 Excel 報表",
                        data=excel_data,
                        file_name=f"大額交易篩選_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info(f"在所選期間內有交易紀錄，但沒有單筆規模大於 {threshold} 的項目。您可以試著調低門檻再次測試！")
            else:
                st.warning("⚠️ 所選期間內完全沒有找到有效的交易資料（可能為假日）。")
