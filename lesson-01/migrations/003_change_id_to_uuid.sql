-- Change id column type from character varying to UUID
ALTER TABLE users ALTER COLUMN id TYPE UUID USING id::UUID; 