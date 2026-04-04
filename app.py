import streamlit as st
import pandas as pd
import requests

# 💡 請替換成您自己的 GitHub 帳號與專案名稱
GITHUB_USER = "您的GitHub帳號"
REPO_NAME = "TPEx-Monitor"
FILE_PATH = "tpex_database.csv"

# 這是 GitHub 原始檔案的標準下載網址格式
DB_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{FILE_PATH}"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測")

@st.cache_data(ttl=600) # 每 10 分鐘檢查一次有無新資料
def load_data():
    try:
        # 直接讀取 GitHub 上的資料庫
        df = pd.read_csv(DB_URL)
        df['日期'] = df['日期'].astype(str)
        # 計算篩選指標
        df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
        return df
    except Exception as e:
        st.error(f"無法讀取雲端資料庫: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # 介面設定
    st.sidebar.header("篩選條件")
    threshold = st.sidebar.slider("單筆平均規模門檻 (十萬)", 10, 200, 50)
    
    # 日期多選
    available_dates = sorted(df['日期'].unique(), reverse=True)
    selected_dates = st.sidebar.multiselect("選擇日期", available_dates, default=available_dates[:5])
    
    # 執行篩選
    mask = (df['單筆平均規模(十萬)'] >= threshold) & (df['日期'].isin(selected_dates))
    result = df[mask].sort_values(['日期', '單筆平均規模(十萬)'], ascending=[False, False])
    
    st.subheader(f"📊 篩選結果 (門檻 > {threshold} 十萬)")
    st.dataframe(result, use_container_width=True)
    
    # 簡單的統計圖表
    if not result.empty:
        st.bar_chart(result.set_index('標的證券名稱')['單筆平均規模(十萬)'])
else:
    st.warning("⚠️ 雲端資料庫目前沒有資料，請確認 GitHub Action 是否已成功執行並產生 tpex_database.csv")
