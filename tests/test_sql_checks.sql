-- Basic production-style integrity checks. Each query should return zero rows
-- except the last two KPI queries.

SELECT s.service_id
FROM crm.service s
LEFT JOIN crm.customer c ON c.customer_id=s.customer_id
WHERE c.customer_id IS NULL;

SELECT d.invoice_detail_id
FROM inv.invoice_detail d
LEFT JOIN inv.invoice i ON i.invoice_id=d.invoice_id
WHERE i.invoice_id IS NULL;

SELECT pd.payment_detail_id
FROM fin.payment_detail pd
LEFT JOIN inv.invoice i ON i.invoice_id=pd.invoice_id
WHERE i.invoice_id IS NULL;

SELECT nr.resource_id
FROM network.network_resource nr
LEFT JOIN crm.service s ON s.service_id=nr.service_id
WHERE s.service_id IS NULL;

-- ARPU
SELECT
    ROUND(SUM(i.total_amount) / NULLIF(COUNT(DISTINCT i.customer_id),0),2) AS avg_invoice_per_customer
FROM inv.invoice i
WHERE i.invoice_date >= CURRENT_DATE - INTERVAL '30 days'
  AND i.invoice_status <> 'VOID';

-- Network capacity
SELECT
    ROUND(100 * SUM(used_capacity_gbps) / NULLIF(SUM(capacity_gbps),0),2) AS pop_utilization_pct
FROM network.pop;
