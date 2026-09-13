import os
import random
from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

SEED = int(os.getenv("SEED", "20260909"))
RECORDS_PER_DAY = int(os.getenv("TRANSACTIONS_PER_DAY", "50"))

random.seed(SEED)

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()

BATCH_SIZE = 100

DB = {
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def money(value):
    """
    Round monetary values to 2 decimal places.
    """
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def get_max_id(cur, table_name, column_name):
    """
    Get the current maximum ID from a table.
    """

    sql = f"""
        SELECT COALESCE(MAX({column_name}), 0)
        FROM {table_name}
    """

    cur.execute(sql)

    return cur.fetchone()[0]


def get_active_services(cur):
    """
    Get existing active services along with their product details.

    Returns:
        service_id
        customer_id
        product_id
        activation_date
        agreed_monthly_price
    """

    cur.execute("""
        SELECT
            s.service_id,
            s.customer_id,
            s.product_id,
            s.activation_date,
            COALESCE(
                crs.agreed_rate,
                rs.monthly_charge
            ) AS monthly_price
        FROM crm.service s

        LEFT JOIN crm.contract_rate_schedule crs
            ON s.contract_id = crs.contract_id
           AND (
                crs.effective_to IS NULL
                OR crs.effective_to >= CURRENT_DATE
           )

        LEFT JOIN prd.rate_schedule rs
            ON s.product_id = rs.product_id
           AND rs.status = 'ACTIVE'

        WHERE s.service_status = 'ACTIVE'

        ORDER BY s.service_id
    """)

    return cur.fetchall()


def get_product_details(cur):
    """
    Get product information.

    Used mainly for transaction generation.
    """

    cur.execute("""
        SELECT
            product_id,
            product_code,
            product_name,
            download_speed_mbps,
            upload_speed_mbps
        FROM prd.product
        WHERE product_status = 'ACTIVE'
        ORDER BY product_id
    """)

    return cur.fetchall()


# ============================================================
# TRANSACTION TYPE LOGIC
# ============================================================

def generate_transaction_type():
    """
    Generate a realistic transaction type.

    Most daily telecom transactions will be renewals,
    with smaller percentages of upgrades, downgrades,
    activations and reconnections.
    """

    transaction_type = random.choices(
        [
            "RENEWAL",
            "UPGRADE",
            "DOWNGRADE",
            "ACTIVATION",
            "RECONNECTION"
        ],
        weights=[
            65,   # Renewal
            12,   # Upgrade
            5,    # Downgrade
            13,   # Activation
            5     # Reconnection
        ],
        k=1
    )[0]

    return transaction_type


# ============================================================
# PRODUCT CHANGE LOGIC
# ============================================================

def calculate_product_change(transaction_type, current_product_id):
    """
    Determine old/new product IDs.

    Product IDs:
        1 = FBR100
        2 = FBR300
        3 = FBR500
        4 = FBR1G
        5 = FBR2G
    """

    old_product_id = None
    new_product_id = current_product_id

    if transaction_type == "UPGRADE":

        old_product_id = current_product_id

        if current_product_id < 5:
            new_product_id = current_product_id + 1
        else:
            # Already on highest plan
            new_product_id = current_product_id

    elif transaction_type == "DOWNGRADE":

        old_product_id = current_product_id

        if current_product_id > 1:
            new_product_id = current_product_id - 1
        else:
            # Already on lowest plan
            new_product_id = current_product_id

    elif transaction_type == "RENEWAL":

        old_product_id = None
        new_product_id = current_product_id

    elif transaction_type == "ACTIVATION":

        old_product_id = None
        new_product_id = current_product_id

    elif transaction_type == "RECONNECTION":

        old_product_id = None
        new_product_id = current_product_id

    return old_product_id, new_product_id


# ============================================================
# MAIN TRANSACTION GENERATOR
# ============================================================

def generate_daily_transactions(
    cur,
    transaction_date,
    records_per_day=50
):
    """
    Generate daily transactions and transaction details.

    Exactly `records_per_day` transactions are created.
    """

    print()
    print("=" * 70)
    print(f"Generating transactions for {transaction_date}")
    print("=" * 70)

    # --------------------------------------------------------
    # Get existing IDs
    # --------------------------------------------------------

    max_transaction_id = get_max_id(
        cur,
        "trx.transaction",
        "transaction_id"
    )

    max_transaction_detail_id = get_max_id(
        cur,
        "trx.transaction_detail",
        "transaction_detail_id"
    )

    print(f"Current max transaction_id       : {max_transaction_id}")
    print(f"Current max transaction_detail_id: {max_transaction_detail_id}")

    # --------------------------------------------------------
    # Get active services
    # --------------------------------------------------------

    services = get_active_services(cur)

    if not services:
        raise RuntimeError(
            "No ACTIVE services found in crm.service."
        )

    print(f"Available active services        : {len(services)}")

    # --------------------------------------------------------
    # Get products
    # --------------------------------------------------------

    products = get_product_details(cur)

    product_price = {}

    # Get prices from rate_schedule
    cur.execute("""
        SELECT
            product_id,
            monthly_charge
        FROM prd.rate_schedule
        WHERE status = 'ACTIVE'
    """)

    for product_id, monthly_charge in cur.fetchall():
        product_price[product_id] = Decimal(str(monthly_charge))

    # --------------------------------------------------------
    # Prepare rows
    # --------------------------------------------------------

    transaction_rows = []
    transaction_detail_rows = []

    transaction_id = max_transaction_id + 1
    transaction_detail_id = max_transaction_detail_id + 1

    channels = [
        "WEB",
        "APP",
        "CALL_CENTER",
        "STORE",
        "PARTNER",
        "API"
    ]

    # --------------------------------------------------------
    # Generate records
    # --------------------------------------------------------

    selected_services = random.sample(
        services,
        min(records_per_day, len(services))
    )

    for service in selected_services:

        (
            service_id,
            customer_id,
            product_id,
            activation_date,
            monthly_price
        ) = service

        # ----------------------------------------------------
        # Transaction type
        # ----------------------------------------------------

        transaction_type = generate_transaction_type()

        # ----------------------------------------------------
        # Make sure activation transactions make sense
        # ----------------------------------------------------

        if transaction_type == "ACTIVATION":

            # Don't create activation before service activation
            if activation_date and activation_date > transaction_date:
                transaction_type = "RENEWAL"

        # ----------------------------------------------------
        # Product change
        # ----------------------------------------------------

        old_product_id, new_product_id = calculate_product_change(
            transaction_type,
            product_id
        )

        # ----------------------------------------------------
        # Amount
        # ----------------------------------------------------

        if monthly_price is None:
            monthly_price = product_price.get(
                product_id,
                Decimal("499.00")
            )

        if transaction_type in (
            "RENEWAL",
            "ACTIVATION"
        ):
            amount = money(monthly_price)

        elif transaction_type == "RECONNECTION":
            amount = money(
                monthly_price * Decimal("0.50")
            )

        elif transaction_type in (
            "UPGRADE",
            "DOWNGRADE"
        ):

            new_price = product_price.get(
                new_product_id,
                monthly_price
            )

            amount = money(new_price)

        else:
            amount = money(monthly_price)

        # ----------------------------------------------------
        # Transaction number
        # ----------------------------------------------------

        transaction_number = (
            f"TXN-{transaction_id:010d}"
        )

        # ----------------------------------------------------
        # Transaction
        # ----------------------------------------------------

        transaction_rows.append(
            (
                transaction_id,
                transaction_number,
                customer_id,
                service_id,
                transaction_type,
                transaction_date,
                "COMPLETED",
                amount,
                "INR",
                random.choice(channels),
                NOW
            )
        )

        # ----------------------------------------------------
        # Discount
        # ----------------------------------------------------

        discount_percent = random.choice(
            [0, 0, 0, 0.05, 0.10]
        )

        discount_amount = money(
            amount * Decimal(str(discount_percent))
        )

        taxable_amount = money(
            amount - discount_amount
        )

        tax_amount = money(
            taxable_amount * Decimal("0.18")
        )

        final_amount = money(
            taxable_amount + tax_amount
        )

        # ----------------------------------------------------
        # Transaction detail
        # ----------------------------------------------------

        transaction_detail_rows.append(
            (
                transaction_detail_id,
                transaction_id,
                1,
                new_product_id,
                old_product_id,
                new_product_id,
                1,
                amount,
                discount_amount,
                tax_amount,
                final_amount
            )
        )

        transaction_id += 1
        transaction_detail_id += 1

    # --------------------------------------------------------
    # Insert transactions
    # --------------------------------------------------------

    if transaction_rows:

        execute_values(
            cur,
            """
            INSERT INTO trx.transaction
            (
                transaction_id,
                transaction_number,
                customer_id,
                service_id,
                transaction_type,
                transaction_date,
                transaction_status,
                amount,
                currency,
                channel,
                created_at
            )
            VALUES %s
            """,
            transaction_rows,
            page_size=BATCH_SIZE
        )

    # --------------------------------------------------------
    # Insert transaction details
    # --------------------------------------------------------

    if transaction_detail_rows:

        execute_values(
            cur,
            """
            INSERT INTO trx.transaction_detail
            (
                transaction_detail_id,
                transaction_id,
                line_number,
                product_id,
                old_product_id,
                new_product_id,
                quantity,
                unit_price,
                discount_amount,
                tax_amount,
                amount
            )
            VALUES %s
            """,
            transaction_detail_rows,
            page_size=BATCH_SIZE
        )

    print()
    print(f"Transactions inserted       : {len(transaction_rows)}")
    print(f"Transaction details inserted: {len(transaction_detail_rows)}")

    return len(transaction_rows)


# ============================================================
# VALIDATION
# ============================================================

def validate_load(
    cur,
    transaction_date,
    expected_count
):
    """
    Validate the newly inserted transactions.
    """

    cur.execute("""
        SELECT COUNT(*)
        FROM trx.transaction
        WHERE transaction_date = %s
    """, (transaction_date,))

    transaction_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM trx.transaction t
        JOIN trx.transaction_detail td
          ON t.transaction_id = td.transaction_id
        WHERE t.transaction_date = %s
    """, (transaction_date,))

    detail_count = cur.fetchone()[0]

    print()
    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)

    print(f"Transaction date             : {transaction_date}")
    print(f"Transactions for date        : {transaction_count}")
    print(f"Transaction details for date : {detail_count}")

    if transaction_count >= expected_count:
        print("STATUS                       : SUCCESS")
    else:
        print("STATUS                       : WARNING")


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Optional date parameter
    #
    # Example:
    #
    # python daily_transactions.py 2026-09-12
    #
    # If no date is provided, today's date is used.
    # --------------------------------------------------------

    import sys

    if len(sys.argv) > 1:
        transaction_date = date.fromisoformat(
            sys.argv[1]
        )
    else:
        transaction_date = TODAY

    print()
    print("=" * 70)
    print("ISP DAILY TRANSACTION LOAD")
    print("=" * 70)

    print(f"Transaction date : {transaction_date}")
    print(f"Records required : {RECORDS_PER_DAY}")
    print(f"Database         : {DB['dbname']}")
    print(f"Host             : {DB['host']}")
    print(f"Port             : {DB['port']}")

    conn = psycopg2.connect(**DB)

    conn.autocommit = False

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Prevent duplicate daily load
            # ------------------------------------------------

            cur.execute("""
                SELECT COUNT(*)
                FROM trx.transaction
                WHERE transaction_date = %s
            """, (transaction_date,))

            existing_count = cur.fetchone()[0]

            if existing_count >= RECORDS_PER_DAY:

                print()
                print(
                    f"SKIPPED: {existing_count} transactions "
                    f"already exist for {transaction_date}."
                )

                conn.rollback()
                return

            # ------------------------------------------------
            # Generate transactions
            # ------------------------------------------------

            inserted = generate_daily_transactions(
                cur,
                transaction_date,
                RECORDS_PER_DAY
            )

            # ------------------------------------------------
            # Validate
            # ------------------------------------------------

            validate_load(
                cur,
                transaction_date,
                inserted
            )

        # ----------------------------------------------------
        # Commit
        # ----------------------------------------------------

        conn.commit()

        print()
        print("=" * 70)
        print("LOAD COMPLETED SUCCESSFULLY")
        print("=" * 70)

        print(
            f"{inserted} transactions loaded for "
            f"{transaction_date}"
        )

    except Exception as exc:

        conn.rollback()

        print()
        print("=" * 70)
        print("LOAD FAILED")
        print("=" * 70)

        print(str(exc))

        raise

    finally:

        conn.close()


if __name__ == "__main__":
    main()
