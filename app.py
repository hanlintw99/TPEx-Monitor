import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime, timedelta

# 💡 請確保您的 GitHub 帳號與專案名稱正確
GITHUB_USER = "hanlintw99"
REPO_NAME = "TPEx-Monitor"
FILE_NAME = "tpex_database.csv"

# 標準 Raw 連結格式
DB_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{FILE_NAME}"

st.set_page_config(page_title="可轉債監控網頁", layout="wide")
st.title("📈 可轉債大額交易雲端監測")

@st.cache_data(ttl=600)
def load_data():
    try:
        # 強制使用不檢查 SSL 的方式抓取，避免某些環境阻擋
        response = requests.get(DB_URL, timeout=15, verify=False)
        if response.status_code == 200:
            # 使用 utf-8-sig 處理中文
            df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8-sig')
            
            # 確保日期欄位為字串以便處理，並轉換數值欄位
            df['日期'] = df['日期'].astype(str)
            # 將 YYYYMMDD 格式轉換為真正的日期物件，方便區間篩選
            df['DateObj'] = pd.to_datetime(df['日期'], format='%Y%m%d').dt.date
            
            df['名目本金'] = pd.to_numeric(df['名目本金'], errors='coerce')
            df['成交筆數'] = pd.to_numeric(df['成交筆數'], errors='coerce')
            df = df.dropna(subset=['名目本金', '成交筆數'])
            df = df[df['成交筆數'] > 0]
            
            # 計算指標
            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
            return df
        else:
            st.error(f"❌ 雲端檔案讀取失敗 (HTTP {response.status_code})")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"連線異常: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.sidebar.header("⚙️ 篩選設定")
    
    # --- 修改部分：日期區間選取 ---
    min_date = df['DateObj'].min()
    max_date = df['DateObj'].max()
    
    date_range = st.sidebar.date_input(
        "📅 選擇日期區間",
        value=(max_date - timedelta(days=7), max_date), # 預設選取最近一週
        min_value=min_date,
        max_value=max_date
    )
    
    threshold = st.sidebar.slider("🎯 單筆平均規模門檻 (十萬)", 10, 200, 50)
    
    # 確保使用者選了兩個日期（開始與結束）
    if len(date_range) == 2:
        start_d, end_d = date_range
        
        # 執行篩選邏輯
        mask = (
            (df['DateObj'] >= start_d) & 
            (df['DateObj'] <= end_d) & 
            (df['單筆平均規模(十萬)'] >= threshold)
        )
        
        result = df[mask].sort_values(['日期', '單筆平均規模(十萬)'], ascending=[False, False])
        
        # 顯示結果
        st.subheader(f"📊 篩選結果 ({start_d} ~ {end_d}, 門檻 > {threshold})")
        if not result.empty:
            display_cols = ['日期', '標的證券代號', '標的證券名稱', '單筆平均規模(十萬)', '名目本金', '成交筆數']
            st.dataframe(result[display_cols], use_container_width=True)
            
            # 提供 Excel 下載
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result[display_cols].to_excel(writer, index=False)
            st.download_button(
                label="📥 下載此區間 Excel 報表",
                data=output.getvalue(),
                file_name=f"CB_Report_{start_d}_{end_d}.xlsx",
                mime="application/vnd.ms-excel"
            )
        else:
            st.info("此區間內無符合門檻之資料，請調低門檻或擴大日期範圍。")
    else:
        st.info("請在日曆中點選「開始日期」與「結束日期」以完成區間選取。")
else:
    st.warning("⚠️ 倉庫中尚未發現 tpex_database.csv 檔案。請先確認 GitHub 上的檔案是否已正確產出。")
