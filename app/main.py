import streamlit as st

pg = st.navigation([
    st.Page("home.py", title="ホーム", icon="🏠️"),
    st.Page("balance.py", title="収支分析", icon="📊")
])
pg.run()
