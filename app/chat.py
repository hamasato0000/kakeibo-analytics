import streamlit as st
import random
import time

st.set_page_config(page_title="チャット", layout="centered")

st.title("Simple Chat")

def response_generator():
    response = random.choice(
        [
            "Hello there! How can I assist you today?",
            "Hi, human! Is there anything I can help you with?",
            "Do you need help?",
        ]
    )
    for word in response.split():
        yield word + " "
        time.sleep(0.05)

# チャット履歴を初期化
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    # ユーザーメッセージをチャットメッセージコンテナに表示
    with st.chat_message("user"):
        st.markdown(prompt)

    # ユーザーメッセージをチャット履歴に追加
    st.session_state.messages.append({"role": "user", "content": prompt})

    response = f"Echo: {prompt}"

    # アシスタントの応答をチャットメッセージコンテナに表示
    with st.chat_message("assistant"):
        response = st.write_stream(response_generator())

    # アシスタントの応答をチャット履歴に追加
    st.session_state.messages.append({"role": "assistant", "content": response})
