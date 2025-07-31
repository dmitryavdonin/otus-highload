-- Create replication user
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replpass';

-- Update configuration
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET max_replication_slots = 10;

-- Reload configuration
SELECT pg_reload_conf(); 