import os
import streamlit as st
from dotenv import load_dotenv
from util import create_secrets_toml

print("main.pyが読み込まれました")

load_dotenv()

create_secrets_toml()

APP_LOGO = os.environ["APP_LOGO"]
st.logo(image=APP_LOGO, size="large")

pg = st.navigation(
    [
        st.Page("home.py", title="ホーム", icon=":material/home:"),
        st.Page("balance.py", title="収支分析", icon=":material/analytics:"),
        st.Page("fixed_variable_cost.py", title="固定費・変動費分析", icon=":material/attach_money:"),
        st.Page("food_analysis.py", title="食費分析", icon=":material/restaurant:"),
        st.Page("file_upload.py", title="ファイルアップロード", icon=":material/cloud_upload:"),
        st.Page("chat.py", title="チャット", icon=":material/chat:"),
    ] if st.user.is_logged_in else [st.Page("home.py", title="ホーム", icon=":material/home:")]
)

pg.run()

if st.user.is_logged_in:
    st.sidebar.write(f"ログイン中：{st.user.name}")
    st.sidebar.button("ログアウト", on_click=st.logout, icon=":material/logout:")
