# 📁 main.py (최적화 통합 버전 + 종목 입력 폼 및 오류 수정 포함)

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime

# ---------------- DB 초기 연결 ------------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# ---------------- 테이블 생성 (최초 1회) ------------------
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
    quantity INTEGER,
    buy_price INTEGER,
    sell_price INTEGER,
    sell_date TEXT,
    account TEXT
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

# ---------------- 데이터 로드 ------------------
df = pd.read_sql("SELECT * FROM stocks", conn)
sold_df = pd.read_sql("SELECT * FROM sold_stocks", conn)

# ---------------- 현재가 mock ------------------
def get_current_price(ticker):
    return 100000 + hash(ticker) % 100000

if not df.empty and "ticker" in df.columns:
    df["current_price"] = df["ticker"].apply(get_current_price)
    df["eval"] = df["quantity"] * df["current_price"]
    df["buy_total"] = df["quantity"] * df["buy_price"]
    df["return"] = ((df["eval"] - df["buy_total"]) / df["buy_total"]) * 100
else:
    df["current_price"] = []
    df["eval"] = []
    df["buy_total"] = []
    df["return"] = []

# ---------------- UI ------------------
st.set_page_config(layout="wide")
st.title("📊 자산 대시보드")

menu = st.sidebar.selectbox("탭을 선택하세요", ["메인", "계좌별", "리포트", "히스토리", "백업 데이터", "종목 추가"])

# ---------------- [1] 메인 ------------------
if menu == "메인":
    st.header("📌 총자산 현황")

    total_eval = int(df["eval"].sum()) if not df.empty else 0
    total_buy = int(df["buy_total"].sum()) if not df.empty else 0
    total_return = (total_eval - total_buy) / total_buy * 100 if total_buy else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("총 매입금액", f"{total_buy:,.0f}₩")
    col2.metric("총 평가금액", f"{total_eval:,.0f}₩")
    col3.metric("총 수익률", f"{total_return:.1f}%")

    if not df.empty:
        st.subheader("📈 종목별 비중 (트리맵)")
        fig = px.treemap(df, path=["account", "name"], values="eval", title="트리맵")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📉 수익률 그래프")
        fig2 = px.bar(df, x="name", y="return", color="account", title="종목별 수익률")
        st.plotly_chart(fig2, use_container_width=True)

# ---------------- [2] 계좌별 ------------------
elif menu == "계좌별":
    st.header("📒 계좌별 상세 내역")
    accounts = df["account"].unique() if "account" in df.columns else []

    if len(accounts) == 0:
        st.warning("등록된 계좌가 없습니다.")
    else:
        for acc in accounts:
            st.subheader(f"📂 {acc} 계좌")
            acc_df = df[df["account"] == acc]
            acc_df_show = acc_df[["name", "quantity", "buy_price", "current_price", "eval", "return"]]
            acc_df_show.columns = ["종목명", "수량", "매입가", "현재가", "평가금액", "수익률"]
            st.dataframe(acc_df_show)

# ---------------- [3] 리포트 ------------------
elif menu == "리포트":
    st.header("📊 자산 리포트")
    if not df.empty:
        fig = px.pie(df, names="name", values="eval", hole=0.4, title="보유 종목 비중")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- [4] 히스토리 ------------------
elif menu == "히스토리":
    st.header("📆 히스토리 기록")
    today = datetime.today().strftime("%Y-%m-%d")

    total_eval = int(df["eval"].sum()) if not df.empty else 0
    total_buy = int(df["buy_total"].sum()) if not df.empty else 0
    total_return = (total_eval - total_buy) / total_buy * 100 if total_buy else 0

    if not pd.read_sql("SELECT * FROM history WHERE record_date = ?", conn, params=(today,)).shape[0]:
        cursor.execute("INSERT INTO history (record_date, total_buy, total_eval, total_return) VALUES (?, ?, ?, ?)",
                       (today, total_buy, total_eval, total_return))
        conn.commit()

    history_df = pd.read_sql("SELECT * FROM history", conn)
    st.line_chart(history_df.set_index("record_date")["total_return"])

# ---------------- [5] 백업 데이터 ------------------
elif menu == "백업 데이터":
    st.header("📁 수동 백업용 테이블")
    st.info("데이터 보호를 위해 별도 CSV 업로드 or 수동 입력 가능")

# ---------------- [6] 종목 추가 ------------------
elif menu == "종목 추가":
    st.header("📝 종목 추가")
    with st.form("add_stock"):
        name = st.text_input("종목명")
        ticker = st.text_input("티커")
        quantity = st.number_input("수량", min_value=1, step=1)
        buy_price = st.number_input("매입가", min_value=1, step=100)
        account = st.selectbox("계좌", ["미래에셋", "키움", "삼성", "나무", "업비트"])
        submitted = st.form_submit_button("추가하기")

        if submitted:
            buy_date = datetime.today().strftime("%Y-%m-%d")
            cursor.execute("INSERT INTO stocks (name, ticker, quantity, buy_price, account, buy_date) VALUES (?, ?, ?, ?, ?, ?)",
                           (name, ticker, quantity, buy_price, account, buy_date))
            conn.commit()
            st.success(f"✅ {name} 종목이 성공적으로 추가되었습니다.")
            st.experimental_rerun()

# ---------------- END ------------------
conn.close()
