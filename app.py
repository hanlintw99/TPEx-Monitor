import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io

# 設定網頁標題與排版
st.set_page_config(page_title="可轉債大額交易篩選", page_icon="📈", layout="wide")

st.title("📈 可轉債選擇權端 - 大額交易動態篩選器")
st.markdown("直接從櫃買中心抓取最新資料，並根據您的條件進行篩選，支援手機與電腦隨時查閱。")

# --- UI 介面：設定篩選條件 ---
col1, col2, col3 = st.columns(3)
with col1:
    # 預設抓取最近 5 天
    start_date = st.date_input("📅 起始日期", datetime.now() - timedelta(days=5))
with col2:
    end_date = st.date_input("📅 結束日期", datetime.now())
with col3:
    # 讓您可以隨時修改門檻，預設為 50
    threshold = st.number_input("🎯 篩選門檻 (單筆平均規模 > X 十萬)", value=50.0, step=5.0)

st.markdown("---")

# --- 執行按鈕 ---
if st.button("🚀 開始抓取與篩選", type="primary"):
    if start_date > end_date:
        st.error("❌ 起始日期不能晚於結束日期喔！")
    else:
        with st.spinner("正在連線至櫃買中心抓取資料，請稍候..."):
            result_list = []
            
            # 計算要抓取的每一天
            delta = end_date - start_date
            dates_to_fetch = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
            
            # 建立進度條
            progress_bar = st.progress(0)
            
            for i, target_date in enumerate(dates_to_fetch):
                date_str = target_date.strftime('%Y%m%d')
                api_url = f"https://www.tpex.org.tw/www/zh-tw/extendProduct/statTrDl?type=daily&fileName=CBdas001&date={date_str}"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                
                try:
                    res = requests.get(api_url, headers=headers, timeout=10)
                    # 判斷是否為無資料的 404 網頁
                    if res.status_code == 200 and "404" not in res.text and "<html" not in res.text:
                        valid_data = []
                        # 處理文字格式，避開 Excel 解碼問題
                        for line in res.text.split('\n'):
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
                            
                            # 動態套用使用者輸入的條件
                            df['單筆平均規模(十萬)'] = df['名目本金'] / df['成交筆數'] / 100000
                            filtered_df = df[df['單筆平均規模(十萬)'] > threshold].copy()
                            
                            if not filtered_df.empty:
                                filtered_df['日期'] = date_str
                                final_cols = ['日期', '標的證券代號', '標的證券名稱', '名目本金', '成交筆數', '單筆平均規模(十萬)']
                                result_list.append(filtered_df[final_cols])
                except Exception as e:
                    st.warning(f"⚠️ {date_str} 抓取失敗: {e}")
                
                # 更新進度條
                progress_bar.progress((i + 1) / len(dates_to_fetch))
            
            # --- 顯示與下載結果 ---
            if result_list:
                final_result = pd.concat(result_list, ignore_index=True)
                st.success(f"🎉 處理完成！共找到 {len(final_result)} 筆符合條件的資料。")
                
                # 直接在網頁上顯示精美的表格供查閱
                st.dataframe(final_result, use_container_width=True)
                
                # 將資料轉換為 Excel 檔案並提供下載按鈕
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
                st.info(f"在 {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')} 期間，沒有找到大於 {threshold} 的資料。")