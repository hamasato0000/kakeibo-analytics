import streamlit as st

st.title("💴 お金の管理を最適化しよう")

if not st.user.is_logged_in:
    st.markdown("#### まずはログイン")
    if st.button("ログイン", icon=":material/login:"):
        st.login("auth0")
else:
    st.sidebar.write(f"ログイン中：{st.user.name}")
    st.sidebar.button("ログアウト", on_click=st.logout, icon=":material/logout:")
