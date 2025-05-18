import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import yfinance as yf
import requests
import plotly.express as px
import os
import shutil

# ✅ STEP 1: 실행할 때마다 database.db를 자동 백업
os.makedirs("backup", exist_ok=True)
backup_path = f"backup/backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
if os.path.exists("database.db"):
    shutil.copyfile("database.db", backup_path)

# 환율 불러오기 (USD to KRW)
def get_usd_krw():
    try:
        res = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=KRW")
        return res.json()["rates"]["KRW"]
    except:
        return 1300.0

# DB 연결
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

accounts = ["미래에셋", "키움", "삼성", "나무", "업비트"]

# 테이블 생성 및 컬럼 마이그레이션 처리
cursor.execute("""
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    quantity INTEGER,
    buy_price_per_unit REAL,
    buy_total_won REAL,
    current_price REAL,
    ticker TEXT,
    account TEXT,
    created_at TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS sold_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    quantity INTEGER,
    buy_price_per_unit REAL,
    sell_price REAL,
    account TEXT,
    sold_at TEXT,
    profit REAL,
    return_pct REAL
)
""")

# 누락 컬럼 자동 추가
for table in ["stocks", "sold_stocks"]:
    existing_cols = [col[1] for col in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    if "buy_price_per_unit" not in existing_cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN buy_price_per_unit REAL DEFAULT 0")
conn.commit()

# 실시간 가격 업데이트
def update_prices():
    df_all = pd.read_sql_query("SELECT * FROM stocks", conn)
    for _, row in df_all.iterrows():
        ticker = row["ticker"]
        acc = row["account"]
        price = None
        try:
            if acc == "업비트":
                url = f"https://api.upbit.com/v1/ticker?markets={ticker}"
                res = requests.get(url)
                price = res.json()[0]["trade_price"]
            else:
                ticker_obj = yf.Ticker(ticker)
                price = ticker_obj.fast_info.get("lastPrice")
            if price and price > 0:
                cursor.execute("UPDATE stocks SET current_price = ? WHERE id = ?", (price, row["id"]))
        except:
            continue
    conn.commit()

update_prices()

page = st.sidebar.selectbox("페이지 선택", ["📊 메인", *accounts, "💼 매도 내역"])

st.sidebar.markdown("### 종목 추가")
with st.sidebar.form("stock_form", clear_on_submit=True):
    account = st.selectbox("계좌 선택", accounts)
    name = st.text_input("종목명")
    ticker = st.text_input("티커")
    quantity = st.number_input("보유 수량", min_value=0, step=1)
    buy_price_per_unit = st.number_input("매입가(원화)", min_value=0.0, step=100.0)
    submitted = st.form_submit_button("추가")
    if submitted:
        if not name or not ticker or quantity <= 0 or buy_price_per_unit <= 0:
            st.warning("⚠️ 모든 항목을 정확히 입력해 주세요.")
        else:
            buy_total_won = buy_price_per_unit * quantity
            cursor.execute("""
                INSERT INTO stocks (name, quantity, buy_price_per_unit, buy_total_won, current_price, ticker, account, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, quantity, buy_price_per_unit, buy_total_won, 0, ticker, account, datetime.now().isoformat()))
            conn.commit()
            st.success(f"✅ {account} 계좌에 {name} 추가 완료!")
            st.rerun()

# 현재 포트폴리오 불러오기
df = pd.read_sql_query("SELECT * FROM stocks", conn)

if not df.empty:
    usd_krw = get_usd_krw()
    df["현재가(₩)"] = df["current_price"] * usd_krw
    df["총 평가금액(₩)"] = df["현재가(₩)"] * df["quantity"]
    df["수익금(₩)"] = df["총 평가금액(₩)"] - df["buy_total_won"]
    df["수익률(%)"] = df.apply(lambda row: (row["수익금(₩)"] / row["buy_total_won"] * 100) if row["buy_total_won"] else None, axis=1)

if page == "📊 메인":
    st.title("📊 전체 포트폴리오 요약")
    if not df.empty:
        total_invest = df["buy_total_won"].sum()
        total_value = df["총 평가금액(₩)"].sum()
        total_profit_sum = df["수익금(₩)"].sum()
        total_return = (total_profit_sum / total_invest) * 100 if total_invest else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("💸 총 매입금액", f"₩{int(total_invest):,}")
        col2.metric("📈 총 평가금액", f"₩{int(total_value):,}")
        col3.metric("📊 총 수익률", f"{total_return:.1f}%")
        st.divider()
        chart_data = df.groupby("account")["총 평가금액(₩)"].sum().reset_index()
        st.bar_chart(chart_data.set_index("account"))
    else:
        st.info("📭 종목이 없습니다. 추가해 주세요.")

elif page in accounts:
    st.title(f"🏦 {page} 계좌 포트폴리오")
    acc_df = df[df["account"] == page]
    if not acc_df.empty:
        pie_data = acc_df.groupby("name")["총 평가금액(₩)"].sum().reset_index()
        st.subheader("📊 종목 비중")
        fig = px.pie(pie_data, values="총 평가금액(₩)", names="name", title=f"{page} 종목 비중", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 상세 내역")
        for idx, row in acc_df.iterrows():
            수익률 = f"{row['수익률(%)']:.1f}%" if row['수익률(%)'] is not None else "-"
            수익금 = f"₩{int(row['수익금(₩)']):,}" if row['수익금(₩)'] else "-"
            현재가 = f"₩{int(row['현재가(₩)']):,}" if row['현재가(₩)'] else "-"
            매입총액 = f"₩{int(row['buy_total_won']):,}" if row['buy_total_won'] else "-"
            st.write(f"**{row['name']}** - 수량: {row['quantity']} / 매입: {매입총액} / 현재가: {현재가} / 수익금: {수익금} / 수익률: {수익률}")
            col1, col2 = st.columns([1, 1])
            if col1.button("매도", key=f"sell_{row['id']}"):
                sell_price = row["current_price"]
                total_sell_krw = sell_price * usd_krw * row["quantity"]
                total_buy_krw = row["buy_price_per_unit"] * row["quantity"]
                profit = total_sell_krw - total_buy_krw
                return_pct = (profit / total_buy_krw) * 100 if total_buy_krw else 0
                cursor.execute("""
                    INSERT INTO sold_stocks (name, quantity, buy_price_per_unit, sell_price, account, sold_at, profit, return_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (row["name"], row["quantity"], row["buy_price_per_unit"], sell_price, row["account"], datetime.now().isoformat(), profit, return_pct))
                cursor.execute("DELETE FROM stocks WHERE id = ?", (row["id"],))
                conn.commit()
                st.success(f"💰 {row['name']} 매도 완료! 수익금: ₩{int(profit):,}")
                st.rerun()
            if col2.button("삭제", key=f"delete_{row['id']}"):
                cursor.execute("DELETE FROM stocks WHERE id = ?", (row["id"],))
                conn.commit()
                st.warning(f"🗑️ {row['name']} 종목이 삭제되었습니다.")
                st.rerun()
    else:
        st.info("해당 계좌에 등록된 종목이 없습니다.")

elif page == "💼 매도 내역":
    st.title("💼 매도 종목 히스토리")
    sold_df = pd.read_sql_query("SELECT * FROM sold_stocks", conn)
    if not sold_df.empty:
        usd_krw = get_usd_krw()
        sold_df["매도금액(₩)"] = sold_df["sell_price"] * usd_krw * sold_df["quantity"]
        sold_df["총매입금액(₩)"] = sold_df["buy_price_per_unit"] * sold_df["quantity"]
        sold_df["수익금(₩)"] = sold_df["매도금액(₩)"] - sold_df["총매입금액(₩)"]
        sold_df["수익률(%)"] = sold_df.apply(lambda row: (row["수익금(₩)"] / row["총매입금액(₩)"] * 100) if row["총매입금액(₩)"] else 0, axis=1)
        sold_df["매도일시"] = pd.to_datetime(sold_df["sold_at"]).dt.date.astype(str)

        sold_df = sold_df.rename(columns={
            "name": "종목명",
            "quantity": "수량",
            "buy_price_per_unit": "매입가(₩)",
            "sell_price": "매도가($)",
            "account": "계좌"
        })

        st.dataframe(sold_df[[
            "종목명", "수량", "매입가(₩)", "매도가($)", "총매입금액(₩)", "매도금액(₩)", "수익금(₩)", "수익률(%)", "계좌", "매도일시"
        ]])
    else:
        st.info("아직 매도된 종목이 없습니다.")
        