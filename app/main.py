import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ページ設定
st.set_page_config(
    page_title="Streamlitデモアプリ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    st.title("Streamlitデモアプリケーション")
    st.write("これは基本的なStreamlitアプリケーションのデモです。")

    # サイドバーの作成
    st.sidebar.header("設定")
    chart_type = st.sidebar.selectbox(
        "グラフの種類を選択してください:",
        ["折れ線グラフ", "棒グラフ", "散布図"]
    )

    data_size = st.sidebar.slider("データポイント数", 10, 100, 50)

    # データを生成
    if st.sidebar.button("新しいデータを生成"):
        st.session_state.data = generate_data(data_size)

    # 初回読み込みまたはデータがない場合はデータを生成
    if 'data' not in st.session_state:
        st.session_state.data = generate_data(data_size)

    # データ表示
    st.subheader("データプレビュー")
    st.dataframe(st.session_state.data)

    # 統計情報
    st.subheader("基本統計")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("平均値", f"{st.session_state.data['y'].mean():.2f}")
        st.metric("最小値", f"{st.session_state.data['y'].min():.2f}")
    with col2:
        st.metric("標準偏差", f"{st.session_state.data['y'].std():.2f}")
        st.metric("最大値", f"{st.session_state.data['y'].max():.2f}")

    # グラフ表示
    st.subheader("データ可視化")
    fig, ax = plt.subplots(figsize=(10, 6))

    if chart_type == "折れ線グラフ":
        ax.plot(st.session_state.data['x'], st.session_state.data['y'])
        ax.set_title("折れ線グラフ")
    elif chart_type == "棒グラフ":
        ax.bar(st.session_state.data['x'], st.session_state.data['y'])
        ax.set_title("棒グラフ")
    elif chart_type == "散布図":
        ax.scatter(st.session_state.data['x'], st.session_state.data['y'])
        ax.set_title("散布図")

    ax.set_xlabel("X値")
    ax.set_ylabel("Y値")
    ax.grid(True)

    st.pyplot(fig)

    # インタラクティブ要素のデモ
    st.subheader("インタラクティブ要素のデモ")

    with st.expander("インタラクティブ機能の詳細"):
        st.write("""
        Streamlitでは、ボタン、スライダー、テキスト入力など、
        様々なインタラクティブな要素を簡単に追加できます。
        """)

    # フォーム
    with st.form(key='form_example'):
        user_name = st.text_input("お名前")
        user_age = st.number_input("年齢", min_value=0, max_value=120, value=30)
        user_comment = st.text_area("コメント")
        submit_button = st.form_submit_button(label='送信')

        if submit_button:
            st.success(f"こんにちは、{user_name}さん！あなたは{user_age}歳ですね。")
            st.info(f"コメント: {user_comment}")

def generate_data(size):
    """サンプルデータを生成する関数"""
    x = np.linspace(0, 10, size)
    y = np.sin(x) * 5 + np.random.randn(size) * 2
    return pd.DataFrame({'x': x, 'y': y})

if __name__ == "__main__":
    main()
