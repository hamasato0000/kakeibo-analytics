from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import re
from io import StringIO
import datetime
import os
import s3_utils

# .envファイルから環境変数を読み込む
load_dotenv()

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = os.environ["S3_PREFIX"]

# 必要なカラムリスト
REQUIRED_COLUMNS = [
    "計算対象", "日付", "内容", "金額（円）", "保有金融機関",
    "大項目", "中項目", "メモ", "振替", "ID"
]

# ファイル名の正規表現パターン
FILE_PATTERN = r"収入・支出詳細_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv"

def validate_file_name(file_name):
    """ファイル名が正しい形式かどうかを検証"""
    match = re.match(FILE_PATTERN, file_name)
    if not match:
        return False, "ファイル名が正しい形式ではありません。「収入・支出詳細_YYYY-MM-DD_YYYY-MM-DD.csv」形式である必要があります。"

    start_date_str = match.group(1)
    end_date_str = match.group(2)

    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")

        # 日付の順序チェック
        if start_date >= end_date:
            return False, "開始日が終了日より後になっています。"

        return True, (start_date, end_date)
    except ValueError:
        return False, "日付の形式が不正です。"

def validate_csv_content(df):
    """CSVの内容を検証"""
    # カラム名の確認
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        return False, f"必要なカラムがありません: {', '.join(missing_columns)}"

    return True, "CSVの内容は有効です。"

def determine_s3_key(start_date):
    """ファイル名から適切なS3のキーを決定"""
    # マネーフォワードの仕様によると、ファイルは翌月の給与支給日までのデータを含む
    # 例: 収入・支出詳細_2024-12-25_2025-01-23.csv は2025年1月分として扱う

    # 開始日の翌月を対象月とする
    # 開始日が25日周辺なので、単純に32日後を計算すれば確実に翌月になる
    next_month = start_date + datetime.timedelta(days=32)
    year = next_month.year
    month = next_month.month

    s3_key = f"{S3_PREFIX}/year={year}/month={month}"
    return s3_key

def main():
    st.set_page_config(page_title="CSV アップローダー", page_icon=":material/cloud_upload:", layout="centered")
    st.title(":material/cloud_upload: CSV アップローダー")

    st.write("マネーフォワードからエクスポートしたCSVファイルをS3にアップロードします。")
    st.write("ファイル名は「収入・支出詳細_YYYY-MM-DD_YYYY-MM-DD.csv」形式である必要があります。")

    # ファイル名例を表示
    with st.expander("ファイル名の例"):
        st.info("例：収入・支出詳細_2024-12-25_2025-01-23.csv")
        st.write("上記の例では、2024年12月25日から2025年1月23日までの取引が記録されています。")
        st.write("このファイルは2025年1月分のデータとして、S3の `year=2025/month=1` フォルダに保存されます。")

    uploaded_file = st.file_uploader("CSVファイルを選択してください", type=["csv"])

    if uploaded_file is not None:
        # ファイル名のバリデーション
        file_name = uploaded_file.name
        is_valid_name, name_result = validate_file_name(file_name)

        if not is_valid_name:
            st.error(name_result)
            return

        start_date, end_date = name_result

        # CSVの読み込みと内容の検証
        try:
            # StringIO経由でデータを読み取る
            string_data = StringIO(uploaded_file.getvalue().decode('shift-jis'))
            df = pd.read_csv(string_data)

            # 内容の検証
            is_valid_content, content_message = validate_csv_content(df)
            if not is_valid_content:
                st.error(content_message)
                return

            st.success("ファイルの検証に成功しました。")
            st.write(f"集計期間: {start_date.strftime('%Y年%m月%d日')} から {end_date.strftime('%Y年%m月%d日')}")

            # データプレビュー
            st.subheader("データプレビュー")
            st.dataframe(df.head())

            # S3に保存するパスの決定
            s3_key = determine_s3_key(start_date)
            st.write(f"保存先: s3://{S3_BUCKET_NAME}/{s3_key}/{file_name}")

            # アップロードボタン
            if st.button("S3にアップロード"):
                # ファイルを再度読み込み
                uploaded_file.seek(0)
                file_content = uploaded_file.read()

                with st.spinner("S3にアップロード中..."):
                    # S3にアップロード
                    success, result = s3_utils.upload_to_s3(S3_BUCKET_NAME, file_content, file_name, s3_key)

                    if success:
                        st.success(f"ファイルを S3 にアップロードしました: {result}")
                    else:
                        st.error(f"アップロード中にエラーが発生しました: {result}")

        except Exception as e:
            st.error(f"ファイル処理中にエラーが発生しました: {str(e)}")

main()
