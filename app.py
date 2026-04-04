import streamlit as st
import pandas as pd
import io
import requests
import yfinance as yf
from datetime import datetime, timedelta

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
            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# 獲取最新即時價格的函數
@st.cache_data(ttl=3600)
def fetch_latest_prices(symbols):
    latest_prices = {}
    for sym in symbols:
        try:
            # 嘗試 .TWO (櫃買)
            ticker = yf.Ticker(f"{sym}.TWO")
            hist = ticker.history(period="1d")
            if not hist.empty:
                latest_prices[str(sym)] = round(hist['Close'].iloc[-1], 2)
            else:
                latest_prices[str(sym)] = "N/A"
        except:
            latest_prices[str(sym)] = "Error"
    return latest_prices

df = load_data()

if not df.empty:
    st.sidebar.header("⚙️ 篩選設定")
    min_date, max_date = df['DateObj'].min(), df['DateObj'].max()
    date_range = st.sidebar.date_input("📅 選擇區間", value=(max_date - timedelta(days=7), max_date), min_value=min_date, max_value=max_date)
    threshold = st.sidebar.slider("🎯 門檻 (十萬)", 10, 200, 50)
    
    if len(date_range) == 2:
        start_d, end_d = date_range
        mask = (df['DateObj'] >= start_d) & (df['DateObj'] <= end_d) & (df['單筆平均規模(十萬)'] >= threshold)
        result = df[mask].copy()
        
        if not result.empty:
            # 只有在需要時才去抓 Yahoo 最新價
            if st.sidebar.button("🔄 同步最新市價"):
                latest_map = fetch_latest_prices(result['標的證券代號'].unique())
                result['最新收盤價'] = result['標的證券代號'].astype(str).map(latest_map)
            else:
                result['最新收盤價'] = "點擊同步"

            st.subheader(f"📊 篩選結果 ({start_d} ~ {end_d})")
            # 欄位排序
            cols = ['日期', '標的證券代號', '標的證券名稱', '單筆平均規模(十萬)', '當日收盤價', '最新收盤價', '名目本金', '成交筆數']
            st.dataframe(result[cols].sort_values('日期', ascending=False), use_container_width=True)
        else:
            st.info("此區間無達標資料。")
else:
    st.warning("⚠️ 正在等待資料庫產出...")
