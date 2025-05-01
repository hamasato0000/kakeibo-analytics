import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_LOGO = os.environ["APP_LOGO"]

pg = st.navigation([
    st.Page("home.py", title="ホーム", icon="🏠️"),
    st.Page("balance.py", title="収支分析", icon="📊")
])
pg.run()

st.logo(image=APP_LOGO, size="large")
