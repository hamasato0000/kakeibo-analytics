import streamlit as st
import pandas as pd
import s3_utils
import os
from datetime import datetime, timedelta
import altair as alt
from dotenv import load_dotenv
import numpy as np

# .envファイルから環境変数を読み込む
load_dotenv()

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = os.environ["S3_PREFIX"]

def preprocess_kakeibo_data(kakeibo_df: pd.DataFrame) -> pd.DataFrame:
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

    # 食費フラグの作成
    df['is_food'] = df['major_category'].str.contains('食費', na=False)

    # 計算対象外のものは削除
    df = df[df['is_target'] == 1]

    # 振替対象のものは削除
    df = df[df['is_transfer'] == 0]

    return df

def get_weekday_count_in_month(year: int, month: int) -> int:
    """指定された年月の平日数を算出する

    :param year: 年
    :type year: int
    :param month: 月
    :type month: int
    :return: 平日数（月曜日〜金曜日）
    :rtype: int
    """
    # 月の最初の日
    start_date = datetime(year, month, 1)

    # 次の月の最初の日を取得して、1日引いて月末を算出
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    weekday_count = 0
    current_date = start_date

    while current_date <= end_date:
        # 平日（月曜日=0 〜 金曜日=4）をカウント
        if current_date.weekday() < 5:
            weekday_count += 1
        current_date += timedelta(days=1)

    return weekday_count

def summarize_monthly_food_data(preprocessed_kakeibo_df: pd.DataFrame) -> pd.DataFrame:
    """月単位の食費データを小項目別に集計する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    :return: 月別集計した食費データ
    :rtype: pd.DataFrame
    """
    df = preprocessed_kakeibo_df.copy()

    # 食費のみを抽出
    food_df = df[df['is_food']].copy()

    # 月別で集計するため、年月のカラムを追加
    food_df['year_month'] = food_df['date'].dt.to_period('M')

    # 小項目別の月別集計
    monthly_food_summary = food_df.groupby(['year_month', 'minor_category'])['amount'].sum().reset_index()

    # 支出は負の値なので正に変換
    monthly_food_summary['amount'] = -monthly_food_summary['amount']

    # ピボットテーブルで月別・小項目別のマトリックスを作成
    pivot_summary = monthly_food_summary.pivot(index='year_month', columns='minor_category', values='amount').fillna(0)

    # カラム名を整理（存在する小項目のみ）
    food_categories = [col for col in pivot_summary.columns if col is not None]

    # DataFrameに戻す
    result_df = pivot_summary.reset_index()

    # 合計列を追加
    result_df['total_food'] = result_df[food_categories].sum(axis=1)

    return result_df

def calculate_workday_food_average(preprocessed_kakeibo_df: pd.DataFrame) -> pd.DataFrame:
    """食費-会の平日あたり平均を算出する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    :return: 月別の食費-会の平日あたり平均データ
    :rtype: pd.DataFrame
    """
    df = preprocessed_kakeibo_df.copy()

    # 食費-会のみを抽出
    work_food_df = df[(df['is_food']) & (df['minor_category'] == '食費-会')].copy()

    # 月別で集計するため、年月のカラムを追加
    work_food_df['year_month'] = work_food_df['date'].dt.to_period('M')

    # 月別の食費-会合計を算出
    monthly_work_food = work_food_df.groupby('year_month')['amount'].sum().reset_index()

    # 支出は負の値なので正に変換
    monthly_work_food['amount'] = -monthly_work_food['amount']

    # 各月の平日数を算出
    monthly_work_food['year'] = monthly_work_food['year_month'].dt.year
    monthly_work_food['month'] = monthly_work_food['year_month'].dt.month
    monthly_work_food['weekday_count'] = monthly_work_food.apply(
        lambda row: get_weekday_count_in_month(row['year'], row['month']), axis=1
    )

    # 平日あたり平均を算出
    monthly_work_food['daily_average'] = monthly_work_food['amount'] / monthly_work_food['weekday_count']
    monthly_work_food['daily_average'] = monthly_work_food['daily_average'].round(0)

    return monthly_work_food[['year_month', 'amount', 'weekday_count', 'daily_average']]

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

def display_food_summaries(monthly_food_summary: pd.DataFrame, workday_food_average: pd.DataFrame, preprocessed_kakeibo_df: pd.DataFrame):
    """食費の集計結果を表示する

    :param monthly_food_summary: 月別の食費集計データ
    :type monthly_food_summary: pd.DataFrame
    :param workday_food_average: 食費-会の平日あたり平均データ
    :type workday_food_average: pd.DataFrame
    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    """
    # 総食費の計算
    total_food_cost = monthly_food_summary['total_food'].sum()

    # 月平均を算出
    monthly_avg_food = monthly_food_summary['total_food'].mean()

    # 食費-会の統計
    if not workday_food_average.empty:
        total_work_food = workday_food_average['amount'].sum()
        avg_daily_work_food = workday_food_average['daily_average'].mean()
        total_weekdays = workday_food_average['weekday_count'].sum()
    else:
        total_work_food = 0
        avg_daily_work_food = 0
        total_weekdays = 0

    # データ期間情報を取得
    start_date, end_date = get_kakeibo_data_range(preprocessed_kakeibo_df)
    months_count = len(monthly_food_summary)

    # 指標を3列で表示
    col1, col2, col3 = st.columns(3)

    with col1:
        # 総食費関連の指標
        st.markdown("### 🍽️ 総食費")

        food_metrics = [
            {"title": "総食費", "value": total_food_cost},
            {"title": "月平均食費", "value": monthly_avg_food}
        ]

        for metric in food_metrics:
            con = st.container(border=True)
            con.markdown(f"**{metric['title']}**")
            con.markdown(f"### :green[¥ {metric['value']:,.0f}]")

    with col2:
        # 食費-会関連の指標
        st.markdown("### ☕ 食費-会")

        work_food_metrics = [
            {"title": "総食費-会", "value": total_work_food},
            {"title": "平日あたり平均", "value": avg_daily_work_food}
        ]

        for metric in work_food_metrics:
            con = st.container(border=True)
            con.markdown(f"**{metric['title']}**")
            con.markdown(f"### :blue[¥ {metric['value']:,.0f}]")

    with col3:
        # その他の指標
        st.markdown("### 📊 その他")

        other_metrics = [
            {"title": "総平日数", "value": f"{total_weekdays}日", "is_count": True},
            {"title": "食費-会の割合", "value": f"{(total_work_food/total_food_cost*100):.1f}%" if total_food_cost > 0 else "0%", "is_ratio": True}
        ]

        for metric in other_metrics:
            con = st.container(border=True)
            con.markdown(f"**{metric['title']}**")
            if metric.get('is_count') or metric.get('is_ratio'):
                con.markdown(f"### :orange[{metric['value']}]")
            else:
                con.markdown(f"### :orange[¥ {metric['value']:,.0f}]")

    # データ期間情報を表示
    st.info(f"📅 **データ期間:** {start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%Y/%m/%d')} （{months_count}ヶ月）")

def plot_monthly_food_trend(monthly_food_summary: pd.DataFrame):
    """月別の食費推移を小項目別の積み上げ棒グラフで表示する

    :param monthly_food_summary: 月別の食費集計データ
    :type monthly_food_summary: pd.DataFrame
    """
    # year_monthをstring型に変換してソート
    df = monthly_food_summary.copy()
    df['year_month_str'] = df['year_month'].astype(str)
    df['year_month_dt'] = df['year_month'].dt.to_timestamp()
    df = df.sort_values('year_month_dt')

    # 食費の小項目カラムを取得（year_month, year_month_str, year_month_dt, total_food以外）
    food_categories = [col for col in df.columns if col not in ['year_month', 'year_month_str', 'year_month_dt', 'total_food']]

    # 食費カテゴリを一定の順序でソート（安定化のため）
    food_categories = sorted(food_categories)

    # 積み上げ棒グラフ用のデータを準備
    stacked_data = pd.melt(
        df,
        id_vars=['year_month_str', 'year_month_dt'],
        value_vars=food_categories,
        var_name='food_category',
        value_name='amount'
    )

    # 0円のデータを除外（グラフを見やすくするため）
    stacked_data = stacked_data[stacked_data['amount'] > 0]

    # 色のパレットを定義
    color_palette = ['#ff7f7f', '#87ceeb', '#98d982', '#ffb347', '#dda0dd', '#f0e68c']

    # 積み上げ棒グラフ作成
    bar_chart = alt.Chart(stacked_data).mark_bar().encode(
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')),
        y=alt.Y('amount:Q', title='金額（円）', stack=True),
        color=alt.Color(
            'food_category:N',
            scale=alt.Scale(
                domain=food_categories,  # カテゴリの順序を明示的に指定
                range=color_palette
            ),
            legend=alt.Legend(title='食費カテゴリ', orient="top")
        ),
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('food_category:N', title='食費カテゴリ'),
            alt.Tooltip('amount:Q', title='金額（円）', format=',')
        ]
    ).properties(
        width=800,
        height=400,
        title='月別食費の推移（小項目別積み上げ）'
    )

    st.altair_chart(bar_chart, use_container_width=True)

def plot_workday_food_average_trend(workday_food_average: pd.DataFrame):
    """食費-会の平日あたり平均の推移をグラフ表示する

    :param workday_food_average: 食費-会の平日あたり平均データ
    :type workday_food_average: pd.DataFrame
    """
    if workday_food_average.empty:
        st.warning("食費-会のデータがありません。")
        return

    df = workday_food_average.copy()

    # year_monthでソートして、順序を保証
    df = df.sort_values('year_month')

    # year_monthをstring型に変換
    df['year_month_str'] = df['year_month'].astype(str)
    df['year_month_dt'] = df['year_month'].dt.to_timestamp()

    # 年月の順序を明示的に定義（時系列順）
    month_order = df['year_month_str'].tolist()

    # 折れ線グラフ作成
    line_chart = alt.Chart(df).mark_line(
        point={
            'filled': True,
            'fill': 'orange',
            'stroke': '#ff7f0e',
            'strokeWidth': 2,
            'size': 100
        },
        color='#ff7f0e',
        strokeWidth=3
    ).encode(
        x=alt.X(
            'year_month_str:N',
            title='年月',
            sort=month_order  # 明示的に順序を指定
        ),
        y=alt.Y('daily_average:Q', title='平日あたり食費-会（円）', scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('amount:Q', title='月合計（円）', format=','),
            alt.Tooltip('weekday_count:Q', title='平日数（日）'),
            alt.Tooltip('daily_average:Q', title='平日あたり平均（円）', format=',')
        ]
    ).properties(
        width=800,
        height=300,
        title='食費-会の平日あたり平均の推移'
    )

    st.altair_chart(line_chart, use_container_width=True)

def main():
    st.set_page_config(
        page_title="食費分析",
        page_icon="🍽️",
        layout="wide"
    )

    st.title("🍽️ 食費分析")

    with st.spinner("家計簿データを取得中..."):
        # S3からデータを取得
        kakeibo_data: pd.DataFrame = s3_utils.read_csv_files_from_s3(bucket_name=S3_BUCKET_NAME, prefix=S3_PREFIX)

    # 家計簿データの前処理
    preprocessed_kakeibo_data: pd.DataFrame = preprocess_kakeibo_data(kakeibo_data)

    # 食費データがあるかチェック
    food_data = preprocessed_kakeibo_data[preprocessed_kakeibo_data['is_food']]
    if food_data.empty:
        st.warning("食費のデータが見つかりません。")
        return

    # 月単位の食費データ集計
    monthly_food_summary: pd.DataFrame = summarize_monthly_food_data(preprocessed_kakeibo_data)

    # 食費-会の平日あたり平均を算出
    workday_food_average: pd.DataFrame = calculate_workday_food_average(preprocessed_kakeibo_data)

    st.header("📈 サマリー")

    # サマリーを表示
    display_food_summaries(monthly_food_summary, workday_food_average, preprocessed_kakeibo_data)

    st.header("📊 グラフ")

    # 月別食費推移グラフ（小項目別積み上げ）を表示
    plot_monthly_food_trend(monthly_food_summary)

    # 食費-会の平日あたり平均推移グラフを表示
    plot_workday_food_average_trend(workday_food_average)

    # 詳細データを表示
    st.header("📋 詳細データ")

    with st.expander("月別食費データ", expanded=False):
        # データを見やすく整形
        display_df = monthly_food_summary.copy()
        display_df['year_month'] = display_df['year_month'].astype(str)

        # カラム名を日本語に変更
        column_rename = {'year_month': '年月', 'total_food': '食費合計（円）'}
        food_categories = [col for col in display_df.columns if col not in ['year_month', 'total_food']]
        for cat in food_categories:
            column_rename[cat] = f'{cat}（円）'

        display_df = display_df.rename(columns=column_rename)
        st.dataframe(display_df, use_container_width=True)

    if not workday_food_average.empty:
        with st.expander("食費-会の平日あたり平均データ", expanded=False):
            # データを見やすく整形
            workday_display_df = workday_food_average.copy()
            workday_display_df['year_month'] = workday_display_df['year_month'].astype(str)
            workday_display_df = workday_display_df.rename(columns={
                'year_month': '年月',
                'amount': '食費-会 月合計（円）',
                'weekday_count': '平日数（日）',
                'daily_average': '平日あたり平均（円）'
            })
            st.dataframe(workday_display_df, use_container_width=True)

main()
