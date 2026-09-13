-- Row counts
SELECT 'crm.customer' table_name, COUNT(*) row_count FROM crm.customer
UNION ALL SELECT 'crm.billing', COUNT(*) FROM crm.billing
UNION ALL SELECT 'crm.contract', COUNT(*) FROM crm.contract
UNION ALL SELECT 'crm.contract_detail', COUNT(*) FROM crm.contract_detail
UNION ALL SELECT 'crm.contract_rate_schedule', COUNT(*) FROM crm.contract_rate_schedule
UNION ALL SELECT 'crm.service', COUNT(*) FROM crm.service
UNION ALL SELECT 'prd.product', COUNT(*) FROM prd.product
UNION ALL SELECT 'prd.rate_schedule', COUNT(*) FROM prd.rate_schedule
UNION ALL SELECT 'inv.invoice', COUNT(*) FROM inv.invoice
UNION ALL SELECT 'inv.invoice_detail', COUNT(*) FROM inv.invoice_detail
UNION ALL SELECT 'fin.payment', COUNT(*) FROM fin.payment
UNION ALL SELECT 'fin.payment_detail', COUNT(*) FROM fin.payment_detail
UNION ALL SELECT 'fin.gl_ledger', COUNT(*) FROM fin.gl_ledger
UNION ALL SELECT 'trx.transaction', COUNT(*) FROM trx.transaction
UNION ALL SELECT 'trx.transaction_detail', COUNT(*) FROM trx.transaction_detail
UNION ALL SELECT 'network.network_site', COUNT(*) FROM network.network_site
UNION ALL SELECT 'network.pop', COUNT(*) FROM network.pop
UNION ALL SELECT 'network.olt', COUNT(*) FROM network.olt
UNION ALL SELECT 'network.pon_port', COUNT(*) FROM network.pon_port
UNION ALL SELECT 'network.network_resource', COUNT(*) FROM network.network_resource
UNION ALL SELECT 'network.bandwidth_allocation', COUNT(*) FROM network.bandwidth_allocation
UNION ALL SELECT 'network.ip_pool', COUNT(*) FROM network.ip_pool
UNION ALL SELECT 'network.ip_assignment', COUNT(*) FROM network.ip_assignment;

-- Revenue reconciliation
SELECT
    COUNT(*) AS invoices,
    ROUND(SUM(total_amount),2) AS invoiced_amount
FROM inv.invoice
WHERE invoice_status <> 'VOID';

SELECT
    ROUND(SUM(p.amount),2) AS successful_payments
FROM fin.payment p
WHERE p.payment_status = 'SUCCESS';

-- Outstanding balance
SELECT
    ROUND(SUM(i.total_amount) - COALESCE(SUM(pd.allocated_amount),0),2) AS estimated_outstanding
FROM inv.invoice i
LEFT JOIN fin.payment_detail pd ON pd.invoice_id = i.invoice_id
WHERE i.invoice_status <> 'VOID';

-- Service/product distribution
SELECT p.product_name, COUNT(*) subscribers
FROM crm.service s
JOIN prd.product p ON p.product_id = s.product_id
WHERE s.service_status = 'ACTIVE'
GROUP BY p.product_name
ORDER BY subscribers DESC;

-- Network utilization
SELECT
    SUM(capacity_gbps) AS pop_capacity_gbps,
    SUM(used_capacity_gbps) AS pop_used_gbps,
    ROUND(100 * SUM(used_capacity_gbps) / NULLIF(SUM(capacity_gbps),0),2) AS utilization_pct
FROM network.pop;
