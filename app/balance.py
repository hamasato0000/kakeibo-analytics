import pandas as pd
import streamlit as st
import os
from datetime import datetime
import altair as alt
from dotenv import load_dotenv
import s3_utils

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

    # 「収入」カテゴリの分類
    df['is_salary'] = df['major_category'].str.contains('収入') & df['minor_category'].str.contains('給与')
    df['is_bonus'] = df['major_category'].str.contains('収入') & df['minor_category'].str.contains('一時所得')
    df['is_other_income'] = df['major_category'].str.contains('収入') & ~(df['minor_category'].str.contains('給与') | df['minor_category'].str.contains('一時所得'))

    # 計算対象外のものは削除
    df = df[df['is_target'] == 1]

    # 振替対象のものは削除
    df = df[df['is_transfer'] == 0]

    return df

def summarize_monthly_kakeibo_data(preprocessed_kakeibo_df: pd.DataFrame) -> pd.DataFrame:
    """月単位の家計簿データを集計する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    :return: 月別集計した家計簿データ
    :rtype: pd.DataFrame
    """

    df = preprocessed_kakeibo_df.copy()

    # 月別で集計するため、年月のカラムを追加
    df['year_month'] = df['date'].dt.to_period('M')

    income_only_salary_df = df[df['is_salary']]
    income_with_others_df = df[df['is_salary'] | df['is_bonus'] | df['is_other_income']]
    expense_df = df[~(df['is_salary'] | df['is_bonus'] | df['is_other_income'])]

    # 月別集計
    monthly_summary = pd.DataFrame({
        'income_only_salary': income_only_salary_df.groupby('year_month')['amount'].sum(),
        'income_with_others': income_with_others_df.groupby('year_month')['amount'].sum(),
        'expense': expense_df.groupby('year_month')['amount'].sum(),
    }).reset_index()

    monthly_summary['balance_only_salary'] = monthly_summary['income_only_salary'] + monthly_summary['expense']
    monthly_summary['balance_with_others'] = monthly_summary['income_with_others'] + monthly_summary['expense']

    return monthly_summary


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

def display_summaries(monthly_kakeibo_summary: pd.DataFrame, preprocessed_kakeibo_df: pd.DataFrame):
    """収支サマリーを3列レイアウトで表示する

    :param monthly_kakeibo_summary: 月別の家計簿集計データ
    :type monthly_kakeibo_summary: pd.DataFrame
    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    """
    # 総収入の計算
    total_income_only_salary = monthly_kakeibo_summary['income_only_salary'].sum()
    total_income_with_others = monthly_kakeibo_summary['income_with_others'].sum()

    # 総支出の計算
    total_expense = monthly_kakeibo_summary['expense'].sum()

    # 総収支バランスの計算
    total_balance_only_salary = total_income_only_salary + total_expense
    total_balance_with_others = total_income_with_others + total_expense

    # 月平均を算出
    monthly_avg = monthly_kakeibo_summary[['income_only_salary', 'income_with_others', 'expense', 'balance_only_salary', 'balance_with_others']].mean()
    monthly_avg = monthly_avg.round(0).astype(int)

    # データ期間情報を取得
    start_date, end_date = get_kakeibo_data_range(preprocessed_kakeibo_df)
    months_count = len(monthly_kakeibo_summary)

    # 指標を3列で表示
    col1, col2, col3 = st.columns(3)

    with col1:
        # 収入関連の指標
        st.markdown("### 💰 収入")

        income_metrics = [
            {"title": "総収入", "value": total_income_with_others},
            {"title": "総収入（給与のみ）", "value": total_income_only_salary},
            {"title": "月平均収入", "value": monthly_avg['income_with_others']},
            {"title": "月平均収入（給与のみ）", "value": monthly_avg['income_only_salary']}
        ]

        for metric in income_metrics:
            con = st.container(border=True)
            con.markdown(f"**{metric['title']}**")
            con.markdown(f"### :blue[¥ {metric['value']:,.0f}]")

    with col2:
        # 支出関連の指標
        st.markdown("### 💸 支出")

        expense_metrics = [
            {"title": "総支出", "value": -total_expense},
            {"title": "月平均支出", "value": -monthly_avg['expense']}
        ]

        for metric in expense_metrics:
            con = st.container(border=True)
            con.markdown(f"**{metric['title']}**")
            con.markdown(f"### :red[¥ {metric['value']:,.0f}]")

    with col3:
        # 収支バランス関連の指標
        st.markdown("### 📊 収支バランス")

        balance_metrics = [
            {"title": "総収支バランス", "value": total_balance_with_others},
            {"title": "総収支バランス（給与のみ）", "value": total_balance_only_salary},
            {"title": "月平均収支バランス", "value": monthly_avg['balance_with_others']},
            {"title": "月平均収支バランス（給与のみ）", "value": monthly_avg['balance_only_salary']}
        ]

        for metric in balance_metrics:
            con = st.container(border=True)
            con.markdown(f"**{metric['title']}**")
            if metric['value'] >= 0:
                con.markdown(f"### :green[¥ {metric['value']:,.0f}]")
            else:
                con.markdown(f"### :orange[¥ {metric['value']:,.0f}]")

    # データ期間情報を表示
    st.info(f"📅 **データ期間:** {start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%Y/%m/%d')} （{months_count}ヶ月）")

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

        income_label = '収入'

        # 収支バランスを計算（収入 - 支出）
        monthly_summary['balance'] = monthly_summary['total_income'] + monthly_summary['total_expense']  # 支出は負の値なので加算

    else:
        # 月ごとの収入と支出を集計
        monthly_summary = df.groupby('year_month').agg(
            total_income=('amount', lambda x: x[df['is_salary']].sum()),
            total_expense=('amount', lambda x: x[~(df['is_salary'] | df['is_bonus'])].sum())
        ).reset_index()

        income_label = '収入（給与のみ）'

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
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')),
        y=alt.Y('amount:Q', title='金額（円）'),
        xOffset='category:N',
        color=alt.Color(
            'category:N',
            scale=alt.Scale(
                domain=[income_label, '支出'],
                range=['#5470c6', '#ff7f7f']
            ),
            legend=alt.Legend(title='区分', orient="top")
        ),
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
            'filled': True,
            'fill': 'yellow',
            'stroke': '#91cc75',
            'strokeWidth': 2,
            'size': 80
        },
        color='#91cc75',
        strokeWidth=2
    ).encode(
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')),
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
        title=f'月別の{income_label}・支出および収支バランスの推移'
    )

    st.altair_chart(chart, use_container_width=True)

def main():
    st.set_page_config(
        page_title="収支分析",
        page_icon="💰",
        layout="wide"
    )

    st.title("💰 収支分析")

    with st.spinner("家計簿データを取得中..."):
        kakeibo_data: pd.DataFrame = s3_utils.read_csv_files_from_s3(bucket_name=S3_BUCKET_NAME, prefix=S3_PREFIX)

    # 家計簿データの前処理
    preprocessed_kakeibo_data: pd.DataFrame = preprocess_kakeibo_data(kakeibo_data)

    # 月単位のデータ集計
    monthly_kakeibo_summary: pd.DataFrame = summarize_monthly_kakeibo_data(preprocessed_kakeibo_data)

    st.header("📈 サマリー")

    # サマリーを表示
    display_summaries(monthly_kakeibo_summary, preprocessed_kakeibo_data)

    st.header("📊 グラフ")

    # 月別収支推移のグラフを表示（賞与込み）
    plot_monthly_balance_trend(preprocessed_kakeibo_data)

    # 月別収支推移のグラフを表示（賞与なし）
    plot_monthly_balance_trend(preprocessed_kakeibo_data, include_bonus=False)

    # 詳細データを表示
    st.header("📋 詳細データ")
    with st.expander("月別収支データ", expanded=False):
        # データを見やすく整形
        display_df = monthly_kakeibo_summary.copy()
        display_df['year_month'] = display_df['year_month'].astype(str)
        display_df = display_df.rename(columns={
            'year_month': '年月',
            'income_only_salary': '収入（給与のみ）（円）',
            'income_with_others': '収入（賞与込み）（円）',
            'expense': '支出（円）',
            'balance_only_salary': '収支バランス（給与のみ）（円）',
            'balance_with_others': '収支バランス（賞与込み）（円）'
        })
        st.dataframe(display_df, use_container_width=True)

main()
