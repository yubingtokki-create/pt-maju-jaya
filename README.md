# PT Maju Jaya — Integrated AIS Revenue Cycle Prototype

A local Flask + SQLite Accounting Information System prototype for the Revenue Cycle:

Customer → Sales Order → Credit Approval → Shipping → Invoice → Cash Receipt → Reports

## Features

- Employee authentication with hashed passwords
- Role-based authorization
- Segregation of duties
- Customer/product master data
- Sales Order + automatic calculation
- Credit assessment using credit availability + historical indicators
- Suspicious/red-flag rules
- Shipping control
- Invoice traceability
- Partial/full cash receipt
- Automatic AR status
- Audit trail
- Dashboard and reports
- SQLite relational database with foreign keys
- Seeded demo users and transactions

## Demo accounts

All demo passwords are:

`password`

| Employee ID | Role |
|---|---|
| SP001 | Salesperson |
| CO001 | Credit Officer |
| WH001 | Warehouse |
| ACC001 | Accounting |
| CSH001 | Cashier |
| MGR001 | Manager |
| ADM001 | System Admin |

## Run locally

### Windows

1. Install Python 3.11+.
2. Open Command Prompt / PowerShell in this folder.
3. Create a virtual environment:

```bash
python -m venv .venv
```

4. Activate it:

```bash
.venv\Scripts\activate
```

5. Install dependencies:

```bash
pip install -r requirements.txt
```

6. Start:

```bash
python app.py
```

7. Open:

`http://127.0.0.1:5000`

The SQLite database is created automatically as `maju_jaya.db`.

## Important demo flow

1. Login as `SP001`
2. Create a credit Sales Order for the normal demo customer.
3. Logout.
4. Login as `CO001` and approve the order.
5. Login as `WH001` and create Shipping.
6. Login as `ACC001` and issue Invoice.
7. Login as `CSH001` and record a partial payment.
8. Record the remaining payment.
9. Open Dashboard / Reports.

The system also seeds a suspicious customer to demonstrate that sufficient credit availability alone does not produce automatic approval.

## Reset database

Stop Flask and delete `maju_jaya.db`, then run:

```bash
python app.py
```

The database will be recreated and seeded.
