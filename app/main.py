import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_LOGO = os.environ["APP_LOGO"]
st.logo(image=APP_LOGO, size="large")

pg = st.navigation(
    [
        st.Page("home.py", title="ホーム", icon="🏠️"),
        st.Page("balance.py", title="収支分析", icon="📊"),
        st.Page("fixed_variable_cost.py", title="固定費・変動費分析", icon="💰"),
        st.Page("file_upload.py", title="ファイルアップロード", icon=":material/cloud_upload:"),
    ] if st.user.is_logged_in else [st.Page("home.py", title="ホーム", icon="🏠️")]
)

pg.run()

if st.user.is_logged_in:
    st.sidebar.write(f"ログイン中：{st.user.name}")
    st.sidebar.button("ログアウト", on_click=st.logout, icon=":material/logout:")
