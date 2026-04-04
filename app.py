import streamlit as st
import pandas as pd

# 💡 請將下方的網址替換成您 GitHub 檔案的 "Raw" 連結
# 格式為: https://raw.githubusercontent.com/您的帳號/專案名/main/tpex_database.csv
DB_URL = "https://raw.githubusercontent.com/您的帳號/TPEx-Monitor/main/tpex_database.csv"

st.title("📈 可轉債大額交易監控網頁版")

@st.cache_data(ttl=3600) # 每小時更新一次快取
def load_cloud_db():
    try:
        df = pd.read_csv(DB_URL)
        df['日期'] = df['日期'].astype(str)
        df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
        return df
    except:
        return pd.DataFrame()

db = load_cloud_db()

if not db.empty:
    # --- 動態篩選介面 ---
    threshold = st.slider("篩選門檻 (十萬)", 0, 150, 50)
    
    # 日期區間篩選
    all_dates = sorted(db['日期'].unique(), reverse=True)
    selected_dates = st.multiselect("選擇查看日期", all_dates, default=all_dates[:5])
    
    filtered = db[(db['單筆平均規模(十萬)'] > threshold) & (db['日期'].isin(selected_dates))]
    
    st.write(f"顯示 {selected_dates} 期間，規模大於 {threshold} 的標的：")
    st.dataframe(filtered.sort_values('日期', ascending=False), use_container_width=True)
else:
    st.error("目前雲端資料庫為空，請先在 GitHub 手動執行一次 Actions。")
