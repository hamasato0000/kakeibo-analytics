import pandas as pd
import s3fs
import streamlit as st
import re
import os
from datetime import datetime
import altair as alt
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = os.environ["S3_PREFIX"]

st.title("📊 収支分析")

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

# S3からCSVファイルを読み込む
@st.cache_data(ttl="1h")
def read_csv_from_s3(file_path):
    """S3からCSVファイルを読み込む"""

    s3 = get_s3fs()
    with s3.open(file_path, 'rb') as f:
        # 文字コードを自動判定して読み込む
        df = pd.read_csv(f, encoding='Shift-JIS')
    return df

def preprocess_data(kakeibo_df: pd.DataFrame) -> pd.DataFrame:
    """家計簿データを前処理する
    :param kakeibo_df: 家計簿データ
    :type kakeibo_df: pd.DataFrame
    :return: 前処理済みの家計簿データ
    :rtype: pd.DataFrame
    """

    df = kakeibo_df.copy()

    # カラム名を英語に変換して扱いやすくする
    columns_mapping = {
        "計算対象": "is_target",
        "日付": "date",
        "内容": "description",
        "金額（円）": "amount",
        "保有金融機関": "financial_institution",
        "大項目": "major_category",
        "中項目": "minor_category",
        "メモ": "memo",
        "振替": "is_transfer",
        "ID": "id"
    }
    df = df.rename(columns=columns_mapping)

    # データ操作や集計をしやすくするために日付をdatetime型に変換
    df['date'] = pd.to_datetime(df['date'])

    # 計算対象と振替のフラグを数値型に変換
    df['is_target'] = df['is_target'].astype(int)
    df['is_transfer'] = df['is_transfer'].astype(int)

    # 「収入」カテゴリの分類
    df['is_salary'] = df['major_category'].str.contains('収入') & df['minor_category'].str.contains('給与')
    df['is_bonus'] = df['major_category'].str.contains('収入') & df['minor_category'].str.contains('一時所得')
    df['is_other_income'] = df['major_category'].str.contains('収入') & ~(df['minor_category'].str.contains('給与') | df['minor_category'].str.contains('一時所得'))

    # 計算対象外のものは削除
    df = df[df['is_target'] == 1]

    # 振替対象のものは削除
    df = df[df['is_transfer'] == 0]

    return df

def get_kakeibo_data_range(preprocessed_kakeibo_df: pd.DataFrame) -> tuple[datetime, datetime]:
    """
    家計簿データの日付範囲を取得する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    :return: 最古の日付, 最新の日付のタプル
    :rtype: tuple[datetime, datetime]
    """

    # date列の最小値と最大値を取得
    oldest_date: datetime = preprocessed_kakeibo_df['date'].min()
    newest_date: datetime = preprocessed_kakeibo_df['date'].max()

    return oldest_date, newest_date

def display_kakeibo_data_range(preprocessed_kakeibo_df: pd.DataFrame):
    """
    家計簿データの期間を表示する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    """

    # 家計簿データの期間を取得
    start_date, end_date = get_kakeibo_data_range(preprocessed_kakeibo_df)
    st.markdown(f":gray[家計簿データの期間：{start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%Y/%m/%d')}]")

def calculate_total_income_expense(preprocessed_kakeibo_df: pd.DataFrame) -> tuple[float, float, float]:
    """
    総収入と総支出を計算する

    :param df: 前処理した家計簿データ
    :type df: pd.DataFrame
    :return: 総収入、総支出、総収支バランスを含むタプル
    :rtype: tuple[float, float, float]
    """
    # 総収入の計算
    total_income = preprocessed_kakeibo_df[preprocessed_kakeibo_df['is_salary'] | preprocessed_kakeibo_df['is_bonus']]['amount'].sum()

    # 総支出の計算
    total_expense = preprocessed_kakeibo_df[~(preprocessed_kakeibo_df['is_salary'] | preprocessed_kakeibo_df['is_bonus'])]['amount'].sum()

    # 総収支バランスの計算
    total_balance = total_income + total_expense  # 支出は負の値なので加算

    return total_income, total_expense, total_balance

def display_total_income_expense(preprocessed_kakeibo_df: pd.DataFrame):
    """
    家計簿データの総収入と総支出を表示する
    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    """

    total_income, total_expense, total_balance = calculate_total_income_expense(preprocessed_kakeibo_df)

    container = st.container(border=True)

    total_income_expense_row = container.columns(2)

    for col in total_income_expense_row:
        col.markdown("#### 総収入" if col == total_income_expense_row[0] else "#### 総支出")
        col.markdown(f"#### :blue[¥ {total_income:,.0f}]" if col == total_income_expense_row[0] else f"#### :red[¥ {total_expense:,.0f}]")

    total_balance_row = container.columns(2)
    total_balance_row[0].markdown("#### 総収支バランス")
    total_balance_row[0].markdown(f"#### :green[¥ {total_balance:,.0f}]")

def display_average_income_expense(preprocessed_kakeibo_df: pd.DataFrame):
    """
    家計簿データの平均収入と平均支出を表示する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    """

    df = preprocessed_kakeibo_df.copy()

    # 年月のカラムを追加
    df['year_month'] = df['date'].dt.to_period('M')

    income_with_bonus_df = df[df['is_salary'] | df['is_bonus']]
    income_without_bonus_df = df[df['is_salary']]
    expense_df = df[~(df['is_salary'] | df['is_bonus'])]

    # 月ごとのデータ集計
    monthly_summary = pd.DataFrame({
        'income_with_bonus': income_with_bonus_df.groupby('year_month')['amount'].sum(),
        'income_without_bonus': income_without_bonus_df.groupby('year_month')['amount'].sum(),
        'expense': expense_df.groupby('year_month')['amount'].sum(),
    }).reset_index()

    monthly_summary['balance_with_bonus'] = monthly_summary['income_with_bonus'] + monthly_summary['expense']
    monthly_summary['balance_without_bonus'] = monthly_summary['income_without_bonus'] + monthly_summary['expense']

    # 月平均を算出
    monthly_avg = monthly_summary[['income_with_bonus', 'income_without_bonus', 'expense', 'balance_with_bonus', 'balance_without_bonus']].mean()
    monthly_avg = monthly_avg.round(0).astype(int)

    category_labels = {
        'income_with_bonus': '月平均収入（賞与込み）',
        'income_without_bonus': '月平均収入（賞与なし）',
        'expense': '月平均支出',
        'balance_with_bonus': '月平均収支バランス（賞与込み）',
        'balance_without_bonus': '月平均収支バランス（賞与なし）'
    }

    for category, amount in monthly_avg.items():
        label = category_labels.get(category, category)  # マッピングがない場合は元の名前を使用
        tile = st.container(border=True)
        tile.subheader(label)
        tile.markdown(f"### ¥ {amount:,.0f}")

def plot_monthly_balance_trend(preprocessed_kakeibo_df: pd.DataFrame, include_bonus: bool = True):
    """月別収支のトレンドをプロットする"""

    # 前処理済みのデータを使用
    df = preprocessed_kakeibo_df.copy()

    # 年月のカラムを追加
    df['year_month'] = df['date'].dt.to_period('M')

    if include_bonus:
        # 月ごとの収入と支出を集計
        monthly_summary = df.groupby('year_month').agg(
            total_income=('amount', lambda x: x[(df['is_salary'] | df['is_bonus'])].sum()),
            total_expense=('amount', lambda x: x[~(df['is_salary'] | df['is_bonus'])].sum())
        ).reset_index()

        income_label = '収入（賞与込み）'

        # 収支バランスを計算（収入 - 支出）
        monthly_summary['balance'] = monthly_summary['total_income'] + monthly_summary['total_expense']  # 支出は負の値なので加算

    else:
        # 月ごとの収入と支出を集計
        monthly_summary = df.groupby('year_month').agg(
            total_income=('amount', lambda x: x[df['is_salary']].sum()),
            total_expense=('amount', lambda x: x[~(df['is_salary'] | df['is_bonus'])].sum())
        ).reset_index()

        income_label = '収入（賞与なし）'

        # 収支バランスを計算（収入 - 支出）
        monthly_summary['balance'] = monthly_summary['total_income'] + monthly_summary['total_expense']  # 支出は負の値なので加算

    # 支出は正の値として表示するため、符号を反転（グラフ用）
    monthly_summary['total_expense_positive'] = -monthly_summary['total_expense']

    # year_monthをstring型に変換してソート
    monthly_summary['year_month_str'] = monthly_summary['year_month'].astype(str)
    monthly_summary['year_month_dt'] = monthly_summary['year_month'].dt.to_timestamp()
    monthly_summary = monthly_summary.sort_values('year_month_dt')

    income_expense_data = pd.melt(
        monthly_summary,
        id_vars=['year_month_str', 'year_month_dt'],
        value_vars=['total_income', 'total_expense_positive'],
        var_name='category',
        value_name='amount'
    )

    # カテゴリ名をわかりやすく変更
    category_mapping = {
        'total_income': income_label,
        'total_expense_positive': '支出'
    }

    income_expense_data['category'] = income_expense_data['category'].map(category_mapping)

    # 棒グラフ作成（グループ化された棒グラフ）
    bar_chart = alt.Chart(income_expense_data).mark_bar().encode(
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')), # X軸に年月を設定、年月でソート
        y=alt.Y('amount:Q', title='金額（円）'), # Y軸に金額を設定
        xOffset='category:N', # カテゴリごとに棒を横にずらす（グループ化）
        # カテゴリ毎に色分け
        color=alt.Color(
            'category:N',
            scale=alt.Scale(
                domain=[income_label, '支出'],
                range=['lightblue', 'salmon']
            ),
            legend=alt.Legend(title='区分', orient="top")
        ),
        # マウスホバー時に表示される情報（ツールチップ）。
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('category:N', title='区分'),
            alt.Tooltip('amount:Q', title='金額（円）', format=',')
        ]
    ).properties(
        width=800,
        height=400,
    )

    # 収支バランス用のデータフレーム
    balance_data = monthly_summary[['year_month_str', 'year_month_dt', 'balance']]

    # 収支バランスの線グラフ作成
    line_chart = alt.Chart(balance_data).mark_line(
        point={
            'filled': True,  # ポイントを塗りつぶし
            'fill': 'yellow',  # ポイントの塗りつぶし色
            'stroke': 'green',  # ポイントの枠線の色
            'strokeWidth': 2,  # ポイントの枠線の太さ
            'size': 80  # ポイントのサイズ
        }, # データポイントを表示
        color='green',
        strokeWidth=2
    ).encode(
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')), # X軸に年月を設定、年月でソート
        y=alt.Y('balance:Q', title='収支バランス（円）', scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('balance:Q', title='収支バランス（円）', format=',')
        ]
    )

    # グラフの重ね合わせとスケール調整
    chart = alt.layer(
        bar_chart,
        line_chart
    ).properties(
        title=f'月別の収入・支出および収支バランスの推移：{income_label}と支出の比較'
    )

    st.altair_chart(chart, use_container_width=True)

def main():

    with st.spinner("家計簿データを取得中..."):
        kakeibo_data: pd.DataFrame = read_csv_files_from_s3(bucket_name=S3_BUCKET_NAME, prefix=S3_PREFIX)

    # 家計簿データの前処理
    preprocessed_kakeibo_data: pd.DataFrame = preprocess_data(kakeibo_data)

    # 家計簿データの期間を表示
    display_kakeibo_data_range(preprocessed_kakeibo_data)

    st.header("サマリー")

    # 総収入と総支出を表示
    display_total_income_expense(preprocessed_kakeibo_data)

    display_average_income_expense(preprocessed_kakeibo_data)

    st.header("グラフ")

    # 月別収支推移のグラフを表示（賞与込み）
    plot_monthly_balance_trend(preprocessed_kakeibo_data)

    # 月別収支推移のグラフを表示（賞与なし）
    plot_monthly_balance_trend(preprocessed_kakeibo_data, include_bonus=False)

main()
