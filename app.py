import streamlit as st
import pandas as pd
import io
import requests
import yfinance as yf
from datetime import datetime, timedelta

# 💡 請確保您的 GitHub 資訊正確
GITHUB_USER = "hanlintw99"
REPO_NAME = "TPEx-Monitor"
FILE_NAME = "tpex_database.csv"
DB_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{FILE_NAME}"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測 (含即時行情)")

# --- 股價抓取函數 (帶快取) ---
@st.cache_data(ttl=3600) # 股價快取 1 小時
def get_cb_prices(symbol_list, date_list):
    """
    批次抓取收盤價。
    symbol_list: 5碼代號清單
    date_list: YYYYMMDD 字串清單
    """
    price_map = {} # {(symbol, date): price}
    latest_map = {} # {symbol: latest_price}
    
    unique_symbols = list(set(symbol_list))
    
    for sym in unique_symbols:
        yf_sym = f"{sym}.TWO"
        try:
            ticker = yf.Ticker(yf_sym)
            # 抓取過去一段時間的歷史資料 (涵蓋資料庫最舊日期至今)
            hist = ticker.history(period="max")
            if not hist.empty:
                # 1. 存入最新價格
                latest_map[sym] = round(hist['Close'].iloc[-1], 2)
                
                # 2. 建立日期索引對應表
                hist.index = hist.index.strftime('%Y%m%d')
                for d in date_list:
                    if d in hist.index:
                        price_map[(sym, d)] = round(hist.loc[d, 'Close'], 2)
                    else:
                        price_map[(sym, d)] = None # 當日停券或無交易
        except:
            latest_map[sym] = None
            
    return price_map, latest_map

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
    
    # 日期與門檻設定
    min_date, max_date = df['DateObj'].min(), df['DateObj'].max()
    date_range = st.sidebar.date_input("📅 選擇日期區間", value=(max_date - timedelta(days=7), max_date), min_value=min_date, max_value=max_date)
    threshold = st.sidebar.slider("🎯 單筆平均規模門檻 (十萬)", 10, 200, 50)
    
    if len(date_range) == 2:
        start_d, end_d = date_range
        mask = (df['DateObj'] >= start_d) & (df['DateObj'] <= end_d) & (df['單筆平均規模(十萬)'] >= threshold)
        result = df[mask].copy()
        
        if not result.empty:
            # --- 抓取價格項目 ---
            with st.spinner("正在同步 Yahoo Finance 收盤行情..."):
                price_map, latest_map = get_cb_prices(result['標的證券代號'].tolist(), result['日期'].tolist())
                
                # 填入「當日收盤價」
                result['當日收盤價'] = result.apply(lambda x: price_map.get((str(x['標的證券代號']), x['日期']), "無資料"), axis=1)
                # 填入「最新收盤價」
                result['最新收盤價'] = result['標的證券代號'].astype(str).map(latest_map)

            # 顯示結果
            st.subheader(f"📊 篩選結果 ({start_d} ~ {end_d})")
            display_cols = ['日期', '標的證券代號', '標的證券名稱', '單筆平均規模(十萬)', '當日收盤價', '最新收盤價', '名目本金', '成交筆數']
            
            # 美化表格：將價格標註顏色
            st.dataframe(result[display_cols].sort_values(['日期', '單筆平均規模(十萬)'], ascending=[False, False]), use_container_width=True)
            
            # 下載按鈕
            output = io.BytesIO()
            result[display_cols].to_excel(output, index=False)
            st.download_button(label="📥 下載含股價報表", data=output.getvalue(), file_name="CB_Analysis.xlsx")
        else:
            st.info("此區間無符合條件資料。")
else:
    st.warning("⚠️ 雲端資料庫讀取中或尚未產生檔案。")
