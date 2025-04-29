import streamlit as st
import pandas as pd
import s3fs # s3fsライブラリ (pip install s3fs)

# --- 定数定義 ---
# !!! ご自身のS3バケット名に置き換えてください !!!
S3_BUCKET_NAME = "mh-kakeibo-data" # 例
S3_BASE_PREFIX = "moneyforward/raw-csvs" # S3内の基本フォルダパス
# S3のフォルダ構成に合わせた検索パターン (全ての年・月のCSV)
S3_SEARCH_PATTERN = f"{S3_BUCKET_NAME}/{S3_BASE_PREFIX}/year=*/month=*/*.csv"
CSV_ENCODING = "shift_jis" # または 'cp932'など

# --- S3接続初期化 ---
# AWS認証情報は環境変数、IAMロール、~/.aws/credentials などで設定されている想定
try:
    fs = s3fs.S3FileSystem()
    st.sidebar.success("S3接続OK")
except Exception as e:
    st.error(f"S3への接続に失敗しました。AWS認証情報を確認してください。エラー: {e}")
    st.stop() # エラー時は処理を停止

# --- データ取得関数 (シンプル版・全件取得) ---
# @st.cache_data(ttl=600) # 必要であればキャッシュを有効化
def load_all_data_from_s3():
    """S3から全ての家計簿CSVデータを読み込む関数"""
    all_data = []
    file_paths_found = []

    st.info(f"S3パス '{S3_SEARCH_PATTERN}' からファイル検索中...")

    try:
        # s3fs.glob は s3:// を付けないパスパターン
        # バケット名を含めたパスパターンで検索
        file_paths_found = fs.glob(S3_SEARCH_PATTERN)

    except Exception as e:
        st.error(f"S3ファイル検索中にエラーが発生しました: {e}")
        return pd.DataFrame(), [] # 空のDataFrameとリストを返す

    if not file_paths_found:
        st.warning("データファイルが見つかりませんでした。")
        return pd.DataFrame(), []

    st.info(f"{len(file_paths_found)} 個のCSVファイルが見つかりました。読み込みます...")

    # --- 見つかったファイルを一つずつ読み込む ---
    for s3_file_path in file_paths_found:
        try:
            # read_csvには 's3://' をつけるか、fs.open()を使う
            df = pd.read_csv(f"s3://{s3_file_path}", encoding=CSV_ENCODING)
            all_data.append(df)
        except Exception as read_e:
            # エラーが発生しても処理を続行し、エラーメッセージを表示
            st.error(f"ファイル読み込みエラー (s3://{s3_file_path}): {read_e}")
            # 必要に応じて、問題のあったファイルパスを記録するなどしても良い

    if not all_data:
        st.warning("ファイルの読み込みに成功しませんでした。")
        return pd.DataFrame(), file_paths_found # 読み込めたデータはないが、見つかったパスは返す

    # --- 読み込んだ全データを結合 ---
    st.success("全ファイルの読み込み完了。データを結合します。")
    combined_df = pd.concat(all_data, ignore_index=True)

    # 日付列をdatetime型に変換 (エラーは無視してNaTにする)
    combined_df['日付'] = pd.to_datetime(combined_df['日付'], errors='coerce')

    return combined_df, file_paths_found # 結合したDataFrameと、見つかったファイルパスのリストを返す

# --- メイン処理 ---
st.header("全家計簿データ取得")

if st.button("S3から全データを読み込む"):
    # データ読み込み関数を実行
    all_df, found_files = load_all_data_from_s3()

    if not all_df.empty:
        st.subheader("読み込み結果 (先頭5行)")
        st.dataframe(all_df.head())
        st.subheader("データ概要")
        st.write(f"合計 {len(all_df)} 行")
        st.write(f"読み込み元ファイル数: {len(found_files)}")
        # メモリ使用量などを表示
        st.text(all_df.info(memory_usage='deep'))

        # 必要であれば、全データをCSVとしてダウンロードする機能などをここに追加できる
        # @st.cache_data
        # def convert_df(df):
        #     return df.to_csv(index=False).encode('utf-8-sig') # BOM付きUTF-8

        # csv_data = convert_df(all_df)
        # st.download_button(
        #     label="全データをCSVでダウンロード",
        #     data=csv_data,
        #     file_name='all_kakeibo_data.csv',
        #     mime='text/csv',
        # )
    else:
        st.info("表示できるデータがありませんでした。")
