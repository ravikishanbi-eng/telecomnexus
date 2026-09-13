from datetime import timedelta, date

from db import get_connection


def get_products():
    """
    Get active products and their current rate schedules.
    """

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    p.product_id,
                    p.product_code,
                    p.product_name,
                    p.product_category,
                    p.technology,
                    p.download_speed_mbps,
                    p.upload_speed_mbps,
                    rs.rate_schedule_id,
                    rs.monthly_charge,
                    rs.activation_charge,
                    rs.tax_percentage,
                    rs.currency
                FROM prd.product p
                JOIN prd.rate_schedule rs
                    ON rs.product_id = p.product_id
                WHERE p.product_status = 'ACTIVE'
                  AND rs.status = 'ACTIVE'
                  AND rs.effective_from <= CURRENT_DATE
                  AND (
                        rs.effective_to IS NULL
                        OR rs.effective_to >= CURRENT_DATE
                  )
                ORDER BY p.product_id
                """
            )

            return cur.fetchall()

    finally:
        conn.close()


def get_next_contract_id(cur):

    cur.execute(
        "SELECT pg_advisory_xact_lock(1002)"
    )

    cur.execute(
        """
        SELECT COALESCE(MAX(contract_id), 0) + 1
        FROM crm.contract
        """
    )

    return cur.fetchone()[0]


def get_next_contract_detail_id(cur):

    cur.execute(
        "SELECT pg_advisory_xact_lock(1003)"
    )

    cur.execute(
        """
        SELECT COALESCE(MAX(contract_detail_id), 0) + 1
        FROM crm.contract_detail
        """
    )

    return cur.fetchone()[0]


def get_next_contract_rate_schedule_id(cur):

    cur.execute(
        "SELECT pg_advisory_xact_lock(1004)"
    )

    cur.execute(
        """
        SELECT COALESCE(MAX(contract_rate_schedule_id), 0) + 1
        FROM crm.contract_rate_schedule
        """
    )

    return cur.fetchone()[0]


def calculate_end_date(contract_type, start_date):

    if contract_type == "MONTHLY":
        return None

    if contract_type == "12_MONTH":
        return start_date + timedelta(days=365)

    if contract_type == "24_MONTH":
        return start_date + timedelta(days=730)

    return None


def create_contract(
    cur,
    customer_id,
    contract_type,
    start_date,
    contract_status,
    auto_renew,
    product_id,
    rate_schedule_id,
    quantity,
    agreed_monthly_price,
    discount_amount,
    tax_percent,
):
    """
    Create:

        crm.contract
        crm.contract_detail
        crm.contract_rate_schedule

    in the same transaction.
    """

    contract_id = get_next_contract_id(cur)

    contract_number = f"CON-{contract_id:09d}"

    end_date = calculate_end_date(
        contract_type,
        start_date,
    )

    cur.execute(
        """
        INSERT INTO crm.contract (
            contract_id,
            contract_number,
            customer_id,
            contract_type,
            start_date,
            end_date,
            contract_status,
            auto_renew,
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
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        """,
        (
            contract_id,
            contract_number,
            customer_id,
            contract_type,
            start_date,
            end_date,
            contract_status,
            auto_renew,
        ),
    )

    contract_detail_id = get_next_contract_detail_id(cur)

    cur.execute(
        """
        INSERT INTO crm.contract_detail (
            contract_detail_id,
            contract_id,
            line_number,
            product_id,
            quantity,
            agreed_monthly_price,
            discount_amount,
            tax_percent,
            effective_from,
            effective_to
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
            %s
        )
        """,
        (
            contract_detail_id,
            contract_id,
            1,
            product_id,
            quantity,
            agreed_monthly_price,
            discount_amount,
            tax_percent,
            start_date,
            end_date,
        ),
    )

    contract_rate_schedule_id = (
        get_next_contract_rate_schedule_id(cur)
    )

    cur.execute(
        """
        INSERT INTO crm.contract_rate_schedule (
            contract_rate_schedule_id,
            contract_id,
            contract_detail_id,
            rate_schedule_id,
            effective_from,
            effective_to,
            agreed_rate
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            contract_rate_schedule_id,
            contract_id,
            contract_detail_id,
            rate_schedule_id,
            start_date,
            end_date,
            agreed_monthly_price,
        ),
    )

    return {
        "contract_id": contract_id,
        "contract_number": contract_number,
        "contract_detail_id": contract_detail_id,
        "contract_rate_schedule_id": contract_rate_schedule_id,
        "end_date": end_date,
    }