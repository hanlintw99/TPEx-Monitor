import streamlit as st
import pandas as pd
import io
import requests

# 💡 自動合成網址，排除 refs/heads 等多餘路徑
GITHUB_USER = "hanlintw99"
REPO_NAME = "TPEx-Monitor"
FILE_NAME = "tpex_database.csv"

# 這是最標準、最不容易出錯的原始資料網址
DB_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{FILE_NAME}"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測")

@st.cache_data(ttl=300)
def load_data():
    try:
        # 使用 verify=False 避免某些環境的 SSL 驗證失敗
        response = requests.get(DB_URL, timeout=10, verify=False)
        
        if response.status_code == 200:
            # 成功抓取
            df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8-sig')
            
            # 基本資料轉換
            df['日期'] = df['日期'].astype(str)
            df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
            df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
            df = df.dropna(subset=['名目本金', '成交筆數'])
            
            # 計算指標
            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
            return df
        else:
            # 這裡會顯示到底為什麼 404
            st.error(f"❌ 雲端檔案讀取失敗 (HTTP {response.status_code})")
            st.info(f"請確認此連結是否能在瀏覽器打開：\n{DB_URL}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"連線異常: {e}")
        return pd.DataFrame()

df = load_data()

# 後續篩選邏輯...
if not df.empty:
    st.sidebar.header("⚙️ 篩選設定")
    threshold = st.sidebar.slider("門檻 (十萬)", 10, 200, 50)
    
    # 日期多選
    all_dates = sorted(df['日期'].unique(), reverse=True)
    sel_dates = st.sidebar.multiselect("日期", all_dates, default=all_dates[:3])
    
    # 顯示結果
    mask = (df['單筆平均規模(十萬)'] >= threshold) & (df['日期'].isin(sel_dates))
    res = df[mask].sort_values(['日期', '單筆平均規模(十萬)'], ascending=[False, False])
    st.dataframe(res[['日期', '標的證券代號', '標的證券名稱', '單筆平均規模(十萬)', '名目本金', '成交筆數']], use_container_width=True)
else:
    st.warning("⚠️ 倉庫中尚未發現 tpex_database.csv 檔案。請先執行 GitHub Actions 並確認檔案已存入 Code 分頁。")
