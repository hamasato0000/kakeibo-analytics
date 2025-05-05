import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_LOGO = os.environ["APP_LOGO"]
st.logo(image=APP_LOGO, size="large")

pg = st.navigation(
    [
        st.Page("home.py", title="ホーム", icon="🏠️"),
        st.Page("balance.py", title="収支分析", icon="📊")
    ] if st.user.is_logged_in else [st.Page("home.py", title="ホーム", icon="🏠️")]
)

pg.run()
