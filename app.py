import streamlit as st
import pandas as pd
import io
import requests

# 💡 請確實替換為您的 GitHub 資訊
GITHUB_USER = "hanlintw99"
REPO_NAME = "TPEx-Monitor"
FILE_PATH = "tpex_database.csv"

# 使用標準的 Raw 檔案連結
DB_URL = f"https://raw.githubusercontent.com/hanlintw99/TPEx-Monitor/main/tpex_database.csv"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測")

@st.cache_data(ttl=600)
def load_data():
    try:
        # 解決編碼問題：先用 requests 抓取原始二進位資料
        response = requests.get(DB_URL, timeout=15)
        if response.status_code == 200:
            # 使用 BytesIO 配合 utf-8-sig (處理 Excel 產生的 BOM)
            csv_data = io.BytesIO(response.content)
            df = pd.read_csv(csv_data, encoding='utf-8-sig')
            
            # 確保欄位型態正確
            df['日期'] = df['日期'].astype(str)
            df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
            df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
            
            # 計算篩選指標
            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
            return df
        else:
            st.error(f"GitHub 檔案抓取失敗，狀態碼：{response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"解析雲端資料庫時發生編碼錯誤: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("⚙️ 篩選設定")
    threshold = st.sidebar.slider("單筆平均規模門檻 (十萬)", 10, 200, 50)
    
    # 日期多選
    available_dates = sorted(df['日期'].unique(), reverse=True)
    selected_dates = st.sidebar.multiselect("選擇查看日期", available_dates, default=available_dates[:5])
    
    # 執行篩選
    mask = (df['單筆平均規模(十萬)'] >= threshold) & (df['日期'].isin(selected_dates))
    result = df[mask].sort_values(['日期', '單筆平均規模(十萬)'], ascending=[False, False])
    
    # 顯示結果
    st.subheader(f"📊 篩選結果 (門檻 > {threshold} 十萬)")
    if not result.empty:
        # 整理欄位順序美化顯示
        display_cols = ['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '單筆平均規模(十萬)']
        st.dataframe(result[display_cols], use_container_width=True)
    else:
        st.info("符合條件的資料為 0 筆，請調低門檻或檢查日期。")
else:
    st.info("💡 正在等待 GitHub Action 產生資料庫檔案，或請檢查 GitHub 上的 tpex_database.csv 是否已存在。")
