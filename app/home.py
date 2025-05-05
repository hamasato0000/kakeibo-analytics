import streamlit as st

st.title("💴 お金の管理を最適化しよう")

if st.button("Log in"):
    st.login("auth0")
st.write(f"Hello, {st.user.to_dict()}!")

if st.user.is_logged_in:
    st.sidebar.write(st.user.name)
    st.sidebar.button("Log out", on_click=st.logout, icon=":material/logout:")
