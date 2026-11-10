-- PostgreSQL. CSVs are regenerated locally; no customer data is committed.
CREATE TABLE customers (
    customer_id text PRIMARY KEY,
    checkout_id text UNIQUE NOT NULL,
    variant text NOT NULL CHECK (variant IN ('control','treatment')),
    customer_segment text NOT NULL,
    merchant_segment text NOT NULL,
    prior_conversion double precision NOT NULL CHECK (prior_conversion BETWEEN 0 AND 1),
    assigned_at timestamp with time zone NOT NULL
);
CREATE TABLE events (
    event_id text PRIMARY KEY,
    checkout_id text NOT NULL REFERENCES customers(checkout_id),
    event_type text NOT NULL,
    event_at timestamp with time zone NOT NULL,
    attempt integer NOT NULL CHECK (attempt >= 0)
);
CREATE INDEX events_checkout_time ON events(checkout_id, event_at);
