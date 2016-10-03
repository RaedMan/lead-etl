drop table if exists output.tests;

create table output.tests as (
    select test_id, kid_id, 
        CASE WHEN a.address in 
            ('5001 S MICHIGAN AVE', '1634 W POLK ST', '810 W MONTROSE AVE') 
        THEN null ELSE a.address_id END AS address_id,
        apt, lab_id,
        bll, sample_date as date, 
        CASE WHEN lab_id = 'C16' THEN 'V' ELSE sample_type END AS sample_type, 
        sample_date - k.date_of_birth AS age,
        first, first_bll6, first_bll10, increase, test_number
    
    from aux.tests t
    join aux.kid_tests_info kt using (test_id)
    left join aux.test_addresses ta using (test_id)
    left join aux.addresses a using (address_id)
    left join aux.kids k using (kid_id)
);

create index on output.tests (kid_id, address_id);
