import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. SECURITY LOGIN ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "Sern2026": # You can change this password
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Group Access Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Group Access Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

if check_password():
    # --- 2. DATABASE SETUP ---
    conn = sqlite3.connect('sern_group.db', check_same_thread=False)
    c = conn.cursor()

    def init_db():
        c.execute('CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY AUTOINCREMENT, member_no TEXT, name TEXT, phone TEXT, id_no TEXT, join_date DATE, status TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS savings (id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT, date DATE, amount REAL, receipt_no TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS loans (loan_id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT, amount REAL, interest_rate REAL, duration INTEGER, status TEXT, date_issued DATE)')
        c.execute('CREATE TABLE IF NOT EXISTS repayments (id INTEGER PRIMARY KEY AUTOINCREMENT, loan_id INTEGER, date DATE, total_paid REAL, interest_portion REAL, principal_portion REAL)')
        conn.commit()

    init_db()

    # --- 3. UTILITY FUNCTIONS ---
    def generate_member_no():
        now = datetime.now()
        prefix = now.strftime("%y%m")
        c.execute("SELECT member_no FROM members WHERE member_no LIKE ? ORDER BY member_no DESC LIMIT 1", (prefix + '%',))
        last_no = c.fetchone()
        seq = int(last_no[0][-3:]) + 1 if last_no else 1
        return f"{prefix}{seq:03d}"

    def create_pdf(member_no, name, df, total):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "SERN SAVINGS GROUP", ln=True, align='C')
        pdf.set_font("Arial", '', 12)
        pdf.cell(200, 10, f"Member Statement: {member_no} - {name}", ln=True, align='C')
        pdf.ln(10)
        pdf.cell(0, 10, f"Total Savings: UGX {total:,.0f}", ln=True)
        pdf.ln(5)
        # Table logic...
        return pdf.output(dest='S').encode('latin-1')

    # --- 4. NAVIGATION ---
    st.sidebar.title("Sern Savings Group")
    menu = ["Member Register", "Member Detail View", "Savings Ledger", "Loan System", "Loan Calculator"]
    choice = st.sidebar.selectbox("Go to:", menu)

    if choice == "Member Register":
        st.header("👥 Member Registration")
        with st.form("reg_form"):
            n, p, i = st.text_input("Full Name"), st.text_input("Phone"), st.text_input("ID No.")
            if st.form_submit_button("Register Member"):
                new_no = generate_member_no()
                c.execute("INSERT INTO members (member_no, name, phone, id_no, join_date, status) VALUES (?,?,?,?,?,?)", 
                          (new_no, n, p, i, datetime.now().date(), "Active"))
                conn.commit()
                st.success(f"Member Registered! Number: {new_no}")
        st.dataframe(pd.read_sql("SELECT member_no, name, phone, join_date FROM members", conn))

    elif choice == "Member Detail View":
        st.header("👤 Individual Portfolio")
        m_list = pd.read_sql("SELECT member_no, name FROM members", conn)
        if not m_list.empty:
            selected = st.selectbox("Select Member", m_list['member_no'] + " - " + m_list['name'])
            m_no = selected.split(" - ")[0]
            m_name = selected.split(" - ")[1]
            
            # Fetch data
            sav_df = pd.read_sql("SELECT date, amount, receipt_no FROM savings WHERE member_id = ?", conn, params=(m_no,))
            total_sav = sav_df['amount'].sum()
            
            st.metric("Total Savings", f"UGX {total_sav:,.0f}")
            st.dataframe(sav_df)
            
            if st.button("Generate Statement"):
                pdf_bytes = create_pdf(m_no, m_name, sav_df, total_sav)
                st.download_button("Download PDF", pdf_bytes, f"{m_no}_statement.pdf", "application/pdf")

    elif choice == "Loan System":
        st.header("🏦 Loan Management")
        t1, t2 = st.tabs(["Issue Loan", "Repayment"])
        with t1:
            m_data = pd.read_sql("SELECT member_no FROM members", conn)
            with st.form("loan_f"):
                m_id = st.selectbox("Member No", m_data)
                amt = st.number_input("Amount", min_value=1000)
                if st.form_submit_button("Issue"):
                    c.execute("INSERT INTO loans (member_id, amount, interest_rate, duration, status, date_issued) VALUES (?,?,?,?,?,?)",
                              (m_id, amt, 3.5, 4, "Active", datetime.now().date()))
                    conn.commit()
                    st.success("Loan Issued")

    elif choice == "Loan Calculator":
        st.header("🧮 Loan Simulator (3.5% Reducing Balance)")
        p = st.number_input("Loan Amount", value=1000000)
        # 4 month calculation
        res = []
        rem = p
        for m in range(1, 5):
            interest = rem * 0.035
            principal = p / 4
            res.append({"Month": m, "Interest": round(interest), "Principal": round(principal), "Total": round(interest + principal)})
            rem -= principal
        st.table(pd.DataFrame(res))

    if st.sidebar.button("Logout"):
        st.session_state["password_correct"] = False
        st.rerun()
