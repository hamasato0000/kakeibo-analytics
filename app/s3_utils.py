import streamlit as st
import pandas as pd
import s3fs


@st.cache_resource
def get_s3fs() -> s3fs.S3FileSystem:
    """S3ファイルシステムのインスタンスを取得する

    :return: S3FileSystemインスタンス
    :rtype: s3fs.S3FileSystem
    """

    # 環境変数から認証情報を取得する場合
    return s3fs.S3FileSystem(anon=False)

@st.cache_data(ttl="1h")
def read_csv_files_from_s3(bucket_name: str, prefix: str) -> pd.DataFrame | None:
    """S3バケットから家計簿CSVファイルの一覧を取得する

    :param bucket_name: S3バケット名
    :type bucket_name: str
    :param prefix: S3バケット内のプレフィックス
    :type prefix: str
    :return: 家計簿データのDataFrame
    :rtype: pd.DataFrame | None
    """

    s3 = get_s3fs()
    csv_path = f"{bucket_name}/{prefix}**/*.csv"
    csv_files = s3.glob(csv_path)

    # 各CSVファイルを読み込みDataFrameのリストに格納
    kakeibo_lists: list[pd.DataFrame] = []
    for csv_file in csv_files:
        try:
            # ファイル名を表示
            filename = csv_file.split('/')[-1]
            print(f"Reading file: {filename}")

            # S3からファイルを読み込む
            with s3.open(csv_file, 'rb') as f:
                # CSVファイルを読み込み
                df = pd.read_csv(f, encoding='shift-jis')

                # ファイル名をDataFrameに追加
                df['source_file'] = filename

                # リストに追加
                kakeibo_lists.append(df)

        except Exception as e:
            print(f"Error reading {csv_file}: {e}")

    # 全てのDataFrameを結合
    if kakeibo_lists:
        return pd.concat(kakeibo_lists, ignore_index=True)
    else:
        print("No CSV files were read successfully.")
        return None
