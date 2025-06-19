CREATE TABLE transactions_v2 (
    msno Utf8,
    payment_method_id Int32,
    payment_plan_days Int32,
    plan_list_price Int32,
    actual_amount_paid Int32,
    is_auto_renew Int8,
    transaction_date Utf8,
    membership_expire_date Utf8,
    is_cancel Int8,
    PRIMARY KEY (msno)
);