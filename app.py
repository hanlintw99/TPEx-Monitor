import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, timedelta

# 💡 請確認您的 GitHub 資訊
GITHUB_USER = "hanlintw99"
REPO_NAME = "TPEx-Monitor"
FILE_NAME = "tpex_database.csv"
DB_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{FILE_NAME}"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測")

@st.cache_data(ttl=600)
def load_data():
    try:
        response = requests.get(DB_URL, timeout=15, verify=False)
        if response.status_code == 200:
            df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8-sig')
            df['日期'] = df['日期'].astype(str)
            df['DateObj'] = pd.to_datetime(df['日期'], format='%Y%m%d').dt.date
            # 計算篩選指標
            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("⚙️ 篩選設定")
    
    # 日期區間選取
    min_date = df['DateObj'].min()
    max_date = df['DateObj'].max()
    
    date_range = st.sidebar.date_input(
        "📅 選擇日期區間",
        value=(max_date - timedelta(days=7), max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    threshold = st.sidebar.slider("🎯 單筆平均規模門檻 (十萬)", 10, 200, 50)
    
    if len(date_range) == 2:
        start_d, end_d = date_range
        mask = (df['DateObj'] >= start_d) & (df['DateObj'] <= end_d) & (df['單筆平均規模(十萬)'] >= threshold)
        result = df[mask].copy()
        
        st.subheader(f"📊 篩選結果 ({start_d} ~ {end_d})")
        if not result.empty:
            # 💡 依照日期降序排列
            display_df = result.sort_values(['日期', '單筆平均規模(十萬)'], ascending=[False, False])
            # 排除輔助用的 DateObj，只顯示乾淨的欄位
            show_cols = ['日期', '標的證券代號', '標的證券名稱', '單筆平均規模(十萬)', '名目本金', '成交筆數']
            st.dataframe(display_df[show_cols], use_container_width=True)
            
            # 下載按鈕
            csv = display_df[show_cols].to_csv(index=False, encoding='utf-8-sig')
            st.download_button(label="📥 下載 CSV 報表", data=csv, file_name="CB_Report.csv", mime="text/csv")
        else:
            st.info("此區間無達標資料。")
else:
    st.warning("⚠️ 正在從 GitHub 讀取資料庫，請稍候...")
