import streamlit as st
import pandas as pd
import s3_utils
import os
from datetime import datetime
import altair as alt
from dotenv import load_dotenv

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
    df['is_income'] = df['major_category'].str.contains('収入')

    # 固定費と変動費の分類
    # 固定費の例：家賃、サブスクリプション、保険料など
    fixed_cost_keywords = ['家賃', '保険', '通信', '固定費', 'サブスク', '定期購入', '会費', '支払い']

    # 固定費フラグの作成
    df['is_fixed_cost'] = False

    # キーワードマッチングで固定費を判定
    for keyword in fixed_cost_keywords:
        df['is_fixed_cost'] = df['is_fixed_cost'] | df['description'].str.contains(keyword, na=False) | \
                              df['minor_category'].str.contains(keyword, na=False) | \
                              df['major_category'].str.contains(keyword, na=False)

    # 変動費フラグの作成（収入でなく、固定費でもないものを変動費と分類）
    df['is_variable_cost'] = ~df['is_income'] & ~df['is_fixed_cost']

    # 計算対象外のものは削除
    df = df[df['is_target'] == 1]

    # 振替対象のものは削除
    df = df[df['is_transfer'] == 0]

    return df

def summarize_monthly_fixed_variable_costs(preprocessed_kakeibo_df: pd.DataFrame) -> pd.DataFrame:
    """月単位の固定費と変動費を集計する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    :return: 月別集計した固定費・変動費データ
    :rtype: pd.DataFrame
    """
    df = preprocessed_kakeibo_df.copy()

    # 月別で集計するため、年月のカラムを追加
    df['year_month'] = df['date'].dt.to_period('M')

    # 収入データを除外（支出だけを集計）
    expense_df = df[~df['is_income']]

    # 固定費と変動費のデータを分離
    fixed_cost_df = expense_df[expense_df['is_fixed_cost']]
    variable_cost_df = expense_df[expense_df['is_variable_cost']]

    # 月別集計
    monthly_summary = pd.DataFrame({
        'fixed_cost': -fixed_cost_df.groupby('year_month')['amount'].sum(),  # 支出は負の値なので正に変換
        'variable_cost': -variable_cost_df.groupby('year_month')['amount'].sum(),  # 支出は負の値なので正に変換
    }).reset_index()

    # 合計列を追加
    monthly_summary['total_cost'] = monthly_summary['fixed_cost'] + monthly_summary['variable_cost']
    monthly_summary['fixed_cost_ratio'] = (monthly_summary['fixed_cost'] / monthly_summary['total_cost'] * 100).round(1)
    monthly_summary['variable_cost_ratio'] = (monthly_summary['variable_cost'] / monthly_summary['total_cost'] * 100).round(1)

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

def display_kakeibo_data_range(preprocessed_kakeibo_df: pd.DataFrame):
    """
    家計簿データの期間を表示する

    :param preprocessed_kakeibo_df: 前処理済みの家計簿データ
    :type preprocessed_kakeibo_df: pd.DataFrame
    """

    # 家計簿データの期間を取得
    start_date, end_date = get_kakeibo_data_range(preprocessed_kakeibo_df)
    st.markdown(f":gray[家計簿データの期間：{start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%Y/%m/%d')}]")

def display_cost_summaries(monthly_cost_summary: pd.DataFrame):
    """固定費と変動費の集計結果を表示する

    :param monthly_cost_summary: 月別の固定費・変動費集計データ
    :type monthly_cost_summary: pd.DataFrame
    """
    # 総固定費の計算
    total_fixed_cost = monthly_cost_summary['fixed_cost'].sum()

    # 総変動費の計算
    total_variable_cost = monthly_cost_summary['variable_cost'].sum()

    # 総支出の計算
    total_cost = total_fixed_cost + total_variable_cost

    # 月平均を算出
    monthly_avg = monthly_cost_summary[['fixed_cost', 'variable_cost', 'total_cost']].mean()
    monthly_avg = monthly_avg.round(0).astype(int)

    # 全期間の固定費率と変動費率
    fixed_cost_ratio = round(total_fixed_cost / total_cost * 100, 1)
    variable_cost_ratio = round(total_variable_cost / total_cost * 100, 1)

    # 表示する指標を辞書で定義
    metrics = [
        {"title": "総固定費", "value": total_fixed_cost, "category": "fixed"},
        {"title": "総変動費", "value": total_variable_cost, "category": "variable"},
        {"title": "総支出", "value": total_cost, "category": "total"},
        {"title": "月平均固定費", "value": monthly_avg['fixed_cost'], "category": "fixed"},
        {"title": "月平均変動費", "value": monthly_avg['variable_cost'], "category": "variable"},
        {"title": "月平均支出", "value": monthly_avg['total_cost'], "category": "total"},
        {"title": f"固定費率", "value": f"{fixed_cost_ratio}%", "category": "ratio"},
        {"title": f"変動費率", "value": f"{variable_cost_ratio}%", "category": "ratio"},
    ]

    # 必要な行数を計算（2列の場合）
    num_rows = (len(metrics) + 1) // 2

    # 指標を動的に表示
    for i in range(num_rows):
        row = st.columns(2)
        for j in range(2):
            idx = i * 2 + j
            if idx < len(metrics):
                metric = metrics[idx]
                with row[j]:
                    con = st.container(border=True)
                    con.markdown(f"##### {metric['title']}")

                    if metric['category'] == 'ratio':
                        con.markdown(f"#### {metric['value']}")
                    else:
                        con.markdown(f"#### :blue[¥ {metric['value']:,.0f}]")

def plot_monthly_fixed_variable_costs(monthly_cost_summary: pd.DataFrame):
    """月別の固定費と変動費の推移をグラフ表示する

    :param monthly_cost_summary: 月別の固定費・変動費集計データ
    :type monthly_cost_summary: pd.DataFrame
    """
    # year_monthをstring型に変換してソート
    df = monthly_cost_summary.copy()
    df['year_month_str'] = df['year_month'].astype(str)
    df['year_month_dt'] = df['year_month'].dt.to_timestamp()
    df = df.sort_values('year_month_dt')

    # 積み上げ棒グラフ用のデータを準備
    stacked_data = pd.melt(
        df,
        id_vars=['year_month_str', 'year_month_dt'],
        value_vars=['fixed_cost', 'variable_cost'],
        var_name='cost_type',
        value_name='amount'
    )

    # カテゴリ名をわかりやすく変更
    category_mapping = {
        'fixed_cost': '固定費',
        'variable_cost': '変動費'
    }

    stacked_data['cost_type'] = stacked_data['cost_type'].map(category_mapping)

    # 積み上げ棒グラフ作成
    bar_chart = alt.Chart(stacked_data).mark_bar().encode(
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')),
        y=alt.Y('amount:Q', title='金額（円）', stack=True),
        color=alt.Color(
            'cost_type:N',
            scale=alt.Scale(
                domain=['固定費', '変動費'],
                range=['#5470c6', '#91cc75']
            ),
            legend=alt.Legend(title='費用タイプ', orient="top")
        ),
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('cost_type:N', title='費用タイプ'),
            alt.Tooltip('amount:Q', title='金額（円）', format=',')
        ]
    ).properties(
        width=800,
        height=400,
        title='月別の固定費と変動費の推移'
    )

    # 総額の線グラフ
    total_line = alt.Chart(df).mark_line(
        point={
            'filled': True,
            'fill': 'yellow',
            'stroke': 'darkred',
            'strokeWidth': 2,
            'size': 80
        },
        color='darkred',
        strokeWidth=2
    ).encode(
        x=alt.X('year_month_str:N', sort=alt.EncodingSortField(field='year_month_dt')),
        y=alt.Y('total_cost:Q', title='合計金額（円）'),
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('total_cost:Q', title='合計金額（円）', format=',')
        ]
    )

    # グラフを重ね合わせて表示
    chart = alt.layer(
        bar_chart,
        total_line
    ).resolve_scale(
        y='independent'  # 線グラフと棒グラフのスケールを独立させる
    )

    st.altair_chart(chart, use_container_width=True)

def plot_fixed_variable_cost_ratio(monthly_cost_summary: pd.DataFrame):
    """月別の固定費率と変動費率の推移をグラフ表示する

    :param monthly_cost_summary: 月別の固定費・変動費集計データ
    :type monthly_cost_summary: pd.DataFrame
    """
    # year_monthをstring型に変換してソート
    df = monthly_cost_summary.copy()
    df['year_month_str'] = df['year_month'].astype(str)
    df['year_month_dt'] = df['year_month'].dt.to_timestamp()
    df = df.sort_values('year_month_dt')

    # 比率のグラフ用データを準備
    ratio_data = pd.melt(
        df,
        id_vars=['year_month_str', 'year_month_dt'],
        value_vars=['fixed_cost_ratio', 'variable_cost_ratio'],
        var_name='ratio_type',
        value_name='percentage'
    )

    # カテゴリ名をわかりやすく変更
    ratio_mapping = {
        'fixed_cost_ratio': '固定費率',
        'variable_cost_ratio': '変動費率'
    }

    ratio_data['ratio_type'] = ratio_data['ratio_type'].map(ratio_mapping)

    # 折れ線グラフ作成
    ratio_chart = alt.Chart(ratio_data).mark_line(
        point={
            'filled': True,
            'size': 80
        },
        strokeWidth=2
    ).encode(
        x=alt.X('year_month_str:N', title='年月', sort=alt.EncodingSortField(field='year_month_dt')),
        y=alt.Y('percentage:Q', title='比率（%）', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color(
            'ratio_type:N',
            scale=alt.Scale(
                domain=['固定費率', '変動費率'],
                range=['#5470c6', '#91cc75']
            ),
            legend=alt.Legend(title='費用比率', orient="top")
        ),
        tooltip=[
            alt.Tooltip('year_month_str:N', title='年月'),
            alt.Tooltip('ratio_type:N', title='費用比率'),
            alt.Tooltip('percentage:Q', title='比率（%）', format='.1f')
        ]
    ).properties(
        width=800,
        height=300,
        title='月別の固定費率と変動費率の推移'
    )

    st.altair_chart(ratio_chart, use_container_width=True)

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

    # 家計簿データの前処理
    preprocessed_kakeibo_data: pd.DataFrame = preprocess_kakeibo_data(kakeibo_data)

    # 月単位のデータ集計
    monthly_cost_summary: pd.DataFrame = summarize_monthly_fixed_variable_costs(preprocessed_kakeibo_data)

    # 家計簿データの期間を表示
    display_kakeibo_data_range(preprocessed_kakeibo_data)

    st.header("固定費・変動費のサマリー")

    # サマリーを表示
    display_cost_summaries(monthly_cost_summary)

    st.header("グラフ")

    # 固定費と変動費の月別推移グラフを表示
    plot_monthly_fixed_variable_costs(monthly_cost_summary)

    # 固定費率と変動費率の月別推移グラフを表示
    plot_fixed_variable_cost_ratio(monthly_cost_summary)

    # 詳細データを表示
    st.header("詳細データ")
    with st.expander("月別固定費・変動費データ", expanded=False):
        st.dataframe(monthly_cost_summary, use_container_width=True)

main()
