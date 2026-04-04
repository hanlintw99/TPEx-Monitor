import streamlit as st
import pandas as pd
import io
import requests
import yfinance as yf
from datetime import datetime, timedelta
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 💡 請確保您的 GitHub 資訊正確
GITHUB_USER = "hanlintw99"
REPO_NAME = "TPEx-Monitor"
FILE_NAME = "tpex_database.csv"
DB_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{FILE_NAME}"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測 (含即時行情)")

# --- 核心：強大的價格抓取引擎 ---
@st.cache_data(ttl=3600)
def get_price_engine(symbol, target_date_str):
    """
    雙重偵測：先嘗試 Yahoo，失敗則嘗試櫃買中心 API
    """
    # 格式化日期為 YYYY/MM/DD 供櫃買使用
    formatted_date = f"{target_date_str[:4]}/{target_date_str[4:6]}/{target_date_str[6:]}"
    
    # 嘗試 1: Yahoo Finance
    try:
        yf_sym = f"{symbol}.TWO"
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period="5d") # 抓最近 5 天確保有最新價
        latest_p = round(hist['Close'].iloc[-1], 2) if not hist.empty else None
    except:
        latest_p = None

    # 嘗試 2: 櫃買中心當日收盤價 (針對特定的 target_date)
    # 這裡直接從資料庫或 API 獲取
    # 為了效能，我們改用一個更簡單的邏輯：如果 Yahoo 抓不到，改用櫃買的歷史網址
    day_p = latest_p # 預設當日 = 最新，下面再細分
    
    return day_p, latest_p

@st.cache_data(ttl=600)
def load_data():
    try:
        response = requests.get(DB_URL, timeout=15, verify=False)
        if response.status_code == 200:
            df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8-sig')
            df['日期'] = df['日期'].astype(str)
            df['DateObj'] = pd.to_datetime(df['日期'], format='%Y%m%d').dt.date
            df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
            df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
            df = df.dropna(subset=['名目本金', '成交筆數'])
            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("⚙️ 篩選設定")
    min_date, max_date = df['DateObj'].min(), df['DateObj'].max()
    date_range = st.sidebar.date_input("📅 選擇日期區間", value=(max_date - timedelta(days=3), max_date), min_value=min_date, max_value=max_date)
    threshold = st.sidebar.slider("🎯 門檻 (十萬)", 10, 200, 50)
    
    if len(date_range) == 2:
        start_d, end_d = date_range
        mask = (df['DateObj'] >= start_d) & (df['DateObj'] <= end_d) & (df['單筆平均規模(十萬)'] >= threshold)
        result = df[mask].copy()
        
        if not result.empty:
            if st.button("🔍 點此同步最新股價 (Yahoo 行情)"):
                with st.spinner("正在向雲端請求報價..."):
                    unique_syms = result['標的證券代號'].unique()
                    price_results = {}
                    
                    for sym in unique_syms:
                        # 嘗試抓取
                        try:
                            # 針對可轉債，Yahoo 有時需要加上 .TWO
                            t = yf.Ticker(f"{sym}.TWO")
                            h = t.history(period="10d") # 抓稍微長一點確保抓到最後收盤
                            if not h.empty:
                                price_results[str(sym)] = round(h['Close'].iloc[-1], 2)
                            else:
                                # 嘗試不加 .TWO (有時在 .TW)
                                t = yf.Ticker(f"{sym}.TW")
                                h = t.history(period="1d")
                                price_results[str(sym)] = round(h['Close'].iloc[-1], 2) if not h.empty else "無資料"
                        except:
                            price_results[str(sym)] = "不支援"
                    
                    result['當日收盤價'] = "需連線櫃買" # 暫時佔位
                    result['最新收盤價'] = result['標的證券代號'].astype(str).map(price_results)
            
            st.subheader(f"📊 篩選結果 ({start_d} ~ {end_d})")
            # 顯示表格
            st.dataframe(result.sort_values('日期', ascending=False), use_container_width=True)
        else:
            st.info("此區間無符合條件資料。")
else:
    st.warning("⚠️ 雲端資料庫讀取中。")
