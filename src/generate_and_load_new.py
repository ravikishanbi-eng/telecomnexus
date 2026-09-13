import os
import math
import random
import ipaddress
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from faker import Faker

# ============================================================
# TelecomNexus - Production-style Internet Planning data loader
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()

SEED = int(os.getenv("SEED", "20260909"))
CUSTOMERS = int(os.getenv("CUSTOMERS", "10000"))
HISTORICAL_MONTHS = int(os.getenv("HISTORICAL_MONTHS", "12"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2000"))

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "telecomnexus")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")

random.seed(SEED)
fake = Faker("en_IN")
fake.seed_instance(SEED)

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()

# -----------------------------
# Master/reference data
# -----------------------------
STATES = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem", "Tiruchirappalli"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"],
    "Delhi": ["New Delhi", "Delhi"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Kanpur", "Ghaziabad", "Agra", "Varanasi"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer"],
    "Punjab": ["Mohali", "Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
}

CITY_COORDINATES = {
    "Mumbai": (19.0760, 72.8777), "Pune": (18.5204, 73.8567), "Nagpur": (21.1458, 79.0882),
    "Nashik": (19.9975, 73.7898), "Aurangabad": (19.8762, 75.3433),
    "Bengaluru": (12.9716, 77.5946), "Mysuru": (12.2958, 76.6394), "Mangaluru": (12.9141, 74.8560),
    "Hubballi": (15.3647, 75.1240), "Belagavi": (15.8497, 74.4977),
    "Chennai": (13.0827, 80.2707), "Coimbatore": (11.0168, 76.9558), "Madurai": (9.9252, 78.1198),
    "Salem": (11.6643, 78.1460), "Tiruchirappalli": (10.7905, 78.7047),
    "Hyderabad": (17.3850, 78.4867), "Warangal": (17.9689, 79.5941), "Nizamabad": (18.6725, 78.0941),
    "Karimnagar": (18.4386, 79.1288), "Khammam": (17.2473, 80.1514),
    "Ahmedabad": (23.0225, 72.5714), "Surat": (21.1702, 72.8311), "Vadodara": (22.3072, 73.1812),
    "Rajkot": (22.3039, 70.8022), "Gandhinagar": (23.2156, 72.6369),
    "New Delhi": (28.6139, 77.2090), "Delhi": (28.7041, 77.1025),
    "Kolkata": (22.5726, 88.3639), "Howrah": (22.5958, 88.2636), "Durgapur": (23.5204, 87.3119),
    "Siliguri": (26.7271, 88.3953), "Asansol": (23.6739, 86.9524),
    "Lucknow": (26.8467, 80.9462), "Noida": (28.5355, 77.3910), "Kanpur": (26.4499, 80.3319),
    "Ghaziabad": (28.6692, 77.4538), "Agra": (27.1767, 78.0081), "Varanasi": (25.3176, 82.9739),
    "Jaipur": (26.9124, 75.7873), "Jodhpur": (26.2389, 73.0243), "Udaipur": (24.5854, 73.7125),
    "Kota": (25.2138, 75.8648), "Ajmer": (26.4499, 74.6399),
    "Mohali": (30.7046, 76.7179), "Ludhiana": (30.9010, 75.8573), "Amritsar": (31.6340, 74.8723),
    "Jalandhar": (31.3260, 75.5762), "Patiala": (30.3398, 76.3869),
}

PRODUCTS = [
    (1, "FBR100", "Fiber Broadband 100 Mbps", "BROADBAND", "FTTH", 100, 50, 999, 499),
    (2, "FBR300", "Fiber Broadband 300 Mbps", "BROADBAND", "FTTH", 300, 100, 999, 699),
    (3, "FBR500", "Fiber Broadband 500 Mbps", "BROADBAND", "FTTH", 500, 250, 999, 899),
    (4, "FBR1G", "Fiber Broadband 1 Gbps", "BROADBAND", "FTTH", 1000, 500, 1499, 1299),
    (5, "FBR2G", "Fiber Broadband 2 Gbps", "BROADBAND", "FTTH", 2000, 1000, 1999, 1999),
]

# -----------------------------
# Helpers
# -----------------------------
def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def dt(value):
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


def rand_date(start_date, end_date):
    if start_date > end_date:
        return start_date
    return start_date + timedelta(days=random.randint(0, (end_date - start_date).days))


def month_start(d):
    return date(d.year, d.month, 1)


def add_months(d, months):
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def weighted_product():
    return random.choices([1, 2, 3, 4, 5], weights=[28, 30, 24, 14, 4], k=1)[0]


def location():
    state = random.choice(list(STATES.keys()))
    city = random.choice(STATES[state])
    return state, city


def insert_many(cur, sql, rows):
    if not rows:
        return
    execute_values(cur, sql, rows, page_size=BATCH_SIZE)


# -----------------------------
# Connection / cleanup
# -----------------------------
def get_connection():
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )


def clear_all(cur):
    print("[1/7] Clearing existing data...")
    cur.execute("""
        TRUNCATE TABLE
            network.bandwidth_allocation,
            network.ip_assignment,
            network.network_resource,
            network.pon_port,
            network.olt,
            network.pop,
            network.network_site,
            network.ip_pool,
            fin.payment_detail,
            fin.payment,
            fin.gl_ledger,
            inv.invoice_detail,
            inv.invoice,
            trx.transaction_detail,
            trx.transaction,
            crm.contract_rate_schedule,
            crm.contract_detail,
            crm.contract,
            crm.service,
            crm.billing,
            crm.customer,
            prd.rate_schedule,
            prd.product
        RESTART IDENTITY CASCADE
    """)


# -----------------------------
# Product
# -----------------------------
def seed_products(cur):
    print("[2/7] Loading products and rate schedules...")
    product_rows = []
    rate_rows = []
    effective_from = date(TODAY.year, TODAY.month, 1)

    for product_id, code, name, category, technology, down, up, install_fee, monthly in PRODUCTS:
        product_rows.append((
            product_id, code, name, category, technology, down, up,
            money(install_fee), "ACTIVE", NOW, NOW
        ))
        rate_rows.append((
            product_id, product_id, f"STD-{code}", money(monthly), money(install_fee),
            Decimal("18.00"), "INR", effective_from, None, "ACTIVE"
        ))

    insert_many(cur, """
        INSERT INTO prd.product
        (product_id, product_code, product_name, product_category, technology,
         download_speed_mbps, upload_speed_mbps, installation_fee,
         product_status, created_at, updated_at)
        VALUES %s
    """, product_rows)

    insert_many(cur, """
        INSERT INTO prd.rate_schedule
        (rate_schedule_id, product_id, rate_code, monthly_charge, activation_charge,
         tax_percentage, currency, effective_from, effective_to, status)
        VALUES %s
    """, rate_rows)


# -----------------------------
# Customers
# -----------------------------
def seed_customers(cur):
    print(f"[3/7] Creating {CUSTOMERS:,} customers and billing accounts...")
    customer_rows = []
    billing_rows = []

    for customer_id in range(1, CUSTOMERS + 1):
        state, city = location()
        first_name = fake.first_name()
        last_name = fake.last_name()
        customer_type = random.choices(
            ["RESIDENTIAL", "SMB", "ENTERPRISE"],
            weights=[84, 13, 3], k=1
        )[0]
        status = random.choices(
            ["ACTIVE", "INACTIVE", "SUSPENDED"],
            weights=[93, 5, 2], k=1
        )[0]
        customer_since = rand_date(date.today() - timedelta(days=5 * 365), TODAY)
        created_at = dt(customer_since)
        updated_at = min(NOW, created_at + timedelta(days=random.randint(0, 90)))

        customer_rows.append((
            customer_id, f"CUST-{customer_id:08d}", customer_type,
            first_name, last_name,
            f"{first_name.lower()}.{last_name.lower()}{customer_id}@example.com",
            str(random.randint(6000000000, 9999999999)),
            f"{random.randint(1,999)}, {fake.street_name()}",
            city, state, fake.postcode(), "India", status,
            customer_since, created_at, updated_at
        ))

        payment_method = random.choices(
            ["UPI", "CARD", "NET_BANKING", "AUTO_DEBIT","BANK_TRANSFER","CASH"],
            weights=[45, 25, 15, 15, 35 , 5], k=1
        )[0]
        billing_rows.append((
            customer_id, customer_id, "MONTHLY", random.randint(1, 10),
            payment_method, money(random.choice([0, 5000, 10000, 25000, 50000])),
            "INR", "ACTIVE", created_at, updated_at
        ))

        if len(customer_rows) >= BATCH_SIZE:
            insert_many(cur, """
                INSERT INTO crm.customer
                (customer_id, customer_number, customer_type, first_name, last_name,
                 email, phone, address_line1, city, state, postal_code, country,
                 customer_status, customer_since, created_at, updated_at)
                VALUES %s
            """, customer_rows)
            insert_many(cur, """
                INSERT INTO crm.billing
                (billing_account_id, customer_id, billing_cycle, billing_day,
                 payment_method, credit_limit, currency, billing_status, created_at, updated_at)
                VALUES %s
            """, billing_rows)
            customer_rows.clear()
            billing_rows.clear()

    insert_many(cur, """
        INSERT INTO crm.customer
        (customer_id, customer_number, customer_type, first_name, last_name,
         email, phone, address_line1, city, state, postal_code, country,
         customer_status, customer_since, created_at, updated_at)
        VALUES %s
    """, customer_rows)
    insert_many(cur, """
        INSERT INTO crm.billing
        (billing_account_id, customer_id, billing_cycle, billing_day,
         payment_method, credit_limit, currency, billing_status, created_at, updated_at)
        VALUES %s
    """, billing_rows)


def seed_contracts_services(cur):
    contract_rows = []
    detail_rows = []
    rate_rows = []
    service_rows = []
    active_services = []

    product_price = {1: 499, 2: 699, 3: 899, 4: 1299, 5: 1999}
    customer_since = {}
    cur.execute("SELECT customer_id, customer_since, city, state, postal_code FROM crm.customer")
    customer_locations = {}
    for row in cur.fetchall():
        customer_since[row[0]] = row[1]
        customer_locations[row[0]] = (row[2], row[3], row[4])

    for customer_id in range(1, CUSTOMERS + 1):
        product_id = weighted_product()
        start = max(customer_since[customer_id], date(TODAY.year - 2, 1, 1))
        start = min(start, TODAY)
        contract_type = random.choices(
            ["MONTHLY", "12_MONTH", "24_MONTH"], weights=[35, 50, 15], k=1
        )[0]
        if contract_type == "MONTHLY":
            end = None
        elif contract_type == "12_MONTH":
            end = start + timedelta(days=365)
        else:
            end = start + timedelta(days=730)

        # Keep most services active for a useful planning dataset.
        contract_status = "ACTIVE" if end is None or end >= TODAY else "EXPIRED"
        if random.random() < 0.92:
            contract_status = "ACTIVE"
            end = None if contract_type == "MONTHLY" else max(end or TODAY, TODAY + timedelta(days=30))

        contract_id = customer_id
        detail_id = customer_id
        rate_id = customer_id
        service_id = customer_id
        monthly = product_price[product_id]
        agreed_price = money(monthly * random.uniform(0.90, 1.00))

        contract_rows.append((
            contract_id, f"CON-{customer_id:08d}", customer_id,
            contract_type, start, end, contract_status,
            contract_type != "MONTHLY", dt(start), NOW
        ))
        detail_rows.append((
            detail_id, contract_id, 1, product_id, 1,
            agreed_price, money(random.choice([0, 0, 25, 50, 100])),
            Decimal("18.00"), start, end
        ))
        rate_rows.append((
            rate_id, contract_id, detail_id, product_id, start, end, agreed_price
        ))

        city, state, postal_code = customer_locations[customer_id]
        tech = "GPON" if product_id <= 3 else "XG-PON"
        service_status = "ACTIVE" if contract_status == "ACTIVE" else "INACTIVE"
        service_rows.append((
            service_id, customer_id, contract_id, product_id,
            f"FTTH-{customer_id:010d}", "BROADBAND", tech,
            start, None if service_status == "ACTIVE" else end,
            service_status,
            f"{random.randint(1,999)}, {fake.street_name()}",
            city, state, postal_code, dt(start), NOW
        ))
        if service_status == "ACTIVE":
            active_services.append((service_id, customer_id, product_id, start, agreed_price))

        if len(contract_rows) >= BATCH_SIZE:
            insert_many(cur, """
                INSERT INTO crm.contract
                (contract_id, contract_number, customer_id, contract_type,
                 start_date, end_date, contract_status, auto_renew, created_at, updated_at)
                VALUES %s
            """, contract_rows)
            insert_many(cur, """
                INSERT INTO crm.contract_detail
                (contract_detail_id, contract_id, line_number, product_id, quantity,
                 agreed_monthly_price, discount_amount, tax_percent, effective_from, effective_to)
                VALUES %s
            """, detail_rows)
            insert_many(cur, """
                INSERT INTO crm.contract_rate_schedule
                (contract_rate_schedule_id, contract_id, contract_detail_id,
                 rate_schedule_id, effective_from, effective_to, agreed_rate)
                VALUES %s
            """, rate_rows)
            insert_many(cur, """
                INSERT INTO crm.service
                (service_id, customer_id, contract_id, product_id, service_number,
                 service_type, technology, activation_date, deactivation_date,
                 service_status, installation_address, city, state, postal_code,
                 created_at, updated_at)
                VALUES %s
            """, service_rows)
            contract_rows.clear(); detail_rows.clear(); rate_rows.clear(); service_rows.clear()

    insert_many(cur, """
        INSERT INTO crm.contract
        (contract_id, contract_number, customer_id, contract_type,
         start_date, end_date, contract_status, auto_renew, created_at, updated_at)
        VALUES %s
    """, contract_rows)
    insert_many(cur, """
        INSERT INTO crm.contract_detail
        (contract_detail_id, contract_id, line_number, product_id, quantity,
         agreed_monthly_price, discount_amount, tax_percent, effective_from, effective_to)
        VALUES %s
    """, detail_rows)
    insert_many(cur, """
        INSERT INTO crm.contract_rate_schedule
        (contract_rate_schedule_id, contract_id, contract_detail_id,
         rate_schedule_id, effective_from, effective_to, agreed_rate)
        VALUES %s
    """, rate_rows)
    insert_many(cur, """
        INSERT INTO crm.service
        (service_id, customer_id, contract_id, product_id, service_number,
         service_type, technology, activation_date, deactivation_date,
         service_status, installation_address, city, state, postal_code,
         created_at, updated_at)
        VALUES %s
    """, service_rows)

    print(f"       Active services: {len(active_services):,}")
    return active_services


# -----------------------------
# Transactions
# -----------------------------
def seed_transactions(cur, active_services):
    print("[4/7] Creating customer transactions...")
    tx_rows = []
    detail_rows = []
    tx_id = 1
    detail_id = 1
    price = {1: 499, 2: 699, 3: 899, 4: 1299, 5: 1999}

    for service_id, customer_id, product_id, start, agreed_price in active_services:
        tx_date = min(start, TODAY)
        tx_rows.append((
            tx_id, f"TXN-{tx_id:010d}", customer_id, service_id,
            "ACTIVATION", dt(tx_date), "COMPLETED", agreed_price,
            "INR", random.choice(["WEB", "APP", "STORE", "CALL_CENTER"]), dt(tx_date)
        ))
        detail_rows.append((
            detail_id, tx_id, 1, product_id, None, product_id, 1,
            agreed_price, money(0), money(agreed_price * Decimal("0.18")),
            money(agreed_price * Decimal("1.18"))
        ))
        tx_id += 1; detail_id += 1

        # Occasional upgrade/downgrade events make the transaction history useful.
        if random.random() < 0.12:
            new_product = random.choice([p for p in range(1, 6) if p != product_id])
            tx_type = "UPGRADE" if new_product > product_id else "DOWNGRADE"
            amount = money(price[new_product])
            event_date = min(TODAY, tx_date + timedelta(days=random.randint(30, 300)))
            tx_rows.append((
                tx_id, f"TXN-{tx_id:010d}", customer_id, service_id,
                tx_type, dt(event_date), "COMPLETED", amount, "INR",
                random.choice(["WEB", "APP", "CALL_CENTER"]), dt(event_date)
            ))
            detail_rows.append((
                detail_id, tx_id, 1, new_product, product_id, new_product, 1,
                amount, money(0), money(amount * Decimal("0.18")),
                money(amount * Decimal("1.18"))
            ))
            tx_id += 1; detail_id += 1

        if len(tx_rows) >= BATCH_SIZE:
            insert_many(cur, """
                INSERT INTO trx.transaction
                (transaction_id, transaction_number, customer_id, service_id,
                 transaction_type, transaction_date, transaction_status, amount,
                 currency, channel, created_at)
                VALUES %s
            """, tx_rows)
            insert_many(cur, """
                INSERT INTO trx.transaction_detail
                (transaction_detail_id, transaction_id, line_number, product_id,
                 old_product_id, new_product_id, quantity, unit_price,
                 discount_amount, tax_amount, amount)
                VALUES %s
            """, detail_rows)
            tx_rows.clear(); detail_rows.clear()

    insert_many(cur, """
        INSERT INTO trx.transaction
        (transaction_id, transaction_number, customer_id, service_id,
         transaction_type, transaction_date, transaction_status, amount,
         currency, channel, created_at)
        VALUES %s
    """, tx_rows)
    insert_many(cur, """
        INSERT INTO trx.transaction_detail
        (transaction_detail_id, transaction_id, line_number, product_id,
         old_product_id, new_product_id, quantity, unit_price,
         discount_amount, tax_amount, amount)
        VALUES %s
    """, detail_rows)


# -----------------------------
# Billing / finance
# -----------------------------
def seed_invoices_payments_gl(cur, active_services):
    print("[5/7] Creating historical invoices, payments and GL...")
    invoice_rows = []
    detail_rows = []
    payment_rows = []
    payment_detail_rows = []
    gl_rows = []

    invoice_id = payment_id = payment_detail_id = gl_id = 1
    price = {1: 499, 2: 699, 3: 899, 4: 1299, 5: 1999}
    service_map = {s[0]: s for s in active_services}

    start_month = add_months(month_start(TODAY), -(HISTORICAL_MONTHS - 1))

    for service_id, customer_id, product_id, activation_date, agreed_price in active_services:
        first_month = month_start(activation_date)
        if first_month < start_month:
            first_month = start_month

        m = first_month
        while m <= month_start(TODAY):
            period_start = m
            period_end = add_months(m, 1) - timedelta(days=1)
            charge = money(agreed_price)
            tax = money(charge * Decimal("0.18"))
            total = money(charge + tax)
            invoice_status = random.choices(
                ["PAID", "OPEN", "OVERDUE", "PARTIALLY_PAID"],
                weights=[82, 8, 6, 4], k=1
            )[0]
            invoice_date = period_start
            due_date = period_start + timedelta(days=15)
            invoice_rows.append((
                invoice_id, f"INV-{invoice_id:010d}", customer_id, customer_id,
                invoice_date, due_date, period_start, period_end,
                charge, money(0), tax, total, invoice_status,
                dt(invoice_date), NOW
            ))
            detail_rows.append((
                invoice_id, invoice_id, 1, service_id, product_id,
                "RECURRING", f"Monthly FTTH service - {PRODUCTS[product_id-1][1]}",
                1, charge, money(0), tax, total
            ))

            if invoice_status in ("PAID", "PARTIALLY_PAID"):
                paid_amount = total if invoice_status == "PAID" else money(total * random.uniform(0.30, 0.80))
                payment_date = min(TODAY, due_date + timedelta(days=random.randint(-5, 20)))
                method = random.choice(["UPI", "CARD", "NET_BANKING", "AUTO_DEBIT","BANK_TRANSFER","CASH"])
                payment_rows.append((
                    payment_id, f"PAY-{payment_id:010d}", customer_id,
                    payment_date, method, "SUCCESS", paid_amount, "INR",
                    f"GW-{payment_id:012d}", dt(payment_date)
                ))
                payment_detail_rows.append((
                    payment_detail_id, payment_id, invoice_id,
                    paid_amount, "ALLOCATED", dt(payment_date)
                ))
                payment_id += 1; payment_detail_id += 1

            gl_rows.extend([
                (gl_id, None, invoice_date, "400100", "Broadband Revenue", total, money(0), "INR",
                 f"INV-{invoice_id:010d}", "Monthly broadband revenue", dt(invoice_date)),
                (gl_id + 1, None, invoice_date, "110100", "Accounts Receivable", money(0), total, "INR",
                 f"INV-{invoice_id:010d}", "Invoice receivable", dt(invoice_date)),
            ])
            gl_id += 2
            invoice_id += 1
            m = add_months(m, 1)

            if len(invoice_rows) >= BATCH_SIZE:
                insert_many(cur, """
                    INSERT INTO inv.invoice
                    (invoice_id, invoice_number, billing_account_id, customer_id,
                     invoice_date, due_date, billing_period_start, billing_period_end,
                     subtotal, discount_amount, tax_amount, total_amount, invoice_status,
                     created_at, updated_at)
                    VALUES %s
                """, invoice_rows)
                insert_many(cur, """
                    INSERT INTO inv.invoice_detail
                    (invoice_detail_id, invoice_id, line_number, service_id, product_id,
                     charge_type, description, quantity, unit_price, discount_amount,
                     tax_amount, line_total)
                    VALUES %s
                """, detail_rows)
                insert_many(cur, """
                    INSERT INTO fin.payment
                    (payment_id, payment_number, customer_id, payment_date,
                     payment_method, payment_status, amount, currency,
                     gateway_reference, created_at)
                    VALUES %s
                """, payment_rows)
                insert_many(cur, """
                    INSERT INTO fin.payment_detail
                    (payment_detail_id, payment_id, invoice_id, allocated_amount,
                     allocation_status, created_at)
                    VALUES %s
                """, payment_detail_rows)
                insert_many(cur, """
                    INSERT INTO fin.gl_ledger
                    (gl_entry_id, transaction_id, entry_date, account_code, account_name,
                     debit_amount, credit_amount, currency, reference_number,
                     description, created_at)
                    VALUES %s
                """, gl_rows)
                invoice_rows.clear(); detail_rows.clear(); payment_rows.clear(); payment_detail_rows.clear(); gl_rows.clear()

    insert_many(cur, """
        INSERT INTO inv.invoice
        (invoice_id, invoice_number, billing_account_id, customer_id,
         invoice_date, due_date, billing_period_start, billing_period_end,
         subtotal, discount_amount, tax_amount, total_amount, invoice_status,
         created_at, updated_at)
        VALUES %s
    """, invoice_rows)
    insert_many(cur, """
        INSERT INTO inv.invoice_detail
        (invoice_detail_id, invoice_id, line_number, service_id, product_id,
         charge_type, description, quantity, unit_price, discount_amount,
         tax_amount, line_total)
        VALUES %s
    """, detail_rows)
    insert_many(cur, """
        INSERT INTO fin.payment
        (payment_id, payment_number, customer_id, payment_date,
         payment_method, payment_status, amount, currency,
         gateway_reference, created_at)
        VALUES %s
    """, payment_rows)
    insert_many(cur, """
        INSERT INTO fin.payment_detail
        (payment_detail_id, payment_id, invoice_id, allocated_amount,
         allocation_status, created_at)
        VALUES %s
    """, payment_detail_rows)
    insert_many(cur, """
        INSERT INTO fin.gl_ledger
        (gl_entry_id, transaction_id, entry_date, account_code, account_name,
         debit_amount, credit_amount, currency, reference_number,
         description, created_at)
        VALUES %s
    """, gl_rows)


# -----------------------------
# Network topology
# -----------------------------
def seed_network(cur, active_services):
    print("[6/7] Building production-style network topology...")

    required_services = len(active_services)
    spare_factor = 1.20
    required_ports = math.ceil(required_services * spare_factor)
    PON_PORTS_PER_OLT = 16
    OLT_CAPACITY_GBPS = 10.0
    required_olts = max(1, math.ceil(required_ports / PON_PORTS_PER_OLT))

    print(f"       Active services       : {required_services:,}")
    print(f"       Required PON ports    : {required_ports:,} (20% spare)")
    print(f"       Required OLTs         : {required_olts:,}")
    print(f"       Planned PON capacity  : {required_olts * PON_PORTS_PER_OLT:,} ports")

    city_locations = [(state, city) for state, cities in STATES.items() for city in cities]
    random.shuffle(city_locations)

    site_rows = []
    pop_rows = []
    olt_rows = []
    pon_rows = []

    site_id = 1
    pop_id = 1
    olt_id = 1
    pon_id = 1
    olt_remaining = required_olts
    site_index = 1

    vendors = [("Huawei", "MA5800-X7"), ("Nokia", "Lightspan FX"), ("ZTE", "C600")]

    # IMPORTANT: olt_remaining is decremented exactly once per OLT.
    # The previous version decremented it at site level AND OLT level,
    # which caused insufficient PON capacity.
    while olt_remaining > 0:
        state, city = city_locations[(site_index - 1) % len(city_locations)]
        site_olts = min(olt_remaining, random.randint(4, 8))

        lat, lon = CITY_COORDINATES.get(city, (20.5937, 78.9629))
        lat += random.uniform(-0.03, 0.03)
        lon += random.uniform(-0.03, 0.03)

        site_rows.append((
            site_id, f"SITE-{site_id:05d}", f"{city} Network Site",
            city, state, str(random.randint(110000, 899999)),
            round(lat, 6), round(lon, 6), "ACTIVE", NOW
        ))

        # Distribute every OLT assigned to this site across its POPs.
        pops_for_site = 1 if site_olts <= 4 else random.randint(1, 2)
        remaining_site_olts = site_olts

        for pop_number in range(1, pops_for_site + 1):
            if remaining_site_olts <= 0:
                break

            # The final POP gets every remaining OLT so none are lost.
            if pop_number == pops_for_site:
                olts_for_pop = remaining_site_olts
            else:
                olts_for_pop = min(remaining_site_olts, random.randint(2, 4))

            # POP capacity is derived from OLT count.
            pop_capacity_gbps = round(olts_for_pop * OLT_CAPACITY_GBPS, 2)
            pop_utilization = random.uniform(0.35, 0.85)
            pop_used_capacity_gbps = round(pop_capacity_gbps * pop_utilization, 2)
            pop_used_capacity_gbps = min(pop_used_capacity_gbps, pop_capacity_gbps)

            pop_rows.append((
                pop_id, site_id, f"POP-{pop_id:05d}",
                f"{city} POP {pop_number}",
                pop_capacity_gbps, pop_used_capacity_gbps,
                "N+1", "ACTIVE", NOW
            ))

            for _ in range(olts_for_pop):
                vendor, model = random.choice(vendors)
                total_ports = PON_PORTS_PER_OLT

                # Service assignment is deterministic enough for reproducibility,
                # while still random-looking. Only active services get ports.
                olt_rows.append((
                    olt_id, pop_id, f"OLT-{olt_id:06d}", vendor, model,
                    total_ports, 0, OLT_CAPACITY_GBPS, "ACTIVE", NOW
                ))

                for port_number in range(1, total_ports + 1):
                    technology = "GPON" if random.random() < 0.75 else "XG-PON"
                    capacity = 2.5 if technology == "GPON" else 10.0
                    pon_rows.append((
                        pon_id, olt_id, port_number, technology,
                        capacity, 0.0, "AVAILABLE"
                    ))
                    pon_id += 1

                olt_id += 1
                olt_remaining -= 1
                remaining_site_olts -= 1

            pop_id += 1

        site_id += 1
        site_index += 1

        if len(site_rows) >= BATCH_SIZE:
            insert_many(cur, """
                INSERT INTO network.network_site
                (site_id, site_code, site_name, city, state, postal_code,
                 latitude, longitude, site_status, created_at)
                VALUES %s
            """, site_rows)
            insert_many(cur, """
                INSERT INTO network.pop
                (pop_id, site_id, pop_code, pop_name, capacity_gbps,
                 used_capacity_gbps, redundancy_level, status, created_at)
                VALUES %s
            """, pop_rows)
            insert_many(cur, """
                INSERT INTO network.olt
                (olt_id, pop_id, olt_code, vendor, model, total_pon_ports,
                 used_pon_ports, total_capacity_gbps, status, created_at)
                VALUES %s
            """, olt_rows)
            insert_many(cur, """
                INSERT INTO network.pon_port
                (pon_port_id, olt_id, port_number, technology,
                 capacity_gbps, used_capacity_gbps, status)
                VALUES %s
            """, pon_rows)
            site_rows.clear(); pop_rows.clear(); olt_rows.clear(); pon_rows.clear()

    insert_many(cur, """
        INSERT INTO network.network_site
        (site_id, site_code, site_name, city, state, postal_code,
         latitude, longitude, site_status, created_at)
        VALUES %s
    """, site_rows)
    insert_many(cur, """
        INSERT INTO network.pop
        (pop_id, site_id, pop_code, pop_name, capacity_gbps,
         used_capacity_gbps, redundancy_level, status, created_at)
        VALUES %s
    """, pop_rows)
    insert_many(cur, """
        INSERT INTO network.olt
        (olt_id, pop_id, olt_code, vendor, model, total_pon_ports,
         used_pon_ports, total_capacity_gbps, status, created_at)
        VALUES %s
    """, olt_rows)
    insert_many(cur, """
        INSERT INTO network.pon_port
        (pon_port_id, olt_id, port_number, technology,
         capacity_gbps, used_capacity_gbps, status)
        VALUES %s
    """, pon_rows)

    # IP pools. IPv4 pools intentionally have sufficient aggregate capacity.
    ip_pool_rows = [
        (1, "CGNAT-100-64-00", "100.64.0.0/20", "IPv4", 4096, 0, "PAN-INDIA", "ACTIVE", NOW),
        (2, "CGNAT-100-64-16", "100.64.16.0/20", "IPv4", 4096, 0, "PAN-INDIA", "ACTIVE", NOW),
        (3, "CGNAT-100-64-32", "100.64.32.0/20", "IPv4", 4096, 0, "PAN-INDIA", "ACTIVE", NOW),
        (4, "IPV6-2001-DB8-100", "2001:db8:100::/48", "IPv6", 65536, 0, "PAN-INDIA", "ACTIVE", NOW),
    ]
    insert_many(cur, """
        INSERT INTO network.ip_pool
        (ip_pool_id, pool_name, cidr, address_family, total_addresses,
         allocated_addresses, region, status, created_at)
        VALUES %s
    """, ip_pool_rows)

    # Assign services to AVAILABLE PON ports. Exactly one service per port in
    # this synthetic model, with 20% spare capacity retained.
    available_port_rows = [r for r in pon_rows if r[6] == "AVAILABLE"]
    # pon_rows was flushed above if BATCH_SIZE was reached, so fetch from DB.
    cur.execute("""
        SELECT pon_port_id, olt_id, capacity_gbps
        FROM network.pon_port
        WHERE status = 'AVAILABLE'
        ORDER BY pon_port_id
    """)
    available_ports = cur.fetchall()
    if len(available_ports) < required_services:
        raise RuntimeError(
            f"Insufficient PON capacity: required {required_services:,}, "
            f"available {len(available_ports):,}."
        )

    service_rows = []
    ip_assignment_rows = []
    bandwidth_rows = []
    service_port_pairs = []

    # Round-robin across IPv4 pools prevents one /20 from being exhausted
    # while other pools still contain addresses.
    ipv4_pools = [1, 2, 3]
    pool_networks = {
        1: ipaddress.ip_network("100.64.0.0/20"),
        2: ipaddress.ip_network("100.64.16.0/20"),
        3: ipaddress.ip_network("100.64.32.0/20"),
    }
    pool_counters = {1: 1, 2: 1, 3: 1}
    pool_allocated = {1: 0, 2: 0, 3: 0}

    product_speed = {p[0]: p[5] for p in PRODUCTS}

    for idx, service in enumerate(active_services):
        service_id, customer_id, product_id, start, agreed_price = service
        pon_id, olt_id, pon_capacity = available_ports[idx]
        service_port_pairs.append((service_id, pon_id, olt_id, product_id))

        # Network resource IDs start at 1 and match service IDs in this dataset.
        committed = float(product_speed[product_id])
        provisioned = committed
        resource_status = "ACTIVE"
        service_rows.append((
            service_id, service_id, pon_id, "FTTH_ACCESS",
            provisioned, committed, resource_status, dt(start)
        ))

        utilization = random.uniform(25.0, 88.0)
        used_mbps = round(committed * utilization / 100.0, 2)
        bandwidth_rows.append((
            service_id, service_id, service_id,
            round(committed, 2), round(committed, 2),
            round(utilization, 2), TODAY
        ))

        pool_id = ipv4_pools[idx % len(ipv4_pools)]
        network = pool_networks[pool_id]
        counter = pool_counters[pool_id]
        ip_value = int(network.network_address) + counter
        if ip_value >= int(network.broadcast_address):
            raise RuntimeError(f"IPv4 pool {pool_id} exhausted")
        ip_address = str(ipaddress.ip_address(ip_value))
        pool_counters[pool_id] += 1
        pool_allocated[pool_id] += 1

        ip_assignment_rows.append((
            idx + 1, pool_id, service_id, ip_address,
            "PRIMARY", dt(start), None
        ))

    insert_many(cur, """
        INSERT INTO network.network_resource
        (resource_id, service_id, pon_port_id, resource_type,
         provisioned_speed_mbps, committed_speed_mbps, status, activated_at)
        VALUES %s
    """, service_rows)
    insert_many(cur, """
        INSERT INTO network.bandwidth_allocation
        (allocation_id, service_id, resource_id, peak_bandwidth_mbps,
         committed_bandwidth_mbps, utilization_percent, measurement_date)
        VALUES %s
    """, bandwidth_rows)
    insert_many(cur, """
        INSERT INTO network.ip_assignment
        (ip_assignment_id, ip_pool_id, service_id, ip_address,
         assignment_type, assigned_at, released_at)
        VALUES %s
    """, ip_assignment_rows)

    # Mark assigned PON ports ACTIVE and update OLT utilization.
    assigned_pon_ids = [x[1] for x in service_port_pairs]
    if assigned_pon_ids:
        cur.execute("""
            UPDATE network.pon_port
            SET status = 'ACTIVE',
                used_capacity_gbps = capacity_gbps
            WHERE pon_port_id = ANY(%s)
        """, (assigned_pon_ids,))

    cur.execute("""
        UPDATE network.olt o
        SET used_pon_ports = x.used_ports
        FROM (
            SELECT olt_id, COUNT(*) AS used_ports
            FROM network.pon_port
            WHERE status = 'ACTIVE'
            GROUP BY olt_id
        ) x
        WHERE o.olt_id = x.olt_id
    """)

    cur.execute("""
        UPDATE network.olt
        SET used_pon_ports = COALESCE(used_pon_ports, 0)
    """)

    # Keep POP used capacity mathematically consistent with the actual OLT
    # utilization. Never allow used capacity to exceed total capacity.
    cur.execute("""
        UPDATE network.pop p
        SET used_capacity_gbps = LEAST(
            p.capacity_gbps,
            COALESCE(x.used_capacity_gbps, 0)
        )
        FROM (
            SELECT
                o.pop_id,
                SUM(o.total_capacity_gbps *
                    CASE WHEN o.total_pon_ports = 0 THEN 0
                         ELSE o.used_pon_ports::numeric / o.total_pon_ports
                    END) AS used_capacity_gbps
            FROM network.olt o
            GROUP BY o.pop_id
        ) x
        WHERE p.pop_id = x.pop_id
    """)

    # Update POPs without any active OLT usage to zero.
    cur.execute("""
        UPDATE network.pop p
        SET used_capacity_gbps = 0
        WHERE NOT EXISTS (
            SELECT 1 FROM network.olt o
            WHERE o.pop_id = p.pop_id AND o.used_pon_ports > 0
        )
    """)

    # Update IP pool allocation counts.
    for pool_id, allocated in pool_allocated.items():
        cur.execute("""
            UPDATE network.ip_pool
            SET allocated_addresses = %s
            WHERE ip_pool_id = %s
        """, (allocated, pool_id))

    # Final topology validations.
    cur.execute("SELECT COUNT(*) FROM network.network_site")
    site_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM network.pop")
    pop_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM network.olt")
    olt_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM network.pon_port")
    pon_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM network.network_resource")
    resource_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM network.ip_assignment")
    ip_count = cur.fetchone()[0]

    if olt_count < required_olts:
        raise RuntimeError(f"OLT validation failed: required {required_olts}, generated {olt_count}")
    if pon_count < required_services:
        raise RuntimeError(f"PON validation failed: required {required_services}, generated {pon_count}")
    if resource_count != required_services:
        raise RuntimeError(f"Resource validation failed: expected {required_services}, generated {resource_count}")
    if ip_count != required_services:
        raise RuntimeError(f"IP assignment validation failed: expected {required_services}, generated {ip_count}")

    cur.execute("""
        SELECT COUNT(*)
        FROM network.pop
        WHERE used_capacity_gbps > capacity_gbps
    """)
    invalid_pops = cur.fetchone()[0]
    if invalid_pops:
        raise RuntimeError(f"POP capacity validation failed: {invalid_pops} POPs exceed capacity")

    print(f"       Sites generated         : {site_count:,}")
    print(f"       POPs generated          : {pop_count:,}")
    print(f"       OLTs generated          : {olt_count:,}")
    print(f"       PON ports generated     : {pon_count:,}")
    print(f"       Network resources       : {resource_count:,}")
    print(f"       IP assignments          : {ip_count:,}")
    print("       Network validation      : PASS")


# -----------------------------
# Final summary
# -----------------------------
def print_summary(cur):
    print("[7/7] Final validation and summary...")
    checks = [
        ("Customers", "SELECT COUNT(*) FROM crm.customer"),
        ("Billing accounts", "SELECT COUNT(*) FROM crm.billing"),
        ("Contracts", "SELECT COUNT(*) FROM crm.contract"),
        ("Services", "SELECT COUNT(*) FROM crm.service"),
        ("Transactions", "SELECT COUNT(*) FROM trx.transaction"),
        ("Invoices", "SELECT COUNT(*) FROM inv.invoice"),
        ("Payments", "SELECT COUNT(*) FROM fin.payment"),
        ("GL entries", "SELECT COUNT(*) FROM fin.gl_ledger"),
        ("Network sites", "SELECT COUNT(*) FROM network.network_site"),
        ("POPs", "SELECT COUNT(*) FROM network.pop"),
        ("OLTs", "SELECT COUNT(*) FROM network.olt"),
        ("PON ports", "SELECT COUNT(*) FROM network.pon_port"),
        ("Network resources", "SELECT COUNT(*) FROM network.network_resource"),
        ("IP assignments", "SELECT COUNT(*) FROM network.ip_assignment"),
    ]

    for label, sql in checks:
        cur.execute(sql)
        print(f"       {label:<24}: {cur.fetchone()[0]:,}")

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'AVAILABLE'),
            COUNT(*) FILTER (WHERE status = 'ACTIVE')
        FROM network.pon_port
    """)
    available, active = cur.fetchone()
    print(f"       Available PON ports     : {available:,}")
    print(f"       Active PON ports        : {active:,}")

    cur.execute("""
        SELECT COUNT(*)
        FROM network.pop
        WHERE used_capacity_gbps > capacity_gbps
    """)
    print(f"       Invalid POP capacities  : {cur.fetchone()[0]:,}")

    cur.execute("""
        SELECT ip_pool_id, pool_name, total_addresses, allocated_addresses
        FROM network.ip_pool
        ORDER BY ip_pool_id
    """)
    print("       IP pool utilization:")
    for row in cur.fetchall():
        print(f"         Pool {row[0]} {row[1]:<22} {row[3]:>6,}/{row[2]:<6,}")


# -----------------------------
# Main
# -----------------------------
def main():
    print("=" * 72)
    print("TelecomNexus - Internet Planning Production Data Loader")
    print("=" * 72)
    print(f"Database : {PGDATABASE}@{PGHOST}:{PGPORT}")
    print(f"Customers: {CUSTOMERS:,}")
    print(f"Seed     : {SEED}")

    conn = None
    try:
        conn = get_connection()
        conn.autocommit = False
        cur = conn.cursor()

        clear_all(cur)
        seed_products(cur)
        seed_customers(cur)
        active_services = seed_contracts_services(cur)
        seed_transactions(cur, active_services)
        seed_invoices_payments_gl(cur, active_services)
        seed_network(cur, active_services)
        print_summary(cur)

        conn.commit()
        cur.close()
        print("=" * 72)
        print("LOAD COMPLETED SUCCESSFULLY")
        print("=" * 72)

    except Exception as exc:
        if conn:
            conn.rollback()
        print("=" * 72)
        print("LOAD FAILED - TRANSACTION ROLLED BACK")
        print(f"ERROR: {exc}")
        print("=" * 72)
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
