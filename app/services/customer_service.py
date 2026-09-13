from datetime import datetime

from db import get_connection


def customer_exists(email, phone):
    """
    Check whether a customer already exists using email or phone.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT customer_id,
                       customer_number,
                       email,
                       phone
                FROM crm.customer
                WHERE LOWER(email) = LOWER(%s)
                   OR phone = %s
                LIMIT 1
                """,
                (email, phone),
            )

            return cur.fetchone()

    finally:
        conn.close()


def get_next_customer_id(cur):
    """
    Generate the next customer ID.

    PostgreSQL advisory lock prevents two concurrent Streamlit
    sessions from generating the same ID.
    """

    cur.execute(
        "SELECT pg_advisory_xact_lock(1001)"
    )

    cur.execute(
        """
        SELECT COALESCE(MAX(customer_id), 0) + 1
        FROM crm.customer
        """
    )

    return cur.fetchone()[0]


def create_customer(
    cur,
    first_name,
    last_name,
    email,
    phone,
    address_line1,
    city,
    state,
    postal_code,
    customer_type="RESIDENTIAL",
    country="India",
):
    customer_id = get_next_customer_id(cur)

    customer_number = f"CUST-{customer_id:08d}"

    now = datetime.now()

    cur.execute(
        """
        INSERT INTO crm.customer (
            customer_id,
            customer_number,
            customer_type,
            first_name,
            last_name,
            email,
            phone,
            address_line1,
            city,
            state,
            postal_code,
            country,
            customer_status,
            customer_since,
            created_at,
            updated_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            CURRENT_DATE,
            %s,
            %s
        )
        """,
        (
            customer_id,
            customer_number,
            customer_type,
            first_name,
            last_name,
            email,
            phone,
            address_line1,
            city,
            state,
            postal_code,
            country,
            "ACTIVE",
            now,
            now,
        ),
    )

    return customer_id, customer_number