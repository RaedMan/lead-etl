drop table if exists output.kid_addresses;

create table output.kid_addresses as (
with wic_addresses as (
    select kid_id, address_id, 
        min(date) as min_date, max(date) as max_date,
        bool_or(mothr_id_i is null) as infant,
        bool_or(mothr_id_i is not null) as mother,
        array_remove(array_agg(distinct CASE WHEN mothr_id_i is null THEN ogc_fid END), null) infant_ogc_fids,
        array_remove(array_agg(distinct CASE WHEN mothr_id_i is not null THEN ogc_fid END), null) mother_ogc_fids
    from aux.kid_wic_addresses 
    where 1=1
    group by 1,2
),

test_addresses as (
    select kid_id, address_id, 
        min(date) as min_date, max(date) as max_date,
        max(bll) as max_bll,
        avg(bll) as mean_bll
    from output.tests 
    where address_id is not null and 
    (1=1)
    group by 1,2
),

hcv_addresses as (
    select kid_id, address_id
    from input.hcv
    join aux.kid_hcvs on member_number = hcv_id
    join aux.addresses using (address)
    where (1=1)
    group by 1,2
),

stellar_addresses as (
    select kid_id, address_id
    from aux.kid_stellars
    join stellar.ca_link on stellar_id = child_id
    join stellar.addr using (addr_id)
    join aux.addresses using on address = upper(assemaddr)
    join output.addresses using (address)
    where (1=1)
    group by 1,2
)

select kid_id, address_id, 
    w.min_date as address_wic_min_date, 
    w.max_date as address_wic_max_date,
    w.mother as address_wic_mother,
    w.infant as address_wic_infant,
    w.mother_ogc_fids as wic_mother_ogc_fids,
    w.infant_ogc_fids as wic_infant_ogc_fids,

    t.min_date as address_test_min_date, 
    t.max_date as address_test_max_date,
    t.max_bll as address_max_bll,
    t.mean_bll as address_mean_bll,

    least(w.min_date, t.min_date) as address_min_date,
    greatest(w.min_date, t.min_date) as address_max_date

from wic_addresses w 
FULL OUTER JOIN test_addresses t using (kid_id, address_id)
FULL OUTER JOIN hcv_addresses using (kid_id, address_id)
FULL OUTER JOIN stellar_addresses using (kid_id, address_id)
);

alter table output.kid_addresses add primary key (kid_id, address_id);
