# 📁 main.py (전체 통합: 자산 요약, 자산 분포, 자산 추이, 종목 관리, 매도 내역 포함)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime

st.set_page_config(layout="wide")

# DB 연결
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# 테이블 생성
cursor.execute('''
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    ticker TEXT,
    quantity INTEGER,
    buy_price INTEGER,
    account TEXT,
    buy_date TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS sold_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    ticker TEXT,
    quantity INTEGER,
    buy_price INTEGER,
    sell_price INTEGER,
    account TEXT,
    sell_date TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT,
    total_buy INTEGER,
    total_eval INTEGER,
    total_return REAL
)
''')

conn.commit()

# 데이터 불러오기
df = pd.read_sql("SELECT * FROM stocks", conn)
sold_df = pd.read_sql("SELECT * FROM sold_stocks", conn)

# 현재가 mock
if not df.empty:
    df["current_price"] = df["ticker"].apply(lambda x: 100000 + hash(x) % 100000)
    df["eval"] = df["quantity"] * df["current_price"]
    df["buy_total"] = df["quantity"] * df["buy_price"]
    df["return"] = ((df["eval"] - df["buy_total"]) / df["buy_total"]) * 100
    df["return_won"] = df["eval"] - df["buy_total"]

# 자동 히스토리 기록
today = datetime.today().strftime("%Y-%m-%d")
history_df = pd.read_sql("SELECT * FROM history", conn)

if not history_df[history_df['record_date'] == today].empty:
    pass
elif not df.empty:
    total_buy = df["buy_total"].sum()
    total_eval = df["eval"].sum()
    total_return = ((total_eval - total_buy) / total_buy) * 100 if total_buy else 0
    cursor.execute("INSERT INTO history (record_date, total_buy, total_eval, total_return) VALUES (?, ?, ?, ?)",
                   (today, total_buy, total_eval, total_return))
    conn.commit()

# 메뉴
menu = st.sidebar.selectbox("탭 선택", ["📊 자산 요약", "📈 자산 추이", "📌 자산 분포", "🧾 종목 관리", "📉 매도 내역"])

# -------------------- 1. 자산 요약 --------------------
if menu == "📊 자산 요약":
    st.header("📊 자산 요약")
    total_eval = int(df["eval"].sum()) if not df.empty else 0
    total_buy = int(df["buy_total"].sum()) if not df.empty else 0
    total_return = (total_eval - total_buy) / total_buy * 100 if total_buy else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("총 매입금액", f"{total_buy:,.0f}₩")
    col2.metric("총 평가금액", f"{total_eval:,.0f}₩")
    col3.metric("총 수익률", f"{total_return:.2f}%")

    st.markdown("---")
    st.subheader("📊 계좌별 수익률 요약")

    if not df.empty:
        account_grouped = df.groupby("account").agg({"eval": "sum", "buy_total": "sum"}).reset_index()
        account_grouped["return_rate"] = ((account_grouped["eval"] - account_grouped["buy_total"]) / account_grouped["buy_total"]) * 100
        account_grouped["return_won"] = account_grouped["eval"] - account_grouped["buy_total"]
        bar_colors = ["red" if r >= 0 else "blue" for r in account_grouped["return_rate"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=account_grouped["account"],
            x=account_grouped["return_rate"],
            orientation='h',
            marker_color=bar_colors,
            text=[f"{int(ret):,}₩" for ret in account_grouped["return_won"]],
            textposition="outside"
        ))
        fig.update_layout(xaxis_title="수익률 (%)", yaxis_title="계좌", height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("보유 종목 데이터가 없습니다.")

# -------------------- 2. 자산 추이 --------------------
elif menu == "📈 자산 추이":
    st.header("📈 자산 추이 분석")
    history_df = pd.read_sql("SELECT * FROM history ORDER BY record_date DESC", conn)

    if not history_df.empty:
        # 총 평가금 + 수익률 이중축
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=history_df['record_date'], y=history_df['total_eval'], mode='lines+markers', name='총 평가금액', yaxis='y1'))
        fig.add_trace(go.Scatter(x=history_df['record_date'], y=history_df['total_return'], mode='lines+markers', name='총 수익률(%)', yaxis='y2'))

        fig.update_layout(
            yaxis=dict(title='총 평가금액', side='left'),
            yaxis2=dict(title='총 수익률 (%)', overlaying='y', side='right'),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📄 자산 추이 표")
        st.dataframe(history_df.sort_values("record_date", ascending=False), use_container_width=True)
    else:
        st.info("자산 추이 데이터가 없습니다.")

# -------------------- 3. 자산 분포 --------------------
elif menu == "📌 자산 분포":
    st.header("📌 종목별 비중 및 계좌 요약")

    if not df.empty:
        pie_df = df.copy()
        pie_df["평가금액"] = pie_df["eval"]
        fig = px.pie(pie_df, values="평가금액", names="name", title="📊 종목별 비중 (평가금 기준)", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 📋 계좌별 요약")
        accounts = df["account"].unique()
        summary_data = {
            "항목": ["매입금액", "평가금액", "수익률"]
        }
        for acc in accounts:
            sub = df[df["account"] == acc]
            b = sub["buy_total"].sum()
            e = sub["eval"].sum()
            r = (e - b) / b * 100 if b else 0
            summary_data[acc] = [int(b), int(e), f"{r:.2f}%"]

        total_b = df["buy_total"].sum()
        total_e = df["eval"].sum()
        total_r = (total_e - total_b) / total_b * 100 if total_b else 0
        summary_data["총합계"] = [int(total_b), int(total_e), f"{total_r:.2f}%"]
        st.dataframe(pd.DataFrame(summary_data))

        st.markdown("### 📑 종목 상세")
        df_show = df[["account", "ticker", "name", "quantity", "current_price", "buy_price", "eval", "buy_total", "return", "return_won"]]
        df_show.columns = ["증권사", "티커", "종목명", "수량", "현재가", "매입가", "평가금", "매입금", "수익률", "손익"]
        st.dataframe(df_show, use_container_width=True)
    else:
        st.warning("보유 종목 데이터가 없습니다.")

# -------------------- 4. 종목 관리 --------------------
elif menu == "🧾 종목 관리":
    st.header("📥 종목 추가")
    with st.form("add_stock"):
        name = st.text_input("종목명")
        ticker = st.text_input("티커")
        quantity = st.number_input("수량", min_value=1, step=1)
        buy_price = st.number_input("매입금액(₩)", min_value=1, step=100)
        account = st.selectbox("계좌", ["미래에셋", "키움", "삼성", "나무", "업비트"])
        submitted = st.form_submit_button("➕ 추가하기")
        if submitted:
            if not name or not ticker or quantity <= 0 or buy_price <= 0 or not account:
                st.warning("⚠️ 모든 항목을 입력해주세요!")
            else:
                buy_date = datetime.today().strftime("%Y-%m-%d")
                cursor.execute("INSERT INTO stocks (name, ticker, quantity, buy_price, account, buy_date) VALUES (?, ?, ?, ?, ?, ?)",
                               (name, ticker, quantity, buy_price, account, buy_date))
                conn.commit()
                st.success(f"✅ {name} 종목이 추가되었습니다.")
                st.experimental_rerun()

    st.markdown("---")
    st.subheader("📋 보유 종목 목록")
    if not df.empty:
        df_show = df[["account", "ticker", "name", "quantity", "current_price", "buy_price", "eval", "buy_total", "return", "return_won"]]
        df_show.columns = ["증권사", "티커", "종목명", "수량", "현재가", "매입가", "평가금", "매입금", "수익률", "손익"]
        st.dataframe(df_show, use_container_width=True)

        selected = st.selectbox("📤 매도할 종목 선택", df["name"])
        if selected:
            selected_row = df[df["name"] == selected].iloc[0]
            with st.form("sell_form"):
                sell_price = st.number_input("매도가(₩)", min_value=1, step=100)
                sell_quantity = st.number_input("매도 수량", min_value=1, max_value=selected_row["quantity"], step=1)
                confirm_sell = st.form_submit_button("💸 매도 처리")
                if confirm_sell:
                    if sell_price <= 0 or sell_quantity <= 0:
                        st.warning("⚠️ 매도 수량과 가격을 모두 입력해주세요!")
                    else:
                        cursor.execute("DELETE FROM stocks WHERE id = ?", (selected_row["id"],))
                        cursor.execute("INSERT INTO sold_stocks (name, ticker, quantity, buy_price, sell_price, account, sell_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                       (selected_row["name"], selected_row["ticker"], sell_quantity, selected_row["buy_price"], sell_price, selected_row["account"], datetime.today().strftime("%Y-%m-%d")))
                        conn.commit()
                        st.success(f"✅ {selected} 종목 매도 완료")
                        st.experimental_rerun()
    else:
        st.info("ℹ️ 아직 등록된 종목이 없습니다.")

# -------------------- 5. 매도 내역 --------------------
elif menu == "📉 매도 내역":
    st.header("📉 매도 종목 기록")
    if not sold_df.empty:
        sold_df["손익"] = (sold_df["sell_price"] - sold_df["buy_price"]) * sold_df["quantity"]
        sold_df["수익률"] = ((sold_df["sell_price"] - sold_df["buy_price"]) / sold_df["buy_price"]) * 100
        show_df = sold_df[["account", "name", "ticker", "quantity", "buy_price", "sell_price", "손익", "수익률", "sell_date"]]
        show_df.columns = ["계좌", "종목명", "티커", "수량", "매입가", "매도가", "손익", "수익률", "매도일"]
        st.dataframe(show_df.sort_values("매도일", ascending=False), use_container_width=True)
    else:
        st.info("ℹ️ 매도된 종목이 아직 없습니다.")

conn.close()
