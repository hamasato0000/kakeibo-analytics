import streamlit as st

st.title(":material/account_balance: お金の管理を最適化しよう")

if not st.user.is_logged_in:
    st.markdown("#### まずはログイン")
    if st.button("ログイン", icon=":material/login:"):
        st.login("auth0")
else:
    st.markdown("#### 収支トレンドを見て全体感を把握しよう")
    st.page_link("balance.py", label="収支分析", icon=":material/analytics:")

    st.markdown("#### 固定費・変動費を見直そう")
    st.page_link("fixed_variable_cost.py", label="固定費・変動費分析", icon=":material/attach_money:")

    st.markdown("#### 食費の傾向を把握しよう")
    st.page_link("food_analysis.py", label="食費分析", icon=":material/restaurant:")

