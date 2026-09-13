import os
import csv
import random
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

SEED = int(os.getenv("SEED", "20260909"))
RECORDS_PER_DAY = int(
    os.getenv("TRANSACTIONS_PER_DAY", "50")
)

OUTPUT_DIR = Path(
    os.getenv("TRANSACTION_OUTPUT_DIR", "output")
)

random.seed(SEED)

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

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
    Round value to 2 decimal places.
    """

    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def get_max_id(cur, table_name, column_name):
    """
    Get maximum ID from an existing PostgreSQL table.
    """

    sql = f"""
        SELECT COALESCE(MAX({column_name}), 0)
        FROM {table_name}
    """

    cur.execute(sql)

    return cur.fetchone()[0]


# ============================================================
# CHECK CURRENT DATE
# ============================================================

def check_today_transactions(cur, transaction_date):
    """
    Check whether transactions already exist
    for the requested date.
    """

    cur.execute(
        """
        SELECT COUNT(*)
        FROM trx.transaction
        WHERE transaction_date = %s
        """,
        (transaction_date,)
    )

    return cur.fetchone()[0]


# ============================================================
# GET ACTIVE SERVICES
# ============================================================

def get_active_services(cur):
    """
    Get existing active services from PostgreSQL.

    These records are used only as source/reference data.
    No data is inserted back into PostgreSQL.
    """

    cur.execute(
        """
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
        """
    )

    return cur.fetchall()


# ============================================================
# TRANSACTION TYPE
# ============================================================

def generate_transaction_type():

    return random.choices(
        [
            "RENEWAL",
            "UPGRADE",
            "DOWNGRADE",
            "ACTIVATION",
            "RECONNECTION"
        ],
        weights=[
            65,
            12,
            5,
            13,
            5
        ],
        k=1
    )[0]


# ============================================================
# PRODUCT CHANGE
# ============================================================

def calculate_product_change(
    transaction_type,
    current_product_id
):

    old_product_id = None
    new_product_id = current_product_id

    # --------------------------------------------------------
    # UPGRADE
    # --------------------------------------------------------

    if transaction_type == "UPGRADE":

        old_product_id = current_product_id

        if current_product_id < 5:
            new_product_id = current_product_id + 1
        else:
            new_product_id = current_product_id

    # --------------------------------------------------------
    # DOWNGRADE
    # --------------------------------------------------------

    elif transaction_type == "DOWNGRADE":

        old_product_id = current_product_id

        if current_product_id > 1:
            new_product_id = current_product_id - 1
        else:
            new_product_id = current_product_id

    # --------------------------------------------------------
    # OTHER TRANSACTIONS
    # --------------------------------------------------------

    else:

        old_product_id = None
        new_product_id = current_product_id

    return old_product_id, new_product_id


# ============================================================
# GENERATE TRANSACTIONS
# ============================================================

def generate_transactions(
    services,
    starting_transaction_id,
    starting_detail_id,
    transaction_date
):

    transactions = []
    transaction_details = []

    transaction_id = starting_transaction_id
    detail_id = starting_detail_id

    channels = [
        "WEB",
        "APP",
        "CALL_CENTER",
        "STORE",
        "PARTNER",
        "API"
    ]

    # --------------------------------------------------------
    # Select 50 different active services
    # --------------------------------------------------------

    number_of_records = min(
        RECORDS_PER_DAY,
        len(services)
    )

    selected_services = random.sample(
        services,
        number_of_records
    )

    # --------------------------------------------------------
    # Generate each transaction
    # --------------------------------------------------------

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
        # Make activation date logical
        # ----------------------------------------------------

        if (
            transaction_type == "ACTIVATION"
            and activation_date
            and activation_date > transaction_date
        ):
            transaction_type = "RENEWAL"

        # ----------------------------------------------------
        # Product change
        # ----------------------------------------------------

        old_product_id, new_product_id = (
            calculate_product_change(
                transaction_type,
                product_id
            )
        )

        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        if monthly_price is None:
            monthly_price = Decimal("499.00")
        else:
            monthly_price = Decimal(
                str(monthly_price)
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

            # Product pricing
            product_prices = {
                1: Decimal("499"),
                2: Decimal("699"),
                3: Decimal("899"),
                4: Decimal("1299"),
                5: Decimal("1999")
            }

            amount = money(
                product_prices.get(
                    new_product_id,
                    monthly_price
                )
            )

        else:

            amount = money(monthly_price)

        # ----------------------------------------------------
        # Transaction number
        # ----------------------------------------------------

        transaction_number = (
            f"TXN-{transaction_id:010d}"
        )

        # ----------------------------------------------------
        # Transaction timestamp
        # ----------------------------------------------------

        transaction_datetime = datetime.combine(
            transaction_date,
            datetime.min.time()
        ).replace(
            tzinfo=timezone.utc
        )

        # Add random time during the day
        random_seconds = random.randint(
            0,
            23 * 3600 + 59 * 60 + 59
        )

        transaction_datetime += timedelta(
            seconds=random_seconds
        )

        # ----------------------------------------------------
        # Transaction row
        # ----------------------------------------------------

        transactions.append([
            transaction_id,
            transaction_number,
            customer_id,
            service_id,
            transaction_type,
            transaction_datetime.isoformat(),
            "COMPLETED",
            amount,
            "INR",
            random.choice(channels),
            NOW.isoformat()
        ])

        # ----------------------------------------------------
        # Discount
        # ----------------------------------------------------

        discount_percent = random.choice(
            [
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0.05"),
                Decimal("0.10")
            ]
        )

        discount_amount = money(
            amount * discount_percent
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

        transaction_details.append([
            detail_id,
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
        ])

        transaction_id += 1
        detail_id += 1

    return transactions, transaction_details


# ============================================================
# WRITE TRANSACTIONS CSV
# ============================================================

def write_transactions_csv(
    transactions,
    transaction_date
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        f"transactions_"
        f"{transaction_date.strftime('%Y%m%d')}.csv"
    )

    filepath = OUTPUT_DIR / filename

    headers = [
        "transaction_id",
        "transaction_number",
        "customer_id",
        "service_id",
        "transaction_type",
        "transaction_date",
        "transaction_status",
        "amount",
        "currency",
        "channel",
        "created_at"
    ]

    with open(
        filepath,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(headers)

        writer.writerows(transactions)

    return filepath


# ============================================================
# WRITE TRANSACTION DETAILS CSV
# ============================================================

def write_transaction_details_csv(
    transaction_details,
    transaction_date
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        f"transaction_details_"
        f"{transaction_date.strftime('%Y%m%d')}.csv"
    )

    filepath = OUTPUT_DIR / filename

    headers = [
        "transaction_detail_id",
        "transaction_id",
        "line_number",
        "product_id",
        "old_product_id",
        "new_product_id",
        "quantity",
        "unit_price",
        "discount_amount",
        "tax_amount",
        "amount"
    ]

    with open(
        filepath,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(headers)

        writer.writerows(transaction_details)

    return filepath


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("DAILY ISP TRANSACTION CSV GENERATOR")
    print("=" * 70)

    print(f"Date              : {TODAY}")
    print(f"Records per day   : {RECORDS_PER_DAY}")
    print(f"Output directory  : {OUTPUT_DIR}")
    print(f"Database           : {DB['dbname']}")
    print()

    # --------------------------------------------------------
    # Connect to PostgreSQL
    # --------------------------------------------------------

    conn = psycopg2.connect(**DB)

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # STEP 1
            # Check whether today's data already exists
            # ------------------------------------------------

            existing_count = check_today_transactions(
                cur,
                TODAY
            )

            print(
                f"Existing transactions for {TODAY}: "
                f"{existing_count}"
            )

            # ------------------------------------------------
            # STOP if today's data exists
            # ------------------------------------------------

            if existing_count > 0:

                print()
                print(
                    f"Data already exists for {TODAY}."
                )

                print(
                    "No CSV files generated."
                )

                return

            # ------------------------------------------------
            # STEP 2
            # Get current MAX IDs
            # ------------------------------------------------

            max_transaction_id = get_max_id(
                cur,
                "trx.transaction",
                "transaction_id"
            )

            max_detail_id = get_max_id(
                cur,
                "trx.transaction_detail",
                "transaction_detail_id"
            )

            print(
                f"Current MAX transaction_id       : "
                f"{max_transaction_id}"
            )

            print(
                f"Current MAX transaction_detail_id: "
                f"{max_detail_id}"
            )

            # ------------------------------------------------
            # STEP 3
            # Get active services
            # ------------------------------------------------

            services = get_active_services(cur)

            if not services:

                raise RuntimeError(
                    "No ACTIVE services found in crm.service."
                )

            print(
                f"Active services available: "
                f"{len(services)}"
            )

            # ------------------------------------------------
            # STEP 4
            # Generate records
            # ------------------------------------------------

            transactions, transaction_details = (
                generate_transactions(
                    services,
                    max_transaction_id + 1,
                    max_detail_id + 1,
                    TODAY
                )
            )

            # ------------------------------------------------
            # STEP 5
            # Write transactions CSV
            # ------------------------------------------------

            transaction_file = (
                write_transactions_csv(
                    transactions,
                    TODAY
                )
            )

            # ------------------------------------------------
            # STEP 6
            # Write transaction details CSV
            # ------------------------------------------------

            detail_file = (
                write_transaction_details_csv(
                    transaction_details,
                    TODAY
                )
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            print()
            print("=" * 70)
            print("CSV GENERATION SUCCESSFUL")
            print("=" * 70)

            print(
                f"Transactions generated       : "
                f"{len(transactions)}"
            )

            print(
                f"Transaction details generated: "
                f"{len(transaction_details)}"
            )

            print()
            print(f"Transactions CSV:")
            print(f"  {transaction_file}")

            print()
            print(f"Transaction Details CSV:")
            print(f"  {detail_file}")

            print()
            print("No data was inserted into PostgreSQL.")

    finally:

        conn.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
