import os
import random
import ipaddress
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

SEED = int(os.getenv("SEED", "20260909"))
CUSTOMERS = int(os.getenv("CUSTOMERS", "10000"))
HISTORICAL_MONTHS = int(os.getenv("HISTORICAL_MONTHS", "12"))

random.seed(SEED)
fake = Faker("en_IN")
fake.seed_instance(SEED)

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()
BATCH_SIZE = 2000

DB = {
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD")
}
def money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def dt(days_back=0):
    return NOW - timedelta(days=days_back)

def rand_date(start, end):
    days = (end - start).days
    return start + timedelta(days=random.randint(0, max(days, 0)))

def month_start(d):
    return d.replace(day=1)

def add_months(d, months):
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)

def weighted_product():
    # More realistic adoption distribution.
    return random.choices(
        [1,2,3,4,5],
        weights=[28,30,24,14,4],
        k=1
    )[0]

STATES = [
    ("Telangana", ["Hyderabad","Warangal","Nizamabad","Karimnagar"]),
    ("Karnataka", ["Bengaluru","Mysuru","Mangaluru","Hubballi"]),
    ("Maharashtra", ["Mumbai","Pune","Nagpur","Nashik"]),
    ("Tamil Nadu", ["Chennai","Coimbatore","Madurai","Salem"]),
    ("Delhi", ["New Delhi"]),
    ("Gujarat", ["Ahmedabad","Surat","Vadodara","Rajkot"]),
    ("West Bengal", ["Kolkata","Siliguri"]),
    ("Kerala", ["Kochi","Thiruvananthapuram","Kozhikode"]),
    ("Rajasthan", ["Jaipur","Udaipur","Jodhpur"]),
    ("Uttar Pradesh", ["Noida","Lucknow","Kanpur","Ghaziabad"]),
]

def location():
    state, cities = random.choice(STATES)
    return state, random.choice(cities)

def insert_many(cur, sql, rows):
    if rows:
        execute_values(cur, sql, rows, page_size=BATCH_SIZE)

def clear_all(cur):
    cur.execute("""
        TRUNCATE
        network.ip_assignment, network.ip_pool, network.bandwidth_allocation,
        network.network_resource, network.pon_port, network.olt, network.pop,
        network.network_site,
        fin.gl_ledger, fin.payment_detail, fin.payment,
        inv.invoice_detail, inv.invoice,
        trx.transaction_detail, trx.transaction,
        crm.service, crm.contract_rate_schedule, crm.contract_detail, crm.contract,
        crm.billing, crm.customer,
        prd.rate_schedule, prd.product
        CASCADE
    """)

def seed_products(cur):
    products = [
        (1,"FBR100","Fiber 100 Mbps","BROADBAND","FTTH",100,50,999,"ACTIVE"),
        (2,"FBR300","Fiber 300 Mbps","BROADBAND","FTTH",300,100,999,"ACTIVE"),
        (3,"FBR500","Fiber 500 Mbps","BROADBAND","FTTH",500,250,999,"ACTIVE"),
        (4,"FBR1G","Fiber 1 Gbps","BROADBAND","FTTH",1000,500,1499,"ACTIVE"),
        (5,"FBR2G","Fiber 2 Gbps","BROADBAND","FTTH",2000,1000,1999,"ACTIVE"),
    ]
    now = NOW
    insert_many(cur, """
        INSERT INTO prd.product
        (product_id,product_code,product_name,product_category,technology,
         download_speed_mbps,upload_speed_mbps,installation_fee,product_status,created_at,updated_at)
        VALUES %s
    """, [p + (now,now) for p in products])

    prices = {1:499,2:699,3:899,4:1299,5:1999}
    rows = []
    rid = 1
    for pid in range(1,6):
        rows.append((rid,pid,f"RS-{pid}-2026",prices[pid],0,18,"INR",date(2026,1,1),None,"ACTIVE"))
        rid += 1
    insert_many(cur, """
        INSERT INTO prd.rate_schedule
        (rate_schedule_id,product_id,rate_code,monthly_charge,activation_charge,
         tax_percentage,currency,effective_from,effective_to,status)
        VALUES %s
    """, rows)
    return prices

def seed_customers(cur):
    rows=[]
    start = TODAY - timedelta(days=6*365)
    for i in range(1, CUSTOMERS+1):
        state, city = location()
        since = rand_date(start, TODAY - timedelta(days=15))
        ctype = random.choices(["RESIDENTIAL","SMB","ENTERPRISE"], [84,13,3])[0]
        status = random.choices(["ACTIVE","INACTIVE","SUSPENDED"], [93,5,2])[0]
        rows.append((
            i, f"CUST-{i:08d}", ctype, fake.first_name(), fake.last_name(),
            fake.email(), f"+91{random.randint(6000000000,9999999999)}",
            fake.building_number()+" "+fake.street_name(),
            city, state, fake.postcode(), "India", status, since, dt(random.randint(1,1800)), NOW
        ))
    insert_many(cur, """
        INSERT INTO crm.customer
        (customer_id,customer_number,customer_type,first_name,last_name,email,phone,
         address_line1,city,state,postal_code,country,customer_status,customer_since,created_at,updated_at)
        VALUES %s
    """, rows)

def seed_billing(cur):
    methods = ["UPI","CARD","NET_BANKING","AUTO_DEBIT","BANK_TRANSFER","CASH"]
    rows=[]
    for i in range(1, CUSTOMERS+1):
        rows.append((
            i, i, "MONTHLY", random.randint(1,28), random.choices(methods,[42,18,8,20,10,2])[0],
            random.choice([0,5000,10000,25000,50000]), "INR",
            random.choices(["ACTIVE","SUSPENDED","CLOSED"],[96,3,1])[0], dt(1200), NOW
        ))
    insert_many(cur, """
        INSERT INTO crm.billing
        (billing_account_id,customer_id,billing_cycle,billing_day,payment_method,
         credit_limit,currency,billing_status,created_at,updated_at)
        VALUES %s
    """, rows)

def seed_contracts_services(cur, prices):
    contracts=[]
    details=[]
    crs=[]
    services=[]
    contract_id=1
    detail_id=1
    crs_id=1
    service_id=1
    active_services=[]

    for customer_id in range(1, CUSTOMERS+1):
        customer = customer_id
        product_id = weighted_product()
        contract_type = random.choices(["MONTHLY","12_MONTH","24_MONTH"], [35,50,15])[0]
        start = TODAY - timedelta(days=random.randint(30, 900))
        if contract_type == "MONTHLY":
            end = None
        elif contract_type == "12_MONTH":
            end = start + timedelta(days=365)
        else:
            end = start + timedelta(days=730)

        if end and end < TODAY:
            status = random.choice(["EXPIRED","CANCELLED","ACTIVE"])
        else:
            status = random.choices(["ACTIVE","CANCELLED","PENDING"], [97,2,1])[0]

        contracts.append((
            contract_id,f"CON-{contract_id:09d}",customer,contract_type,start,end,status,
            random.random()<0.92, dt(random.randint(10,1500)), NOW
        ))

        base = Decimal(str(prices[product_id]))
        discount = money(base * Decimal(str(random.choice([0,0,0.05,0.10,0.15]))))
        agreed = money(base-discount)

        details.append((
            detail_id,contract_id,1,product_id,1,agreed,discount,18,start,end
        ))
        crs.append((crs_id,contract_id,detail_id,product_id,start,end,agreed))
        sid = service_id
        svc_status = "ACTIVE"
        deact = None
        if status == "CANCELLED":
            svc_status = "DISCONNECTED"
            deact = rand_date(start, min(TODAY, start+timedelta(days=300)))
        elif status == "EXPIRED":
            svc_status = random.choice(["ACTIVE","DISCONNECTED"])
            if svc_status=="DISCONNECTED":
                deact = min(TODAY, end)

        state, city = location()
        services.append((
            sid,customer_id,contract_id,product_id,f"SRV-{sid:010d}","BROADBAND",
            "FTTH",start,deact,svc_status,fake.building_number()+" "+fake.street_name(),
            city,state,fake.postcode(),dt(random.randint(1,1200)),NOW
        ))
        if svc_status == "ACTIVE":
            active_services.append((sid,customer_id,product_id,start,agreed))
        contract_id += 1
        detail_id += 1
        crs_id += 1
        service_id += 1

    insert_many(cur, """
        INSERT INTO crm.contract
        (contract_id,contract_number,customer_id,contract_type,start_date,end_date,contract_status,
         auto_renew,created_at,updated_at) VALUES %s
    """, contracts)
    insert_many(cur, """
        INSERT INTO crm.contract_detail
        (contract_detail_id,contract_id,line_number,product_id,quantity,agreed_monthly_price,
         discount_amount,tax_percent,effective_from,effective_to) VALUES %s
    """, details)
    insert_many(cur, """
        INSERT INTO crm.contract_rate_schedule
        (contract_rate_schedule_id,contract_id,contract_detail_id,rate_schedule_id,
         effective_from,effective_to,agreed_rate) VALUES %s
    """, crs)
    insert_many(cur, """
        INSERT INTO crm.service
        (service_id,customer_id,contract_id,product_id,service_number,service_type,technology,
         activation_date,deactivation_date,service_status,installation_address,city,state,postal_code,
         created_at,updated_at) VALUES %s
    """, services)
    return active_services

def seed_transactions(cur, active_services, prices):
    rows=[]
    details=[]
    tid=1
    tdid=1
    channels=["WEB","APP","CALL_CENTER","STORE","PARTNER","API"]
    for sid,cid,pid,start,agreed in active_services:
        event_types = ["ACTIVATION","RENEWAL"]
        if random.random() < 0.18:
            event_types.append("UPGRADE")
        if random.random() < 0.08:
            event_types.append("DOWNGRADE")
        if random.random() < 0.03:
            event_types.append("RECONNECTION")
        for et in random.sample(event_types, k=random.randint(1,min(2,len(event_types)))):
            tdate = max(start, TODAY - timedelta(days=random.randint(1,360)))
            amount = agreed if et in ("ACTIVATION","RENEWAL") else money(random.uniform(0.0, float(agreed)))
            rows.append((
                tid,f"TXN-{tid:010d}",cid,sid,et,tdate, "COMPLETED", amount,
                "INR", random.choice(channels), NOW
            ))
            old_pid = None
            new_pid = pid
            if et=="UPGRADE":
                old_pid = max(1,pid-1)
            elif et=="DOWNGRADE":
                new_pid = max(1,pid-1)
                old_pid = pid
            details.append((
                tdid,tid,1,pid,old_pid,new_pid,1,amount,0,
                money(amount*Decimal("0.18")), money(amount*Decimal("1.18"))
            ))
            tid += 1
            tdid += 1
    insert_many(cur, """
        INSERT INTO trx.transaction
        (transaction_id,transaction_number,customer_id,service_id,transaction_type,
         transaction_date,transaction_status,amount,currency,channel,created_at)
        VALUES %s
    """, rows)
    insert_many(cur, """
        INSERT INTO trx.transaction_detail
        (transaction_detail_id,transaction_id,line_number,product_id,old_product_id,new_product_id,
         quantity,unit_price,discount_amount,tax_amount,amount) VALUES %s
    """, details)

def seed_invoices_payments_gl(cur, active_services, prices):
    invoice_rows=[]
    invoice_details=[]
    payment_rows=[]
    payment_details=[]
    gl_rows=[]
    invoice_id=1
    inv_detail_id=1
    payment_id=1
    payment_detail_id=1
    gl_id=1

    for sid,cid,pid,start,agreed in active_services:
        first_month = max(month_start(start), add_months(month_start(TODAY), -HISTORICAL_MONTHS))
        m = first_month
        while m <= month_start(TODAY):
            period_start=m
            period_end=add_months(m,1)-timedelta(days=1)
            invoice_date=min(period_start+timedelta(days=2), TODAY)
            due_date=min(period_start+timedelta(days=17), TODAY+timedelta(days=30))
            discount=money(agreed*Decimal(str(random.choice([0,0,0.05,0.10]))))
            taxable=money(agreed-discount)
            tax=money(taxable*Decimal("0.18"))
            total=money(taxable+tax)
            age_days=(TODAY-due_date).days
            status="PAID" if age_days>0 and random.random()<0.86 else (
                "OVERDUE" if age_days>0 else "ISSUED"
            )
            invoice_rows.append((
                invoice_id,f"INV-{invoice_id:010d}",cid,cid,invoice_date,due_date,
                period_start,period_end,agreed,discount,tax,total,status,dt(random.randint(1,1000)),NOW
            ))
            invoice_details.append((
                inv_detail_id,invoice_id,1,sid,pid,"RECURRING",
                f"Broadband subscription - {pid}",1,agreed,discount,tax,total
            ))

            # Payments: realistic mixture of full, partial and unpaid.
            pay_probability = 0.95 if status=="PAID" else (0.35 if status=="OVERDUE" else 0.10)
            if random.random() < pay_probability:
                pay_amount = total
                if status=="OVERDUE" and random.random()<0.18:
                    pay_amount=money(total*Decimal(str(random.choice([0.25,0.5,0.75]))))
                method=random.choice(["UPI","CARD","NET_BANKING","AUTO_DEBIT","BANK_TRANSFER"])
                pdate=min(due_date+timedelta(days=random.randint(-3,25)), TODAY)
                payment_status="SUCCESS"
                payment_rows.append((
                    payment_id,f"PAY-{payment_id:010d}",cid,pdate,method,payment_status,
                    pay_amount,"INR",f"GW-{random.randint(10**11,10**12-1)}",dt(random.randint(1,900))
                ))
                payment_details.append((
                    payment_detail_id,payment_id,invoice_id,pay_amount,"ALLOCATED",NOW
                ))
                payment_id += 1
                payment_detail_id += 1

            gl_rows.extend([
                (gl_id,None,invoice_date,"400100","Internet Subscription Revenue",0,total,"INR",
                 f"INV-{invoice_id:010d}","Invoice revenue recognition",NOW),
                (gl_id+1,None,invoice_date,"120100","Accounts Receivable",total,0,"INR",
                 f"INV-{invoice_id:010d}","Customer receivable",NOW),
            ])
            gl_id += 2
            invoice_id += 1
            inv_detail_id += 1
            m=add_months(m,1)

    insert_many(cur, """
        INSERT INTO inv.invoice
        (invoice_id,invoice_number,billing_account_id,customer_id,invoice_date,due_date,
         billing_period_start,billing_period_end,subtotal,discount_amount,tax_amount,total_amount,
         invoice_status,created_at,updated_at) VALUES %s
    """, invoice_rows)
    insert_many(cur, """
        INSERT INTO inv.invoice_detail
        (invoice_detail_id,invoice_id,line_number,service_id,product_id,charge_type,description,
         quantity,unit_price,discount_amount,tax_amount,line_total) VALUES %s
    """, invoice_details)
    insert_many(cur, """
        INSERT INTO fin.payment
        (payment_id,payment_number,customer_id,payment_date,payment_method,payment_status,amount,
         currency,gateway_reference,created_at) VALUES %s
    """, payment_rows)
    insert_many(cur, """
        INSERT INTO fin.payment_detail
        (payment_detail_id,payment_id,invoice_id,allocated_amount,allocation_status,created_at)
        VALUES %s
    """, payment_details)
    insert_many(cur, """
        INSERT INTO fin.gl_ledger
        (gl_entry_id,transaction_id,entry_date,account_code,account_name,debit_amount,credit_amount,
         currency,reference_number,description,created_at) VALUES %s
    """, gl_rows)

def seed_network(cur, active_services):
    # City-level synthetic network topology.
    site_rows=[]
    pop_rows=[]
    olt_rows=[]
    pon_rows=[]
    site_id=1
    pop_id=1
    olt_id=1
    pon_id=1
    sites=[]
    for state,cities in STATES:
        for city in cities[:min(2,len(cities))]:
            lat = random.uniform(8.0, 28.5)
            lon = random.uniform(68.0, 88.5)
            site_rows.append((site_id,f"SITE-{site_id:04d}",f"{city} Network Hub",city,state,
                              str(random.randint(100000,799999)),round(lat,6),round(lon,6),
                              "ACTIVE",NOW))
            # 1-2 POPs per site
            for p in range(random.randint(1,2)):
                cap=random.choice([40,80,100,200])
                used=round(cap*random.uniform(0.35,0.88),2)
                pop_rows.append((pop_id,site_id,f"POP-{pop_id:05d}",f"{city} POP {p+1}",cap,used,
                                 random.choice(["N+1","N+2"]),"ACTIVE",NOW))
                for o in range(random.randint(2,4)):
                    total_ports=16
                    used_ports=random.randint(6,15)
                    olt_rows.append((olt_id,pop_id,f"OLT-{olt_id:06d}",
                                     random.choice(["Huawei","Nokia","ZTE"]),
                                     random.choice(["MA5800","7360 ISAM","C600"]),
                                     total_ports,used_ports,random.choice([20,40,80]),
                                     "ACTIVE",NOW))
                    for port in range(1,total_ports+1):
                        port_cap=random.choice([2.5,10])
                        used_cap=round(port_cap*random.uniform(0.2,0.82),2)
                        status="ACTIVE" if port<=used_ports else "AVAILABLE"
                        pon_rows.append((pon_id,olt_id,port,"GPON" if port_cap==2.5 else "XGS-PON",
                                         port_cap,used_cap,status))
                        pon_id+=1
                    olt_id+=1
                pop_id+=1
            site_id+=1

    insert_many(cur, """
        INSERT INTO network.network_site
        (site_id,site_code,site_name,city,state,postal_code,latitude,longitude,site_status,created_at)
        VALUES %s
    """, site_rows)
    insert_many(cur, """
        INSERT INTO network.pop
        (pop_id,site_id,pop_code,pop_name,capacity_gbps,used_capacity_gbps,redundancy_level,status,created_at)
        VALUES %s
    """, pop_rows)
    insert_many(cur, """
        INSERT INTO network.olt
        (olt_id,pop_id,olt_code,vendor,model,total_pon_ports,used_pon_ports,total_capacity_gbps,status,created_at)
        VALUES %s
    """, olt_rows)
    insert_many(cur, """
        INSERT INTO network.pon_port
        (pon_port_id,olt_id,port_number,technology,capacity_gbps,used_capacity_gbps,status)
        VALUES %s
    """, pon_rows)

    # Assign active services to available PON ports.
    resource_rows=[]
    bandwidth_rows=[]
    ip_pool_rows=[]
    ip_assignment_rows=[]
    service_map={}
    resource_id=1
    allocation_id=1
    ip_assignment_id=1

    # A few realistic IP pools.
    pools=[
        (1,"HYD-BRAS-IPv4-01","100.64.0.0/20","IPv4",4096,0,"Hyderabad","ACTIVE"),
        (2,"BLR-BRAS-IPv4-01","100.64.16.0/20","IPv4",4096,0,"Bengaluru","ACTIVE"),
        (3,"MUM-BRAS-IPv4-01","100.64.32.0/20","IPv4",4096,0,"Mumbai","ACTIVE"),
        (4,"NATIONAL-IPv6-01","2001:db8:100::/48","IPv6",65536,0,"National","ACTIVE"),
    ]
    insert_many(cur, """
        INSERT INTO network.ip_pool
        (ip_pool_id,pool_name,cidr,address_family,total_addresses,allocated_addresses,region,status)
        VALUES %s
    """, pools)

    pon_ids=[r[0] for r in pon_rows if r[6]=="AVAILABLE"]
    random.shuffle(pon_ids)
    ip_counter=0

    for idx,(sid,cid,pid,start,agreed) in enumerate(active_services):
        if not pon_ids:
            break
        pon_id=pon_ids.pop()
        speed={1:100,2:300,3:500,4:1000,5:2000}[pid]
        resource_rows.append((resource_id,sid,pon_id,"FTTH",speed,int(speed*0.8),"PROVISIONED",start))
        utilization=round(random.uniform(8,92),2)
        bandwidth_rows.append((allocation_id,sid,resource_id,int(speed*random.uniform(0.6,1.2)),
                               int(speed*0.8),utilization,TODAY))
        ip_pool_id=[1,2,3][idx%3]
        ip_addr=str(ipaddress.ip_address(int(ipaddress.ip_address("100.64.0.1"))+ip_counter))
        ip_counter += 1
        ip_assignment_rows.append((ip_assignment_id,ip_pool_id,sid,ip_addr,
                                    "STATIC" if random.random()<0.08 else "DYNAMIC",start,None))
        resource_id+=1
        allocation_id+=1
        ip_assignment_id+=1

    insert_many(cur, """
        INSERT INTO network.network_resource
        (resource_id,service_id,pon_port_id,resource_type,provisioned_speed_mbps,
         committed_speed_mbps,status,activated_at) VALUES %s
    """, resource_rows)
    insert_many(cur, """
        INSERT INTO network.bandwidth_allocation
        (allocation_id,service_id,resource_id,peak_bandwidth_mbps,committed_bandwidth_mbps,
         utilization_percent,measurement_date) VALUES %s
    """, bandwidth_rows)
    insert_many(cur, """
        INSERT INTO network.ip_assignment
        (ip_assignment_id,ip_pool_id,service_id,ip_address,assignment_type,assigned_at,released_at)
        VALUES %s
    """, ip_assignment_rows)

    # Update pool allocations.
    for pool_id in [1,2,3]:
        cur.execute("""
            UPDATE network.ip_pool p
            SET allocated_addresses = (
                SELECT COUNT(*) FROM network.ip_assignment a WHERE a.ip_pool_id=p.ip_pool_id
            )
            WHERE p.ip_pool_id=%s
        """,(pool_id,))

def main():
    print(f"Starting synthetic ISP load: customers={CUSTOMERS}, months={HISTORICAL_MONTHS}, seed={SEED}")
    conn=psycopg2.connect(**DB)
    conn.autocommit=False
    try:
        with conn.cursor() as cur:
            clear_all(cur)
            prices=seed_products(cur)
            seed_customers(cur)
            seed_billing(cur)
            active_services=seed_contracts_services(cur, prices)
            seed_transactions(cur, active_services, prices)
            seed_invoices_payments_gl(cur, active_services, prices)
            seed_network(cur, active_services)
        conn.commit()
        print(f"SUCCESS: loaded {CUSTOMERS} customers and {len(active_services)} active services.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__=="__main__":
    main()
