import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
import sqlite3
from functools import wraps
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "pt-maju-jaya-demo-secret-change-me"
DB = "maju_jaya.db"

ROLE_LABELS = {
    "ADMIN": "System Admin",
    "SALES": "Salesperson",
    "CREDIT": "Credit Officer",
    "WAREHOUSE": "Warehouse Staff",
    "ACCOUNTING": "Accounting / Billing",
    "CASHIER": "Cashier",
    "MANAGER": "Manager",
}

PERMISSIONS = {
    "ADMIN": {"users", "customers", "products", "sales_orders", "credit", "shipping", "invoices", "receipts", "reports", "audit"},
    "SALES": {"customers", "products", "sales_orders"},
    "CREDIT": {"customers", "products", "sales_orders", "credit", "reports"},
    "WAREHOUSE": {"products", "sales_orders", "shipping"},
    "ACCOUNTING": {"customers", "products", "sales_orders", "shipping", "invoices", "reports"},
    "CASHIER": {"customers", "invoices", "receipts", "reports"},
    "MANAGER": {"customers", "products", "sales_orders", "credit", "shipping", "invoices", "receipts", "reports", "audit"},
}

STATUS_LABELS = {
    "DRAFT": "Draft",
    "SUBMITTED": "Submitted",
    "CREDIT_PENDING": "Credit Pending",
    "CREDIT_APPROVED": "Credit Approved",
    "CREDIT_REJECTED": "Credit Rejected",
    "PROCESSING": "Processing",
    "PARTIAL_SHIPPED": "Partially Shipped",
    "SHIPPED": "Fully Shipped",
    "INVOICED": "Invoiced",
    "PAID": "Paid",
    "REJECTED": "Rejected",
    "UNPAID": "Unpaid",
    "PARTIAL": "Partial",
}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT UNIQUE NOT NULL,
    employee_name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payment_terms (
    payment_term_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    days INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_code TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    customer_type TEXT,
    npwp TEXT,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,
    billing_address TEXT,
    city TEXT,
    province TEXT,
    postal_code TEXT,
    credit_limit REAL NOT NULL DEFAULT 0,
    payment_term_id INTEGER,
    customer_status TEXT NOT NULL DEFAULT 'ACTIVE',
    suspicious_flag INTEGER NOT NULL DEFAULT 0,
    suspicious_reason TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(payment_term_id) REFERENCES payment_terms(payment_term_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT UNIQUE NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT,
    brand TEXT,
    description TEXT,
    unit TEXT NOT NULL DEFAULT 'unit',
    selling_price REAL NOT NULL DEFAULT 0,
    available_stock INTEGER NOT NULL DEFAULT 0,
    product_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales_orders (
    sales_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    so_number TEXT UNIQUE NOT NULL,
    order_date TEXT NOT NULL,
    customer_id INTEGER NOT NULL,
    salesperson_id INTEGER NOT NULL,
    sales_type TEXT NOT NULL CHECK(sales_type IN ('CASH','CREDIT')),
    payment_term_id INTEGER,
    delivery_date TEXT,
    delivery_address TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    discount_amount REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    shipping_cost REAL NOT NULL DEFAULT 0,
    grand_total REAL NOT NULL DEFAULT 0,
    order_status TEXT NOT NULL DEFAULT 'DRAFT',
    customer_notes TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(salesperson_id) REFERENCES users(user_id),
    FOREIGN KEY(payment_term_id) REFERENCES payment_terms(payment_term_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS sales_order_details (
    so_detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    discount_pct REAL NOT NULL DEFAULT 0 CHECK(discount_pct >= 0),
    tax_rate REAL NOT NULL DEFAULT 0,
    line_subtotal REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(sales_order_id) REFERENCES sales_orders(sales_order_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS credit_approvals (
    credit_approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_order_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    credit_limit REAL NOT NULL,
    current_outstanding REAL NOT NULL,
    available_credit REAL NOT NULL,
    order_amount REAL NOT NULL,
    overdue_amount REAL NOT NULL DEFAULT 0,
    overdue_invoice_count INTEGER NOT NULL DEFAULT 0,
    average_payment_days REAL NOT NULL DEFAULT 0,
    late_payment_count INTEGER NOT NULL DEFAULT 0,
    rejected_order_count INTEGER NOT NULL DEFAULT 0,
    suspicious_flag INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'LOW',
    historical_performance TEXT,
    decision TEXT NOT NULL DEFAULT 'PENDING',
    decision_reason TEXT,
    approved_by INTEGER,
    approval_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sales_order_id) REFERENCES sales_orders(sales_order_id),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(approved_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS customer_credit_history (
    credit_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    review_date TEXT NOT NULL,
    previous_credit_limit REAL NOT NULL,
    outstanding REAL NOT NULL,
    overdue_amount REAL NOT NULL,
    total_credit_sales REAL NOT NULL,
    total_paid REAL NOT NULL,
    late_payment_count INTEGER NOT NULL,
    average_payment_days REAL NOT NULL,
    rejected_order_count INTEGER NOT NULL,
    suspicious_flag INTEGER NOT NULL,
    suspicious_reason TEXT,
    risk_level TEXT NOT NULL,
    recommended_limit REAL,
    reviewed_by INTEGER,
    review_status TEXT NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(reviewed_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS credit_limit_reviews (
    credit_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    review_date TEXT NOT NULL,
    previous_limit REAL NOT NULL,
    recommended_limit REAL NOT NULL,
    final_limit REAL,
    risk_level TEXT NOT NULL,
    reason TEXT,
    reviewed_by INTEGER,
    decision TEXT NOT NULL,
    effective_date TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(reviewed_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS shippings (
    shipping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipping_number TEXT UNIQUE NOT NULL,
    sales_order_id INTEGER NOT NULL,
    shipping_date TEXT NOT NULL,
    delivery_address TEXT NOT NULL,
    shipped_by INTEGER NOT NULL,
    shipping_status TEXT NOT NULL DEFAULT 'CONFIRMED',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sales_order_id) REFERENCES sales_orders(sales_order_id),
    FOREIGN KEY(shipped_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS shipping_details (
    shipping_detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipping_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity_ordered INTEGER NOT NULL,
    quantity_shipped INTEGER NOT NULL CHECK(quantity_shipped > 0),
    remarks TEXT,
    FOREIGN KEY(shipping_id) REFERENCES shippings(shipping_id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    sales_order_id INTEGER NOT NULL,
    shipping_id INTEGER NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    customer_id INTEGER NOT NULL,
    invoice_amount REAL NOT NULL,
    paid_amount REAL NOT NULL DEFAULT 0,
    outstanding_amount REAL NOT NULL,
    invoice_status TEXT NOT NULL DEFAULT 'UNPAID',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sales_order_id) REFERENCES sales_orders(sales_order_id),
    FOREIGN KEY(shipping_id) REFERENCES shippings(shipping_id),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS cash_receipts (
    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number TEXT UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL,
    receipt_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    payment_method_id INTEGER NOT NULL,
    bank_reference TEXT,
    received_by INTEGER NOT NULL,
    remarks TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id),
    FOREIGN KEY(payment_method_id) REFERENCES payment_methods(payment_method_id),
    FOREIGN KEY(received_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    role TEXT,
    action TEXT NOT NULL,
    module TEXT NOT NULL,
    record_id TEXT,
    old_value TEXT,
    new_value TEXT,
    description TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
"""

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def q(sql, params=(), one=False):
    conn = db()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchone() if one else cur.fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()

def exec_sql(sql, params=()):
    conn = db()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def scalar(sql, params=()):
    row = q(sql, params, one=True)
    return row[0] if row else 0

def money(x):
    try:
        return f"Rp {float(x):,.0f}".replace(",", ".")
    except Exception:
        return "Rp 0"

@app.template_filter("money")
def money_filter(x):
    return money(x)

@app.template_filter("datefmt")
def datefmt(x):
    if not x:
        return "-"
    return str(x)[:10]

@app.context_processor
def inject_globals():
    u = current_user()
    return {
        "role_labels": ROLE_LABELS,
        "status_labels": STATUS_LABELS,
        "current_user": u,
        "permissions": PERMISSIONS.get(u["role"], set()) if u else set(),
    }

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return q("SELECT * FROM users WHERE user_id = ? AND status='ACTIVE'", (uid,), one=True)

def log_action(action, module, record_id=None, old_value=None, new_value=None, description=None):
    u = current_user()
    exec_sql(
        """INSERT INTO audit_logs
        (user_id, role, action, module, record_id, old_value, new_value, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            u["user_id"] if u else None,
            u["role"] if u else None,
            action, module, str(record_id) if record_id is not None else None,
            old_value, new_value, description
        ),
    )

def notify(role, message):
    users = q("SELECT user_id FROM users WHERE role=? AND status='ACTIVE'", (role,))
    for u in users:
        exec_sql("INSERT INTO notifications(user_id,message) VALUES(?,?)", (u["user_id"], message))

def permission_required(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            u = current_user()
            if not u:
                return redirect(url_for("login"))
            if permission not in PERMISSIONS.get(u["role"], set()):
                log_action("ACCESS_DENIED", permission, description=f"Unauthorized access attempt to {request.path}")
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def next_number(prefix, table, column):
    value = scalar(f"SELECT COUNT(*) FROM {table}")
    return f"{prefix}-{value+1:06d}"

def parse_money(value, default=0):
    try:
        return float(Decimal(str(value or default)))
    except (InvalidOperation, ValueError):
        return default

def customer_metrics(customer_id):
    credit_sales = scalar("""
        SELECT COALESCE(SUM(so.grand_total),0)
        FROM sales_orders so
        WHERE so.customer_id=? AND so.sales_type='CREDIT'
          AND so.order_status NOT IN ('CANCELLED','CREDIT_REJECTED')
    """, (customer_id,))
    paid = scalar("""
        SELECT COALESCE(SUM(cr.amount),0)
        FROM cash_receipts cr
        JOIN invoices i ON i.invoice_id=cr.invoice_id
        WHERE i.customer_id=?
    """, (customer_id,))
    outstanding = scalar("""
        SELECT COALESCE(SUM(outstanding_amount),0)
        FROM invoices
        WHERE customer_id=? AND invoice_status IN ('UNPAID','PARTIAL')
    """, (customer_id,))
    overdue = scalar("""
        SELECT COALESCE(SUM(outstanding_amount),0)
        FROM invoices
        WHERE customer_id=? AND invoice_status IN ('UNPAID','PARTIAL')
          AND date(due_date) < date('now')
    """, (customer_id,))
    overdue_count = scalar("""
        SELECT COUNT(*) FROM invoices
        WHERE customer_id=? AND invoice_status IN ('UNPAID','PARTIAL')
          AND date(due_date) < date('now')
    """, (customer_id,))
    orders = scalar("SELECT COUNT(*) FROM sales_orders WHERE customer_id=?", (customer_id,))
    rejected = scalar("""
        SELECT COUNT(*) FROM sales_orders
        WHERE customer_id=? AND order_status='CREDIT_REJECTED'
    """, (customer_id,))
    late_count = scalar("""
        SELECT COUNT(*) FROM invoices
        WHERE customer_id=? AND date(due_date) < date('now')
          AND invoice_status IN ('UNPAID','PARTIAL')
    """, (customer_id,))
    avg_days = scalar("""
        SELECT COALESCE(AVG(julianday(p.last_paid_date)-julianday(i.invoice_date)),0)
        FROM (
          SELECT invoice_id, MAX(receipt_date) AS last_paid_date
          FROM cash_receipts GROUP BY invoice_id
        ) p
        JOIN invoices i ON i.invoice_id=p.invoice_id
        WHERE i.customer_id=?
    """, (customer_id,))
    last_payment = q("""
        SELECT MAX(cr.receipt_date) AS d
        FROM cash_receipts cr
        JOIN invoices i ON i.invoice_id=cr.invoice_id
        WHERE i.customer_id=?
    """, (customer_id,), one=True)["d"]
    return {
        "total_credit_sales": float(credit_sales or 0),
        "total_paid": float(paid or 0),
        "current_outstanding": float(outstanding or 0),
        "overdue_amount": float(overdue or 0),
        "overdue_invoice_count": int(overdue_count or 0),
        "total_orders": int(orders or 0),
        "rejected_order_count": int(rejected or 0),
        "late_payment_count": int(late_count or 0),
        "average_payment_days": round(float(avg_days or 0), 1),
        "last_payment_date": last_payment,
    }

def assess_customer(customer_id, order_amount):
    c = q("""
        SELECT c.*, pt.days AS payment_days
        FROM customers c
        LEFT JOIN payment_terms pt ON pt.payment_term_id=c.payment_term_id
        WHERE c.customer_id=?
    """, (customer_id,), one=True)
    m = customer_metrics(customer_id)
    credit_limit = float(c["credit_limit"] or 0)
    available = credit_limit - m["current_outstanding"]
    red_flags = []

    if credit_limit > 0 and m["overdue_amount"] > credit_limit * 0.30:
        red_flags.append("Overdue amount exceeds 30% of credit limit.")
    if m["average_payment_days"] > (c["payment_days"] or 0) + 30:
        red_flags.append("Average payment days exceed payment terms by more than 30 days.")
    if m["late_payment_count"] >= 3:
        red_flags.append("Late payment frequency is at least 3.")
    if m["overdue_invoice_count"] >= 2:
        red_flags.append("There are at least 2 overdue invoices.")
    if credit_limit > 0 and m["current_outstanding"] / credit_limit > 0.80:
        red_flags.append("Outstanding exceeds 80% of credit limit.")
    if m["rejected_order_count"] >= 2:
        red_flags.append("Customer has at least 2 rejected credit orders.")

    suspicious = bool(c["suspicious_flag"]) or bool(red_flags)
    risk = "HIGH" if suspicious and len(red_flags) >= 2 else ("MEDIUM" if suspicious else "LOW")

    if c["customer_status"] != "ACTIVE":
        decision = "REJECTED"
        reason = "Customer is inactive."
    elif available < order_amount:
        decision = "REJECTED"
        reason = "Available credit is below the order amount."
    elif suspicious:
        decision = "REVIEW REQUIRED"
        reason = "Automatic approval blocked: " + " ".join(red_flags or [c["suspicious_reason"] or "Suspicious indicator is active."])
    else:
        decision = "APPROVED"
        reason = "Within credit limit and acceptable payment history."

    performance = "GOOD" if risk == "LOW" else ("WATCH" if risk == "MEDIUM" else "HIGH RISK")
    return {
        "credit_limit": credit_limit,
        "current_outstanding": m["current_outstanding"],
        "available_credit": available,
        "order_amount": order_amount,
        "overdue_amount": m["overdue_amount"],
        "overdue_invoice_count": m["overdue_invoice_count"],
        "average_payment_days": m["average_payment_days"],
        "late_payment_count": m["late_payment_count"],
        "rejected_order_count": m["rejected_order_count"],
        "suspicious_flag": int(suspicious),
        "risk_level": risk,
        "historical_performance": performance,
        "decision": decision,
        "decision_reason": reason,
        "red_flags": red_flags,
    }

def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    conn.commit()

    if scalar("SELECT COUNT(*) FROM users") == 0:
        demo = [
            ("SP001","Sarah Putri","sp001","password","SALES","Sales"),
            ("CO001","Citra Olivia","co001","password","CREDIT","Credit"),
            ("WH001","Wawan Hadi","wh001","password","WAREHOUSE","Warehouse"),
            ("ACC001","Andi Wijaya","acc001","password","ACCOUNTING","Accounting"),
            ("CSH001","Caca Sari","csh001","password","CASHIER","Finance"),
            ("MGR001","Maya Gunawan","mgr001","password","MANAGER","Management"),
            ("ADM001","Admin System","admin","password","ADMIN","IT"),
        ]

        for eid, name, username, pw, role, dept in demo:
            exec_sql(
                """INSERT INTO users(employee_id,employee_name,username,password_hash,role,department)
                   VALUES(?,?,?,?,?,?)""",
                (eid, name, username, generate_password_hash(pw), role, dept)
            )

    if scalar("SELECT COUNT(*) FROM payment_terms") == 0:
        for code, name, days in [("CASH","Cash",0),("NET15","Net 15",15),("NET30","Net 30",30),("NET60","Net 60",60)]:
            exec_sql("INSERT INTO payment_terms(code,name,days) VALUES(?,?,?)", (code,name,days))

    if scalar("SELECT COUNT(*) FROM payment_methods") == 0:
        for code, name in [("CASH","Cash"),("TRANSFER","Bank Transfer"),("CARD","Credit Card"),("CHEQUE","Cheque"),("GIRO","Giro")]:
            exec_sql("INSERT INTO payment_methods(code,name) VALUES(?,?)", (code,name))

    if scalar("SELECT COUNT(*) FROM products") == 0:
        products = [
            ("P001","Laptop","Computer","Lenovo","Business laptop","unit",15000000,25),
            ("P002","Printer","Printing","Canon","Business printer","unit",4500000,40),
            ("P003","Projector","Presentation","Epson","Business projector","unit",8500000,15),
        ]
        for row in products:
            exec_sql("""INSERT INTO products(product_code,product_name,category,brand,description,unit,selling_price,available_stock)
                        VALUES(?,?,?,?,?,?,?,?)""", row)

    if scalar("SELECT COUNT(*) FROM customers") == 0:
        net30 = scalar("SELECT payment_term_id FROM payment_terms WHERE code='NET30'")
        customers = [
            ("CUST001","PT Maju Sejahtera","Corporate","01.234.567.8-999.000","Budi","081234567890","budi@maju.test",1,
             "Jl. Merdeka No. 10","Jakarta","DKI Jakarta","10110",100000000,net30,"ACTIVE",0,None),
            ("CUST002","PT XYZ Teknologi","Corporate","02.345.678.9-888.000","Rina","081298765432","rina@xyz.test",1,
             "Jl. Industri No. 20","Jakarta","DKI Jakarta","10220",100000000,net30,"ACTIVE",1,
             "Historical red flags require credit review."),
            ("CUST003","PT Demo Cash","Corporate","03.456.789.0-777.000","Deni","081277788899","deni@demo.test",1,
             "Jl. Sudirman No. 5","Tangerang","Banten","15111",0,scalar("SELECT payment_term_id FROM payment_terms WHERE code='CASH'"),"ACTIVE",0,None),
        ]
        for row in customers:
            exec_sql("""INSERT INTO customers(customer_code,customer_name,customer_type,npwp,contact_person,phone,email,email_verified,
                        billing_address,city,province,postal_code,credit_limit,payment_term_id,customer_status,suspicious_flag,suspicious_reason)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)

    # Seed suspicious customer's historical indicators through a completed credit-history snapshot.
    if scalar("SELECT COUNT(*) FROM customer_credit_history") == 0:
        cust2 = scalar("SELECT customer_id FROM customers WHERE customer_code='CUST002'")
        co = scalar("SELECT user_id FROM users WHERE employee_id='CO001'")
        exec_sql("""INSERT INTO customer_credit_history
            (customer_id,review_date,previous_credit_limit,outstanding,overdue_amount,total_credit_sales,total_paid,
             late_payment_count,average_payment_days,rejected_order_count,suspicious_flag,suspicious_reason,
             risk_level,recommended_limit,reviewed_by,review_status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cust2, date.today().isoformat(),100000000,20000000,60000000,300000000,240000000,5,75,2,1,
             "Overdue amount, late payments, and repeated rejected orders.", "HIGH", 60000000, co, "REVIEW"))
    conn.close()

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        u = q("SELECT * FROM users WHERE username=? AND status='ACTIVE'", (username,), one=True)
        if u and check_password_hash(u["password_hash"], password):
            session.clear()
            session["user_id"] = u["user_id"]
            log_action("LOGIN","AUTH",u["employee_id"],description="Successful login")
            flash(f"Welcome, {u['employee_name']} ({ROLE_LABELS[u['role']]})", "success")
            return redirect(url_for("dashboard"))
        log_action("FAILED_LOGIN","AUTH",description=f"Failed login for username {username}")
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    u = current_user()
    if u:
        log_action("LOGOUT","AUTH",u["employee_id"],description="User logged out")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    sales = scalar("SELECT COALESCE(SUM(grand_total),0) FROM sales_orders WHERE order_status NOT IN ('DRAFT','CANCELLED','CREDIT_REJECTED')")
    ar = scalar("SELECT COALESCE(SUM(outstanding_amount),0) FROM invoices WHERE invoice_status IN ('UNPAID','PARTIAL')")
    collected = scalar("SELECT COALESCE(SUM(amount),0) FROM cash_receipts")
    pending_credit = scalar("SELECT COUNT(*) FROM sales_orders WHERE order_status='CREDIT_PENDING'")
    pending_shipping = scalar("""SELECT COUNT(*) FROM sales_orders WHERE order_status IN ('CREDIT_APPROVED','PROCESSING','PARTIAL_SHIPPED')""")
    unpaid = scalar("SELECT COUNT(*) FROM invoices WHERE invoice_status='UNPAID'")
    partial = scalar("SELECT COUNT(*) FROM invoices WHERE invoice_status='PARTIAL'")
    paid = scalar("SELECT COUNT(*) FROM invoices WHERE invoice_status='PAID'")
    suspicious = scalar("SELECT COUNT(*) FROM customers WHERE suspicious_flag=1")
    overdue = scalar("""SELECT COALESCE(SUM(outstanding_amount),0) FROM invoices
                        WHERE invoice_status IN ('UNPAID','PARTIAL') AND date(due_date)<date('now')""")
    recent = q("""SELECT so.so_number, c.customer_name, so.grand_total, so.order_status, so.order_date
                  FROM sales_orders so JOIN customers c ON c.customer_id=so.customer_id
                  ORDER BY so.sales_order_id DESC LIMIT 8""")
    return render_template("dashboard.html", sales=sales, ar=ar, collected=collected,
                           pending_credit=pending_credit, pending_shipping=pending_shipping,
                           unpaid=unpaid, partial=partial, paid=paid, suspicious=suspicious,
                           overdue=overdue, recent=recent)

@app.route("/customers")
@permission_required("customers")
def customers():
    rows = q("""SELECT c.*, pt.code AS payment_term
                FROM customers c LEFT JOIN payment_terms pt ON pt.payment_term_id=c.payment_term_id
                ORDER BY c.customer_id DESC""")
    return render_template("customers.html", customers=rows)

@app.route("/customers/new", methods=["GET","POST"])
@permission_required("customers")
def customer_new():
    if request.method == "POST":
        u = current_user()
        code = request.form["customer_code"].strip().upper()
        if q("SELECT customer_id FROM customers WHERE customer_code=?", (code,), one=True):
            flash("Customer code already exists.", "danger")
            return redirect(url_for("customer_new"))
        term = request.form.get("payment_term_id") or None
        cid = exec_sql("""INSERT INTO customers
            (customer_code,customer_name,customer_type,npwp,contact_person,phone,email,email_verified,
             billing_address,city,province,postal_code,credit_limit,payment_term_id,customer_status,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code,request.form["customer_name"],request.form.get("customer_type"),request.form.get("npwp"),
             request.form.get("contact_person"),request.form.get("phone"),request.form.get("email"),0,
             request.form.get("billing_address"),request.form.get("city"),request.form.get("province"),
             request.form.get("postal_code"),parse_money(request.form.get("credit_limit")),term,"ACTIVE",u["user_id"]))
        log_action("CREATE","CUSTOMERS",cid,description=f"Customer {code} created")
        flash("Customer created. Email verification is simulated in this prototype.", "success")
        return redirect(url_for("customers"))
    return render_template("customer_form.html", terms=q("SELECT * FROM payment_terms ORDER BY days"))

@app.route("/customers/<int:customer_id>/verify", methods=["POST"])
@permission_required("customers")
def verify_customer(customer_id):
    q("SELECT * FROM customers WHERE customer_id=?", (customer_id,), one=True)
    exec_sql("UPDATE customers SET email_verified=1, updated_at=CURRENT_TIMESTAMP WHERE customer_id=?", (customer_id,))
    log_action("VERIFY_EMAIL","CUSTOMERS",customer_id,description="Customer email marked verified (demo)")
    flash("Customer email verified.", "success")
    return redirect(url_for("customers"))

@app.route("/products")
@permission_required("products")
def products():
    return render_template("products.html", products=q("SELECT * FROM products ORDER BY product_id DESC"))

@app.route("/sales-orders")
@permission_required("sales_orders")
def sales_orders():
    rows = q("""SELECT so.*, c.customer_name, u.employee_id, u.employee_name
                FROM sales_orders so
                JOIN customers c ON c.customer_id=so.customer_id
                JOIN users u ON u.user_id=so.salesperson_id
                ORDER BY so.sales_order_id DESC""")
    return render_template("sales_orders.html", orders=rows)

@app.route("/sales-orders/new", methods=["GET","POST"])
@permission_required("sales_orders")
def sales_order_new():
    u = current_user()
    if u["role"] != "SALES":
        flash("Only Salesperson can create Sales Orders in this prototype.", "danger")
        return redirect(url_for("sales_orders"))
    customers_list = q("SELECT c.*, pt.code AS term_code FROM customers c LEFT JOIN payment_terms pt ON pt.payment_term_id=c.payment_term_id WHERE c.customer_status='ACTIVE' ORDER BY c.customer_name")
    products_list = q("SELECT * FROM products WHERE product_status='ACTIVE' ORDER BY product_name")
    terms = q("SELECT * FROM payment_terms ORDER BY days")
    if request.method == "POST":
        customer_id = int(request.form["customer_id"])
        sales_type = request.form["sales_type"]
        term_id = request.form.get("payment_term_id") or None
        delivery_date = request.form.get("delivery_date")
        address = request.form.get("delivery_address","").strip()
        product_ids = request.form.getlist("product_id")
        quantities = request.form.getlist("quantity")
        discounts = request.form.getlist("discount_pct")
        if not product_ids:
            flash("At least one product is required.", "danger")
            return redirect(url_for("sales_order_new"))
        customer = q("SELECT * FROM customers WHERE customer_id=?", (customer_id,), one=True)
        if not customer or customer["customer_status"] != "ACTIVE":
            flash("Customer is inactive or invalid.", "danger")
            return redirect(url_for("sales_order_new"))
        if not customer["email_verified"]:
            flash("Customer email must be verified before transaction submission in this prototype.", "danger")
            return redirect(url_for("sales_order_new"))
        lines = []
        subtotal = discount_total = tax_total = 0
        for pid, qty, disc in zip(product_ids, quantities, discounts):
            p = q("SELECT * FROM products WHERE product_id=? AND product_status='ACTIVE'", (int(pid),), one=True)
            qty_i = int(qty or 0)
            disc_f = parse_money(disc)
            if not p or qty_i <= 0:
                flash("Invalid product or quantity.", "danger")
                return redirect(url_for("sales_order_new"))
            if qty_i > p["available_stock"]:
                flash(f"Insufficient stock for {p['product_name']}. Available: {p['available_stock']}.", "danger")
                return redirect(url_for("sales_order_new"))
            if disc_f < 0 or disc_f > 100:
                flash("Invalid discount.", "danger")
                return redirect(url_for("sales_order_new"))
            if disc_f > 10:
                flash("Discount above 10% requires Manager approval. This prototype blocks submission until that approval workflow is implemented.", "danger")
                return redirect(url_for("sales_order_new"))
            line_base = p["selling_price"] * qty_i
            disc_amt = line_base * disc_f / 100
            net = line_base - disc_amt
            tax = net * 0.11
            subtotal += line_base
            discount_total += disc_amt
            tax_total += tax
            lines.append((int(pid), qty_i, p["selling_price"], disc_f, 0.11, net))
        shipping_cost = parse_money(request.form.get("shipping_cost"))
        grand_total = subtotal - discount_total + tax_total + shipping_cost
        so_number = next_number("SO-2026", "sales_orders", "so_number")
        status = "CREDIT_PENDING" if sales_type == "CREDIT" else "SUBMITTED"
        conn = db()
        try:
            cur = conn.execute("""INSERT INTO sales_orders
                (so_number,order_date,customer_id,salesperson_id,sales_type,payment_term_id,delivery_date,delivery_address,
                 subtotal,discount_amount,tax_amount,shipping_cost,grand_total,order_status,customer_notes,created_by)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (so_number,date.today().isoformat(),customer_id,u["user_id"],sales_type,term_id,delivery_date,address,
                 subtotal,discount_total,tax_total,shipping_cost,grand_total,status,request.form.get("customer_notes"),u["user_id"]))
            so_id = cur.lastrowid
            for pid, qty_i, price, disc_f, tax_rate, net in lines:
                conn.execute("""INSERT INTO sales_order_details
                    (sales_order_id,product_id,quantity,unit_price,discount_pct,tax_rate,line_subtotal)
                    VALUES(?,?,?,?,?,?,?)""", (so_id,pid,qty_i,price,disc_f,tax_rate,net))
            conn.commit()
        finally:
            conn.close()
        log_action("CREATE","SALES_ORDER",so_id,description=f"{so_number} created")
        if sales_type == "CREDIT":
            notify("CREDIT", f"Sales Order {so_number} requires credit approval.")
        flash(f"{so_number} created successfully.", "success")
        return redirect(url_for("sales_orders"))
    return render_template("sales_order_form.html", customers=customers_list, products=products_list, terms=terms)

@app.route("/sales-orders/<int:so_id>")
@login_required
def sales_order_detail(so_id):
    so = q("""SELECT so.*, c.customer_name, c.customer_code, c.email, c.credit_limit,
              u.employee_name AS salesperson_name, u.employee_id AS salesperson_employee,
              pt.code AS term_code, pt.days AS term_days
              FROM sales_orders so
              JOIN customers c ON c.customer_id=so.customer_id
              JOIN users u ON u.user_id=so.salesperson_id
              LEFT JOIN payment_terms pt ON pt.payment_term_id=so.payment_term_id
              WHERE so.sales_order_id=?""", (so_id,), one=True)
    if not so:
        abort(404)
    details = q("""SELECT sod.*, p.product_name, p.product_code
                   FROM sales_order_details sod JOIN products p ON p.product_id=sod.product_id
                   WHERE sod.sales_order_id=?""", (so_id,))
    credit = q("SELECT ca.*, u.employee_id AS approver_employee, u.employee_name AS approver_name FROM credit_approvals ca LEFT JOIN users u ON u.user_id=ca.approved_by WHERE sales_order_id=? ORDER BY credit_approval_id DESC", (so_id,), one=True)
    shipping = q("SELECT * FROM shippings WHERE sales_order_id=? ORDER BY shipping_id DESC", (so_id,))
    invoice = q("SELECT * FROM invoices WHERE sales_order_id=? ORDER BY invoice_id DESC", (so_id,), one=True)
    return render_template("sales_order_detail.html", so=so, details=details, credit=credit, shipping=shipping, invoice=invoice)

@app.route("/credit")
@permission_required("credit")
def credit_queue():
    rows = q("""SELECT so.*, c.customer_name, c.credit_limit,
                ca.decision, ca.risk_level, ca.suspicious_flag
                FROM sales_orders so
                JOIN customers c ON c.customer_id=so.customer_id
                LEFT JOIN credit_approvals ca ON ca.sales_order_id=so.sales_order_id
                WHERE so.sales_type='CREDIT' AND so.order_status='CREDIT_PENDING'
                ORDER BY so.sales_order_id DESC""")
    return render_template("credit.html", orders=rows)

@app.route("/credit/<int:so_id>")
@permission_required("credit")
def credit_assess(so_id):
    so = q("SELECT * FROM sales_orders WHERE sales_order_id=?", (so_id,), one=True)
    if not so or so["sales_type"] != "CREDIT":
        abort(404)
    assessment = assess_customer(so["customer_id"], so["grand_total"])
    customer = q("""SELECT c.*, pt.code AS term_code, pt.days AS term_days
                     FROM customers c LEFT JOIN payment_terms pt ON pt.payment_term_id=c.payment_term_id
                     WHERE c.customer_id=?""", (so["customer_id"],), one=True)
    history = q("""SELECT h.*, u.employee_id AS reviewer_employee
                   FROM customer_credit_history h LEFT JOIN users u ON u.user_id=h.reviewed_by
                   WHERE h.customer_id=? ORDER BY h.credit_history_id DESC""", (so["customer_id"],))
    return render_template("credit_assess.html", so=so, customer=customer, assessment=assessment, history=history)

@app.route("/credit/<int:so_id>/decision", methods=["POST"])
@permission_required("credit")
def credit_decision(so_id):
    u = current_user()
    if u["role"] != "CREDIT":
        abort(403)
    so = q("SELECT * FROM sales_orders WHERE sales_order_id=?", (so_id,), one=True)
    if not so or so["order_status"] != "CREDIT_PENDING":
        flash("This Sales Order is not awaiting credit approval.", "danger")
        return redirect(url_for("credit_queue"))
    if so["salesperson_id"] == u["user_id"]:
        flash("You cannot approve your own Sales Order.", "danger")
        return redirect(url_for("credit_queue"))
    assessment = assess_customer(so["customer_id"], so["grand_total"])
    requested = request.form.get("decision")
    if requested == "APPROVED":
        if assessment["decision"] != "APPROVED":
            flash("System blocked approval because credit rules require review/rejection.", "danger")
            return redirect(url_for("credit_assess", so_id=so_id))
        final = "APPROVED"
    elif requested == "REJECTED":
        final = "REJECTED"
    else:
        final = "REVIEW REQUIRED"

    so_status = "CREDIT_APPROVED" if final == "APPROVED" else ("CREDIT_REJECTED" if final == "REJECTED" else "CREDIT_PENDING")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = q("SELECT credit_approval_id FROM credit_approvals WHERE sales_order_id=? ORDER BY credit_approval_id DESC", (so_id,), one=True)
    if existing:
        exec_sql("""UPDATE credit_approvals SET credit_limit=?,current_outstanding=?,available_credit=?,order_amount=?,
                    overdue_amount=?,overdue_invoice_count=?,average_payment_days=?,late_payment_count=?,rejected_order_count=?,
                    suspicious_flag=?,risk_level=?,historical_performance=?,decision=?,decision_reason=?,approved_by=?,approval_date=?
                    WHERE credit_approval_id=?""",
                 (assessment["credit_limit"],assessment["current_outstanding"],assessment["available_credit"],assessment["order_amount"],
                  assessment["overdue_amount"],assessment["overdue_invoice_count"],assessment["average_payment_days"],
                  assessment["late_payment_count"],assessment["rejected_order_count"],assessment["suspicious_flag"],
                  assessment["risk_level"],assessment["historical_performance"],final,
                  request.form.get("remarks") or assessment["decision_reason"],u["user_id"],now,existing["credit_approval_id"]))
    else:
        exec_sql("""INSERT INTO credit_approvals
            (sales_order_id,customer_id,credit_limit,current_outstanding,available_credit,order_amount,overdue_amount,
             overdue_invoice_count,average_payment_days,late_payment_count,rejected_order_count,suspicious_flag,risk_level,
             historical_performance,decision,decision_reason,approved_by,approval_date)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (so_id,so["customer_id"],assessment["credit_limit"],assessment["current_outstanding"],assessment["available_credit"],
             assessment["order_amount"],assessment["overdue_amount"],assessment["overdue_invoice_count"],
             assessment["average_payment_days"],assessment["late_payment_count"],assessment["rejected_order_count"],
             assessment["suspicious_flag"],assessment["risk_level"],assessment["historical_performance"],final,
             request.form.get("remarks") or assessment["decision_reason"],u["user_id"],now))
    exec_sql("UPDATE sales_orders SET order_status=?, updated_at=CURRENT_TIMESTAMP WHERE sales_order_id=?", (so_status,so_id))
    exec_sql("""INSERT INTO customer_credit_history
        (customer_id,review_date,previous_credit_limit,outstanding,overdue_amount,total_credit_sales,total_paid,
         late_payment_count,average_payment_days,rejected_order_count,suspicious_flag,suspicious_reason,risk_level,
         recommended_limit,reviewed_by,review_status)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (so["customer_id"],date.today().isoformat(),assessment["credit_limit"],assessment["current_outstanding"],
         assessment["overdue_amount"],customer_metrics(so["customer_id"])["total_credit_sales"],
         customer_metrics(so["customer_id"])["total_paid"],assessment["late_payment_count"],assessment["average_payment_days"],
         assessment["rejected_order_count"],assessment["suspicious_flag"]," ".join(assessment["red_flags"]),
         assessment["risk_level"],None,u["user_id"],final))
    log_action("CREDIT_DECISION","CREDIT",so_id,description=f"{so['so_number']}: {final}")
    if final == "APPROVED":
        notify("WAREHOUSE", f"{so['so_number']} is credit approved and ready for shipping.")
        flash("Credit approved. Shipping is now eligible.", "success")
    elif final == "REJECTED":
        flash("Credit rejected. Shipping is blocked.", "danger")
    else:
        flash("Review required. Automatic approval remains blocked.", "warning")
    return redirect(url_for("credit_queue"))

@app.route("/shipping")
@permission_required("shipping")
def shipping():
    rows = q("""SELECT so.*, c.customer_name
                FROM sales_orders so JOIN customers c ON c.customer_id=so.customer_id
                WHERE so.order_status IN ('CREDIT_APPROVED','PROCESSING','PARTIAL_SHIPPED','SUBMITTED')
                  AND (so.sales_type='CASH' OR so.order_status='CREDIT_APPROVED')
                ORDER BY so.sales_order_id DESC""")
    return render_template("shipping.html", orders=rows)

@app.route("/shipping/<int:so_id>/create", methods=["GET","POST"])
@permission_required("shipping")
def shipping_create(so_id):
    u = current_user()
    if u["role"] != "WAREHOUSE":
        abort(403)
    so = q("SELECT * FROM sales_orders WHERE sales_order_id=?", (so_id,), one=True)
    if not so:
        abort(404)
    if so["sales_type"] == "CREDIT":
        ca = q("SELECT * FROM credit_approvals WHERE sales_order_id=? AND decision='APPROVED' ORDER BY credit_approval_id DESC", (so_id,), one=True)
        if not ca:
            flash("Shipping blocked: approved credit is required.", "danger")
            return redirect(url_for("shipping"))
    details = q("""SELECT sod.*, p.product_name,p.available_stock,p.product_code,
                   COALESCE((SELECT SUM(sd.quantity_shipped) FROM shipping_details sd
                             JOIN shippings s ON s.shipping_id=sd.shipping_id
                             WHERE s.sales_order_id=so.sales_order_id AND sd.product_id=sod.product_id),0) shipped_before
                   FROM sales_order_details sod JOIN products p ON p.product_id=sod.product_id
                   WHERE sod.sales_order_id=?""", (so_id,))
    if request.method == "POST":
        conn = db()
        try:
            ship_num = next_number("SH-2026", "shippings", "shipping_number")
            cur = conn.execute("""INSERT INTO shippings(shipping_number,sales_order_id,shipping_date,delivery_address,shipped_by)
                                  VALUES(?,?,?,?,?)""",
                               (ship_num,so_id,date.today().isoformat(),so["delivery_address"],u["user_id"]))
            sid = cur.lastrowid
            total_lines = 0
            full = True
            for d in details:
                qty = int(request.form.get(f"qty_{d['so_detail_id']}",0) or 0)
                remaining = d["quantity"] - d["shipped_before"]
                if qty < 0 or qty > remaining or qty > d["available_stock"]:
                    conn.rollback()
                    flash(f"Invalid shipping quantity for {d['product_name']}. Remaining: {remaining}, stock: {d['available_stock']}.", "danger")
                    return redirect(url_for("shipping_create", so_id=so_id))
                if qty:
                    conn.execute("""INSERT INTO shipping_details(shipping_id,product_id,quantity_ordered,quantity_shipped,remarks)
                                    VALUES(?,?,?,?,?)""", (sid,d["product_id"],d["quantity"],qty,request.form.get(f"remark_{d['so_detail_id']}")))
                    conn.execute("UPDATE products SET available_stock=available_stock-?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?", (qty,d["product_id"]))
                    total_lines += qty
                if d["shipped_before"] + qty < d["quantity"]:
                    full = False
            if total_lines == 0:
                conn.rollback()
                flash("At least one quantity must be shipped.", "danger")
                return redirect(url_for("shipping_create", so_id=so_id))
            status = "SHIPPED" if full else "PARTIAL_SHIPPED"
            conn.execute("UPDATE sales_orders SET order_status=?, updated_at=CURRENT_TIMESTAMP WHERE sales_order_id=?", (status,so_id))
            conn.commit()
        finally:
            conn.close()
        log_action("CREATE","SHIPPING",sid,description=f"{ship_num} created for {so['so_number']}")
        notify("ACCOUNTING", f"Shipping {ship_num} completed. Invoice can be reviewed.")
        flash(f"{ship_num} created.", "success")
        return redirect(url_for("shipping"))
    return render_template("shipping_form.html", so=so, details=details)

@app.route("/invoices")
@permission_required("invoices")
def invoices():
    rows = q("""SELECT i.*, c.customer_name, so.so_number, s.shipping_number
                FROM invoices i
                JOIN customers c ON c.customer_id=i.customer_id
                JOIN sales_orders so ON so.sales_order_id=i.sales_order_id
                JOIN shippings s ON s.shipping_id=i.shipping_id
                ORDER BY i.invoice_id DESC""")
    shipments = q("""SELECT s.*, so.so_number, c.customer_name
                     FROM shippings s JOIN sales_orders so ON so.sales_order_id=s.sales_order_id
                     JOIN customers c ON c.customer_id=so.customer_id
                     WHERE s.shipping_status='CONFIRMED'
                     AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.shipping_id=s.shipping_id)
                     ORDER BY s.shipping_id DESC""")
    return render_template("invoices.html", invoices=rows, shipments=shipments)

@app.route("/invoices/create/<int:shipping_id>", methods=["GET","POST"])
@permission_required("invoices")
def invoice_create(shipping_id):
    u = current_user()
    if u["role"] != "ACCOUNTING":
        abort(403)
    ship = q("""SELECT s.*, so.so_number, so.customer_id, so.grand_total, so.payment_term_id,
                c.customer_name, pt.days AS term_days
                FROM shippings s JOIN sales_orders so ON so.sales_order_id=s.sales_order_id
                JOIN customers c ON c.customer_id=so.customer_id
                LEFT JOIN payment_terms pt ON pt.payment_term_id=so.payment_term_id
                WHERE s.shipping_id=? AND s.shipping_status='CONFIRMED'""", (shipping_id,), one=True)
    if not ship:
        abort(404)
    if q("SELECT invoice_id FROM invoices WHERE shipping_id=?", (shipping_id,), one=True):
        flash("This shipment has already been invoiced.", "danger")
        return redirect(url_for("invoices"))
    if request.method == "POST":
        invoice_num = next_number("INV-2026", "invoices", "invoice_number")
        inv_date = date.today()
        due = inv_date + timedelta(days=int(ship["term_days"] or 0))
        iid = exec_sql("""INSERT INTO invoices
            (invoice_number,sales_order_id,shipping_id,invoice_date,due_date,customer_id,invoice_amount,outstanding_amount,created_by)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (invoice_num,ship["sales_order_id"],shipping_id,inv_date.isoformat(),due.isoformat(),ship["customer_id"],ship["grand_total"],ship["grand_total"],u["user_id"]))
        exec_sql("UPDATE sales_orders SET order_status='INVOICED', updated_at=CURRENT_TIMESTAMP WHERE sales_order_id=?", (ship["sales_order_id"],))
        log_action("CREATE","INVOICE",iid,description=f"{invoice_num} created")
        notify("CASHIER", f"Invoice {invoice_num} is ready for payment.")
        flash(f"{invoice_num} issued.", "success")
        return redirect(url_for("invoices"))
    return render_template("invoice_confirm.html", ship=ship)

@app.route("/receipts")
@permission_required("receipts")
def receipts():
    invoices_list = q("""SELECT i.*, c.customer_name
                         FROM invoices i JOIN customers c ON c.customer_id=i.customer_id
                         WHERE i.invoice_status IN ('UNPAID','PARTIAL')
                         ORDER BY i.due_date""")
    receipts_list = q("""SELECT cr.*, i.invoice_number, c.customer_name, pm.name AS payment_method,
                         u.employee_id
                         FROM cash_receipts cr
                         JOIN invoices i ON i.invoice_id=cr.invoice_id
                         JOIN customers c ON c.customer_id=i.customer_id
                         JOIN payment_methods pm ON pm.payment_method_id=cr.payment_method_id
                         JOIN users u ON u.user_id=cr.received_by
                         ORDER BY cr.receipt_id DESC""")
    methods = q("SELECT * FROM payment_methods ORDER BY name")
    return render_template("receipts.html", invoices=invoices_list, receipts=receipts_list, methods=methods)

@app.route("/receipts/create", methods=["POST"])
@permission_required("receipts")
def receipt_create():
    u = current_user()
    if u["role"] != "CASHIER":
        abort(403)
    invoice_id = int(request.form["invoice_id"])
    amount = parse_money(request.form.get("amount"))
    inv = q("SELECT * FROM invoices WHERE invoice_id=?", (invoice_id,), one=True)
    if not inv or inv["invoice_status"] == "PAID":
        flash("Invoice is invalid or already paid.", "danger")
        return redirect(url_for("receipts"))
    if amount <= 0 or amount > inv["outstanding_amount"]:
        flash("Payment must be greater than 0 and cannot exceed outstanding balance.", "danger")
        return redirect(url_for("receipts"))
    rid = exec_sql("""INSERT INTO cash_receipts(receipt_number,invoice_id,receipt_date,amount,payment_method_id,bank_reference,received_by,remarks)
                      VALUES(?,?,?,?,?,?,?,?)""",
                   (next_number("RC-2026","cash_receipts","receipt_number"),invoice_id,date.today().isoformat(),amount,
                    int(request.form["payment_method_id"]),request.form.get("bank_reference"),u["user_id"],request.form.get("remarks")))
    paid = scalar("SELECT COALESCE(SUM(amount),0) FROM cash_receipts WHERE invoice_id=?", (invoice_id,))
    outstanding = max(float(inv["invoice_amount"]) - float(paid), 0)
    status = "PAID" if outstanding == 0 else "PARTIAL"
    exec_sql("UPDATE invoices SET paid_amount=?, outstanding_amount=?, invoice_status=? WHERE invoice_id=?", (paid,outstanding,status,invoice_id))
    if status == "PAID":
        so_id = inv["sales_order_id"]
        exec_sql("UPDATE sales_orders SET order_status='PAID', updated_at=CURRENT_TIMESTAMP WHERE sales_order_id=?", (so_id,))
    log_action("CREATE","CASH_RECEIPT",rid,description=f"Payment {amount} recorded for {inv['invoice_number']}")
    flash(f"Payment recorded. Invoice status: {status}.", "success")
    return redirect(url_for("receipts"))

@app.route("/reports")
@permission_required("reports")
def reports():
    sales_by_product = q("""SELECT p.product_name, SUM(sod.quantity) qty,
                            SUM(sod.line_subtotal) amount
                            FROM sales_order_details sod
                            JOIN products p ON p.product_id=sod.product_id
                            JOIN sales_orders so ON so.sales_order_id=sod.sales_order_id
                            WHERE so.order_status NOT IN ('DRAFT','CANCELLED','CREDIT_REJECTED')
                            GROUP BY p.product_id ORDER BY amount DESC""")
    customer_sales = q("""SELECT c.customer_name, COUNT(so.sales_order_id) orders,
                           COALESCE(SUM(CASE WHEN so.order_status NOT IN ('DRAFT','CANCELLED','CREDIT_REJECTED') THEN so.grand_total ELSE 0 END),0) total_sales,
                           COALESCE((SELECT SUM(cr.amount) FROM cash_receipts cr JOIN invoices i ON i.invoice_id=cr.invoice_id WHERE i.customer_id=c.customer_id),0) total_paid,
                           COALESCE((SELECT SUM(i.outstanding_amount) FROM invoices i WHERE i.customer_id=c.customer_id AND i.invoice_status IN ('UNPAID','PARTIAL')),0) outstanding
                           FROM customers c LEFT JOIN sales_orders so ON so.customer_id=c.customer_id
                           GROUP BY c.customer_id ORDER BY total_sales DESC""")
    ar = q("""SELECT i.invoice_number,c.customer_name,i.invoice_date,i.due_date,i.invoice_amount,i.paid_amount,
              i.outstanding_amount,i.invoice_status,
              CASE WHEN i.outstanding_amount>0 AND date(i.due_date)<date('now') THEN CAST(julianday('now')-julianday(i.due_date) AS INTEGER) ELSE 0 END AS overdue_days
              FROM invoices i JOIN customers c ON c.customer_id=i.customer_id ORDER BY i.due_date""")
    orders = q("""SELECT so.so_number,so.order_date,c.customer_name,u.employee_id salesperson,
                  so.grand_total,so.order_status
                  FROM sales_orders so JOIN customers c ON c.customer_id=so.customer_id
                  JOIN users u ON u.user_id=so.salesperson_id ORDER BY so.sales_order_id DESC""")
    return render_template("reports.html", sales_by_product=sales_by_product, customer_sales=customer_sales, ar=ar, orders=orders)

@app.route("/audit")
@permission_required("audit")
def audit():
    logs = q("""SELECT a.*, u.employee_id, u.employee_name
                FROM audit_logs a LEFT JOIN users u ON u.user_id=a.user_id
                ORDER BY a.audit_id DESC LIMIT 250""")
    return render_template("audit.html", logs=logs)

@app.route("/users")
@permission_required("users")
def users():
    return render_template("users.html", users=q("SELECT employee_id,employee_name,username,role,department,status,created_at FROM users ORDER BY user_id"))

@app.route("/notifications")
@login_required
def notifications():
    u = current_user()
    rows = q("SELECT * FROM notifications WHERE user_id=? ORDER BY notification_id DESC LIMIT 50", (u["user_id"],))
    return render_template("notifications.html", notifications=rows)

@app.route("/notifications/read/<int:nid>", methods=["POST"])
@login_required
def notification_read(nid):
    u = current_user()
    exec_sql("UPDATE notifications SET is_read=1 WHERE notification_id=? AND user_id=?", (nid,u["user_id"]))
    return redirect(url_for("notifications"))

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="You are not authorized to perform this action."), 403

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="The requested record/page was not found."), 404

@app.route("/api/customer/<int:customer_id>/metrics")
@login_required
def customer_metrics_api(customer_id):
    c = q("SELECT * FROM customers WHERE customer_id=?", (customer_id,), one=True)
    if not c:
        return jsonify({"error":"Customer not found"}), 404
    m = customer_metrics(customer_id)
    return jsonify({
        "customer": c["customer_name"],
        "credit_limit": c["credit_limit"],
        **m
    })

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
