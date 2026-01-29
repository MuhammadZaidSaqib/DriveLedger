
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import calendar
import sqlite3
DB_PATH = "driveledger.db"

def db_init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    with open("init_driveledger.sql", "r", encoding="utf-8") as f:
        cur.executescript(f.read())
    conn.commit()
    conn.close()

def load_all_from_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM vehicles")
    vehicles = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM sales")
    sales = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM expenses")
    expenses = [dict(r) for r in cur.fetchall()]

    conn.close()
    return vehicles, sales, expenses

def save_vehicle(v):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO vehicles VALUES (?,?,?,?,?,?,?)",
        tuple(v.values())
    )
    conn.commit()
    conn.close()

def save_sale(s):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sales VALUES (?,?,?,?,?)",
        tuple(s.values())
    )
    conn.commit()
    conn.close()

def save_expense(e):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses VALUES (?,?,?,?)",
        tuple(e.values())
    )
    conn.commit()
    conn.close()

# ------------------------
# Data classes (records)
# ------------------------
@dataclass
class Vehicle:
    id: int
    brand: str
    model: str
    year: int
    purchase_price: float
    expected_sell_price: float
    date_added: str  # ISO date string

@dataclass
class SaleRecord:
    sale_id: int
    vehicle_id: int
    customer_name: str
    sale_price: float
    date: str  # ISO string

@dataclass
class ExpenseRecord:
    expense_id: int
    description: str
    amount: float
    date: str  # ISO string

# ------------------------
# Initialize session state
# ------------------------
db_init()
def main():
    st.set_page_config(page_title="DriveLedger Pro", layout="wide")
    db_init()              # ✅ REQUIRED
    init_state()
    page = sidebar_menu()

def init_state():
    if "inventory" not in st.session_state:
        st.session_state.inventory: List[Vehicle] = []
    if "sales" not in st.session_state:
        st.session_state.sales: List[SaleRecord] = []
    if "expenses" not in st.session_state:
        st.session_state.expenses: List[ExpenseRecord] = []
    if "purchase_history" not in st.session_state:
        # list of dicts {amount, date}
        st.session_state.purchase_history: List[Dict[str, Any]] = []
    if "next_vehicle_id" not in st.session_state:
        st.session_state.next_vehicle_id = 1
    if "next_sale_id" not in st.session_state:
        st.session_state.next_sale_id = 1
    if "next_expense_id" not in st.session_state:
        st.session_state.next_expense_id = 1
    if "cumulative_purchase_cost" not in st.session_state:
        st.session_state.cumulative_purchase_cost = 0.0

# ------------------------
# Helpers
# ------------------------
def inventory_df() -> pd.DataFrame:
    rows = [asdict(v) for v in st.session_state.inventory]
    if rows:
        return pd.DataFrame(rows)
    else:
        return pd.DataFrame(columns=["id","brand","model","year","purchase_price","expected_sell_price","date_added"])

def sales_df() -> pd.DataFrame:
    rows = [asdict(s) for s in st.session_state.sales]
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=["sale_id","vehicle_id","customer_name","sale_price","date"])

def expenses_df() -> pd.DataFrame:
    rows = [asdict(e) for e in st.session_state.expenses]
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=["expense_id","description","amount","date"])

def add_vehicle(brand: str, model: str, year: int, purchase_price: float, expected_sell_price: float):
    vid = st.session_state.next_vehicle_id
    date_added = datetime.utcnow().isoformat()
    v = Vehicle(vid, brand.strip(), model.strip(), int(year), float(purchase_price), float(expected_sell_price), date_added)
    st.session_state.inventory.insert(0, v)  # insert at head
    st.session_state.next_vehicle_id += 1
    # track cumulative purchase cost and purchase history (for monthly breakdown)
    st.session_state.cumulative_purchase_cost += float(purchase_price)
    st.session_state.purchase_history.append({"amount": float(purchase_price), "date": date_added})
    st.success(f"Vehicle added with ID: {vid}")

def find_vehicle_by_id(vid: int) -> Optional[Vehicle]:
    for v in st.session_state.inventory:
        if v.id == vid:
            return v
    return None

def remove_vehicle_by_id(vid: int) -> bool:
    for i, v in enumerate(st.session_state.inventory):
        if v.id == vid:
            st.session_state.inventory.pop(i)
            return True
    return False

def sell_vehicle(vid: int, customer_name: str, sale_price: float):
    vehicle = find_vehicle_by_id(vid)
    if vehicle is None:
        st.error("Vehicle ID not found in inventory.")
        return
    sale_id = st.session_state.next_sale_id
    rec = SaleRecord(sale_id, vid, customer_name.strip(), float(sale_price), datetime.utcnow().isoformat())
    st.session_state.sales.append(rec)
    removed = remove_vehicle_by_id(vid)
    if removed:
        st.success(f"Vehicle ID {vid} sold. Sale ID: {sale_id}")
        st.session_state.next_sale_id += 1
    else:
        st.error("Failed to remove vehicle from inventory (unexpected).")

def add_expense(description: str, amount: float):
    eid = st.session_state.next_expense_id
    rec = ExpenseRecord(eid, description.strip(), float(amount), datetime.utcnow().isoformat())
    st.session_state.expenses.append(rec)
    st.session_state.total_other_expenses = getattr(st.session_state, "total_other_expenses", 0.0) + float(amount)
    st.session_state.next_expense_id += 1
    st.success(f"Expense added with ID: {eid}")

# ------------------------
# Aggregation for dashboard
# ------------------------
def month_key_from_iso(iso_dt: str) -> (int, int):
    # returns (year, month)
    try:
        dt = datetime.fromisoformat(iso_dt)
    except Exception:
        dt = datetime.utcnow()
    return dt.year, dt.month

def monthly_aggregation_for_year(year: int):
    # returns two lists month 1..12 for debit and credit
    debit_month = [0.0]*12
    credit_month = [0.0]*12

    # Credits: sales
    for s in st.session_state.sales:
        y,m = month_key_from_iso(s.date)
        if y == year:
            credit_month[m-1] += float(s.sale_price)

    # Debits: expenses
    for e in st.session_state.expenses:
        y,m = month_key_from_iso(e.date)
        if y == year:
            debit_month[m-1] += float(e.amount)

    # Debits: purchases (from purchase_history)
    for p in st.session_state.purchase_history:
        y,m = month_key_from_iso(p["date"])
        if y == year:
            debit_month[m-1] += float(p["amount"])

    return debit_month, credit_month

def totals_from_monthly(debit_month, credit_month):
    total_debit = sum(debit_month)
    total_credit = sum(credit_month)
    return total_debit, total_credit

# ------------------------
# UI layout
# ------------------------
def sidebar_menu():
    st.sidebar.title("DriveLedger Pro")
    st.sidebar.markdown("Inventory & Financials")
    page = st.sidebar.radio("Menu", (
        "Dashboard",
        "Add Vehicle",
        "View Inventory",
        "Search Vehicle",
        "Sell Vehicle",
        "Sales Records",
        "Expenses",
        "Financial Summary"
    ))
    return page

# Dashboard page with visual layout similar to sample image
def dashboard_page():
    st.title("🚗 Ledger Balance Monitoring — Dashboard")
    # Year selector
    current_year = datetime.utcnow().year
    years_available = list({month_key_from_iso(item["date"])[0] for item in st.session_state.purchase_history}
                           | {month_key_from_iso(s.date)[0] for s in st.session_state.sales}
                           | {month_key_from_iso(e.date)[0] for e in st.session_state.expenses}
                           | {current_year})
    years_available = sorted(years_available)
    year = st.selectbox("Select YEAR", options=years_available, index=len(years_available)-1 if years_available else 0)

    # Starting balance input (user-provided)
    starting_balance = st.number_input("Starting Balance (optional)", value=0.0, format="%.2f")

    # compute monthly aggregates
    debit_month, credit_month = monthly_aggregation_for_year(int(year))
    total_debit, total_credit = totals_from_monthly(debit_month, credit_month)
    adjusted_balance = starting_balance + (total_credit - total_debit)

    # Top summary cards
    c1, c2, c3, c4 = st.columns([1,1,1,1])
    c1.metric("Total Debit", f"${total_debit:,.2f}")
    c2.metric("Total Credit", f"${total_credit:,.2f}")
    c3.metric("Starting Balance", f"${starting_balance:,.2f}")
    c4.metric("Adjusted Balance", f"${adjusted_balance:,.2f}")

    st.markdown("---")

    # layout: left table, center charts, right pie/vertical
    left, center, right = st.columns([1.2, 2.4, 1.2])

    # Left: monthly debit/credit table (styled)
    with left:
        st.subheader("Monthly Debit / Credit")
        months = [calendar.month_name[i] for i in range(1,13)]
        table_rows = []
        for i, m in enumerate(months):
            table_rows.append({
                "Month": m,
                "Debit": float(debit_month[i]),
                "Credit": float(credit_month[i])
            })
        df_monthly = pd.DataFrame(table_rows)
        # format currency
        def fmt(x): return f"${x:,.2f}" if x != 0 else "$0.00"
        display_df = df_monthly.copy()
        display_df["Debit"] = display_df["Debit"].apply(fmt)
        display_df["Credit"] = display_df["Credit"].apply(fmt)
        st.table(display_df.set_index("Month"))

    # Center: Line chart (monthly totals) and small bar chart below
    with center:
        st.subheader("Monthly Trend")
        months_short = [calendar.month_abbr[i] for i in range(1,13)]
        df_plot = pd.DataFrame({
            "month": months_short,
            "debit": debit_month,
            "credit": credit_month,
            "net": [credit_month[i] - debit_month[i] for i in range(12)]
        })

        # Line chart: Net or separate? We'll plot both debit & credit as lines + net as area
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=df_plot["month"], y=df_plot["debit"],
                                      mode="lines+markers", name="Debit", line=dict(width=2)))
        fig_line.add_trace(go.Scatter(x=df_plot["month"], y=df_plot["credit"],
                                      mode="lines+markers", name="Credit", line=dict(width=2)))
        fig_line.add_trace(go.Bar(x=df_plot["month"], y=df_plot["net"], name="Net (Credit - Debit)", opacity=0.35))
        fig_line.update_layout(height=300, margin=dict(l=20,r=20,t=30,b=20), legend=dict(orientation="h"))
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("#### Debit & Credit by Month (Grouped)")
        fig_group = go.Figure(data=[
            go.Bar(name="Debit", x=df_plot["month"], y=df_plot["debit"]),
            go.Bar(name="Credit", x=df_plot["month"], y=df_plot["credit"])
        ])
        fig_group.update_layout(barmode='group', height=300, margin=dict(l=20,r=20,t=30,b=20))
        st.plotly_chart(fig_group, use_container_width=True)

    # Right: Pie + Vertical comparison
    with right:
        st.subheader("Breakdown")
        # Pie chart (debit vs credit)
        pie_fig = px.pie(names=["Debit", "Credit"], values=[total_debit, total_credit],
                         title="Debit vs Credit", hole=0.4)
        pie_fig.update_traces(textposition='inside', textinfo='percent+label')
        pie_fig.update_layout(height=280, margin=dict(l=0,r=0,t=30,b=0))
        st.plotly_chart(pie_fig, use_container_width=True)

        st.markdown("### Totals")
        # Vertical comparison bars
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=["Debit"], y=[total_debit], name="Debit", marker_color="#EF553B"))
        fig_comp.add_trace(go.Bar(x=["Credit"], y=[total_credit], name="Credit", marker_color="#00CC96"))
        fig_comp.update_layout(height=300, showlegend=False, margin=dict(l=20,r=20,t=20,b=20))
        st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("---")
    st.subheader("Details & Downloads")
    col_a, col_b = st.columns(2)
    with col_a:
        inv = inventory_df()
        st.write("Inventory (current):")
        st.dataframe(inv, use_container_width=True)
        if not inv.empty:
            st.download_button("Download Inventory CSV", data=inv.to_csv(index=False).encode("utf-8"),
                                file_name=f"inventory_{year}.csv", mime="text/csv")
    with col_b:
        s = sales_df()
        e = expenses_df()
        st.write("Sales & Expenses (selected year):")
        sel_sales = s[s["date"].str.slice(0,4) == str(year)] if not s.empty else s
        sel_expenses = e[e["date"].str.slice(0,4) == str(year)] if not e.empty else e
        st.write("Sales:")
        st.dataframe(sel_sales, use_container_width=True)
        st.write("Expenses:")
        st.dataframe(sel_expenses, use_container_width=True)

# Regular pages (Add, View, Search, Sell, Sales, Expenses, Financial Summary)
def page_add_vehicle():
    st.header("➕ Add Vehicle to Inventory")
    with st.form("add_vehicle_form", clear_on_submit=True):
        brand = st.text_input("Brand", placeholder="e.g., Toyota")
        model = st.text_input("Model", placeholder="e.g., Corolla")
        year = st.number_input("Year", min_value=1900, max_value=2100, value=datetime.utcnow().year, step=1)
        purchase_price = st.number_input("Purchase Price", min_value=0.0, value=0.0, format="%.2f")
        expected_sell_price = st.number_input("Expected Selling Price", min_value=0.0, value=0.0, format="%.2f")
        submitted = st.form_submit_button("Add Vehicle")
        if submitted:
            if not brand or not model:
                st.error("Brand and model cannot be empty.")
            else:
                add_vehicle(brand, model, year, purchase_price, expected_sell_price)

def page_view_inventory():
    st.header("📋 Current Inventory")
    df = inventory_df()
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        st.download_button("Download Inventory CSV", data=df.to_csv(index=False).encode('utf-8'),
                           file_name="inventory.csv", mime="text/csv")

def page_search_vehicle():
    st.header("🔎 Search Vehicle by ID")
    vid = st.number_input("Enter vehicle ID", min_value=1, step=1)
    if st.button("Search"):
        v = find_vehicle_by_id(int(vid))
        if v:
            st.success("Vehicle found:")
            st.write(asdict(v))
        else:
            st.warning(f"No vehicle found with ID {vid}.")

def page_sell_vehicle():
    st.header("💸 Sell Vehicle")
    with st.form("sell_vehicle_form", clear_on_submit=True):
        vid = st.number_input("Vehicle ID to sell", min_value=1, step=1)
        customer = st.text_input("Customer Name")
        sale_price = st.number_input("Actual Sale Price", min_value=0.0, value=0.0, format="%.2f")
        submitted = st.form_submit_button("Sell Vehicle")
        if submitted:
            if not customer:
                st.error("Customer name required.")
            else:
                sell_vehicle(int(vid), customer, float(sale_price))

def page_sales_records():
    st.header("📈 Sales Records")
    df = sales_df()
    if df.empty:
        st.info("No sales recorded yet.")
    else:
        st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)
        st.download_button("Download Sales CSV", data=df.to_csv(index=False).encode("utf-8"),
                           file_name="sales.csv", mime="text/csv")

def page_expenses():
    st.header("🧾 Expenses")
    with st.form("add_expense_form", clear_on_submit=True):
        desc = st.text_input("Expense Description")
        amount = st.number_input("Amount", min_value=0.0, value=0.0, format="%.2f")
        submitted = st.form_submit_button("Add Expense")
        if submitted:
            if not desc:
                st.error("Description required.")
            else:
                add_expense(desc, amount)
    st.subheader("All Expenses")
    df = expenses_df()
    if df.empty:
        st.info("No expenses recorded.")
    else:
        st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)
        st.download_button("Download Expenses CSV", data=df.to_csv(index=False).encode("utf-8"),
                           file_name="expenses.csv", mime="text/csv")

def page_financial_summary():
    st.header("💼 Financial Summary")
    cum_purchase = st.session_state.get("cumulative_purchase_cost", 0.0)
    revenue = sum(s.sale_price for s in st.session_state.sales)
    expenses = sum(e.amount for e in st.session_state.expenses)
    profit = revenue - (cum_purchase + expenses)

    col1, col2, col3 = st.columns(3)
    col1.metric("Cumulative Purchase Cost", f"${cum_purchase:,.2f}")
    col2.metric("Total Revenue (Sales)", f"${revenue:,.2f}")
    col3.metric("Total Other Expenses", f"${expenses:,.2f}")

    st.markdown(f"**Net Profit / Loss:** `{profit:,.2f}`")
    if profit > 0:
        st.success("Status: PROFIT")
    elif profit < 0:
        st.error("Status: LOSS")
    else:
        st.info("Status: BREAK-EVEN")

    st.markdown("---")
    st.write("Vehicles sold:", len(st.session_state.sales))
    st.write("Vehicles currently in inventory:", len(st.session_state.inventory))

# ------------------------
# Main
# ------------------------
def main():
    st.set_page_config(page_title="DriveLedger Pro", layout="wide", initial_sidebar_state="expanded")
    st.markdown("<h1 style='text-align:center'>🚗 DriveLedger Pro — Streamlit</h1>", unsafe_allow_html=True)
    init_state()
    page = sidebar_menu()

    if page == "Dashboard":
        dashboard_page()
    elif page == "Add Vehicle":
        page_add_vehicle()
    elif page == "View Inventory":
        page_view_inventory()
    elif page == "Search Vehicle":
        page_search_vehicle()
    elif page == "Sell Vehicle":
        page_sell_vehicle()
    elif page == "Sales Records":
        page_sales_records()
    elif page == "Expenses":
        page_expenses()
    elif page == "Financial Summary":
        page_financial_summary()
    else:
        st.write("Unknown page selected.")

if __name__ == "__main__":
    main()
