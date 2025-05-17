import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# DB 연결
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# 테이블 생성
cursor.execute("""
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    quantity INTEGER,
    buy_price REAL,
    current_price REAL,
    created_at TEXT
)
""")
conn.commit()

# 제목
st.title("📈 나만의 포트폴리오 대시보드")

# 종목 입력 폼
with st.form("stock_form"):
    name = st.text_input("종목명 (예: 삼성전자)")
    quantity = st.number_input("보유 수량", min_value=0, step=1)
    buy_price = st.number_input("매입가", min_value=0.0, step=1.0)
    current_price = st.number_input("현재가", min_value=0.0, step=1.0)
    submitted = st.form_submit_button("종목 추가")

    if submitted and name:
        cursor.execute("INSERT INTO stocks (name, quantity, buy_price, current_price, created_at) VALUES (?, ?, ?, ?, ?)", 
                       (name, quantity, buy_price, current_price, datetime.now().isoformat()))
        conn.commit()
        st.success(f"{name} 추가 완료!")

# 저장된 종목 보여주기
df = pd.read_sql_query("SELECT * FROM stocks", conn)

if not df.empty:
    df["총 매입금액"] = df["quantity"] * df["buy_price"]
    df["총 평가금액"] = df["quantity"] * df["current_price"]
    df["수익금"] = df["총 평가금액"] - df["총 매입금액"]
    df["수익률 (%)"] = (df["수익금"] / df["총 매입금액"]) * 100

    st.subheader("📋 종목 리스트")
    st.dataframe(df[["name", "quantity", "buy_price", "current_price", "수익금", "수익률 (%)"]])
else:
    st.info("아직 등록된 종목이 없습니다.")
