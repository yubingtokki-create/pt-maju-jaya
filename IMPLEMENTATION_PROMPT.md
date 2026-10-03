# Implementation Prompt — PT Maju Jaya Integrated AIS

Use this prompt when asking an AI coding assistant to extend this project.

You are an expert Accounting Information Systems (AIS) designer, ERP architect, relational database designer, UI/UX designer, and Python full-stack developer.

Extend the existing PT Maju Jaya Flask + SQLite project. Do NOT replace the existing architecture unless necessary.

The application is an integrated Revenue Cycle AIS:

Customer → Sales Order → Credit Approval → Shipping → Invoice → Cash Receipt → Reports

The application must remain a real integrated system, not disconnected CRUD screens.

## Non-negotiable controls

- Authentication before system access.
- Role-based authorization enforced server-side.
- Segregation of duties.
- Salesperson cannot approve own credit.
- Credit shipping requires approved credit for credit sales.
- Invoice requires valid shipping.
- Cash receipt requires valid outstanding invoice.
- Payment status updates automatically.
- Historical credit information is calculated from transaction data where possible.
- Suspicious/red-flag indicators must have explicit rules.
- Credit Limit is not the only approval criterion.
- Credit-limit changes require authorized review.
- Audit trail must record critical actions.
- Reports must query the database, not hard-coded values.
- Do not allow users to bypass controls by manually entering a URL or calling a restricted endpoint.

## Credit Assessment

Evaluate:

- Credit limit
- Current outstanding
- Available credit
- Overdue amount
- Overdue invoice count
- Late payment count
- Average payment days
- Payment terms
- Rejected order count
- Suspicious indicators
- Historical performance

Red flags:

- Overdue > 30% of credit limit
- Average payment days > payment terms + 30 days
- Late payment count >= 3
- Overdue invoice count >= 2
- Outstanding / credit limit > 80%
- Rejected order count >= 2

Decision:

- Customer inactive → REJECTED
- Available credit < order amount → REJECTED
- Suspicious/red flag → REVIEW REQUIRED; automatic approval blocked
- No blocking condition + sufficient credit + acceptable history → APPROVED

Use rules + risk classification rather than a single score.

## Roles

SP001 — Salesperson
CO001 — Credit Officer
WH001 — Warehouse
ACC001 — Accounting/Billing
CSH001 — Cashier
MGR001 — Manager
ADM001 — System Admin

Keep incompatible duties separated.

## Database

Preserve the required tables:

Customers
Products
Sales Orders
Sales Order Details
Credit Approvals
Shippings
Shipping Details
Invoices
Cash Receipts

Supporting tables may include:

Users
Roles/Permissions
Payment Terms
Payment Methods
Audit Logs
Customer Credit History
Credit Limit Reviews
Notifications

Use primary keys, foreign keys, unique constraints, and server-side validation.

## Local execution

The project must remain runnable with:

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

Then open:

http://127.0.0.1:5000

Do not introduce a requirement to host the application online just to run the prototype locally.
