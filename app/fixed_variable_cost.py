import streamlit as st
import pandas as pd
import s3_utils
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = os.environ["S3_PREFIX"]

def main():
    st.set_page_config(
        page_title="固定費・変動費分析",
        page_icon=":material/attach_money:",
        layout="wide"
    )

    st.title(":material/attach_money: 固定費・変動費分析")

    with st.spinner("家計簿データを取得中..."):
        # S3からデータを取得
        kakeibo_data: pd.DataFrame = s3_utils.read_csv_files_from_s3(bucket_name=S3_BUCKET_NAME, prefix=S3_PREFIX)

    st.dataframe(kakeibo_data, use_container_width=True)

main()
