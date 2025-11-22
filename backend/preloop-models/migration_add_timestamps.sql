-- Migration script to add created and last_updated columns to Account and Tracker tables
-- Compatible with PostgreSQL

BEGIN;

-- Add columns to Account table if they don't exist
DO $$
BEGIN
    -- Check if 'created' column exists in account table
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'account' AND column_name = 'created'
    ) THEN
        -- Add 'created' column, default to current timestamp
        ALTER TABLE account ADD COLUMN created TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL;
        
        -- Set 'created' value for existing records to current timestamp 
        -- (or you could use created_at if you want to preserve that information)
        UPDATE account SET created = created_at;
    END IF;

    -- Check if 'last_updated' column exists in account table
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'account' AND column_name = 'last_updated'
    ) THEN
        -- Add 'last_updated' column, default to current timestamp
        ALTER TABLE account ADD COLUMN last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL;
        
        -- Set 'last_updated' value for existing records to updated_at
        UPDATE account SET last_updated = updated_at;
    END IF;
END $$;

-- Add columns to Tracker table if they don't exist
DO $$
BEGIN
    -- Check if 'created' column exists in tracker table
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'tracker' AND column_name = 'created'
    ) THEN
        -- Add 'created' column, default to current timestamp
        ALTER TABLE tracker ADD COLUMN created TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL;
        
        -- Set 'created' value for existing records to created_at
        UPDATE tracker SET created = created_at;
    END IF;

    -- Check if 'last_updated' column exists in tracker table
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'tracker' AND column_name = 'last_updated'
    ) THEN
        -- Add 'last_updated' column, default to current timestamp
        ALTER TABLE tracker ADD COLUMN last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL;
        
        -- Set 'last_updated' value for existing records to updated_at
        UPDATE tracker SET last_updated = updated_at;
    END IF;
END $$;

-- Create trigger functions to automatically update last_updated on change

-- First, check if the function already exists and drop it if so
DROP FUNCTION IF EXISTS update_last_updated_column() CASCADE;

-- Create the trigger function
CREATE FUNCTION update_last_updated_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create or replace triggers for each table

-- Drop triggers if they exist
DROP TRIGGER IF EXISTS update_account_last_updated ON account;
DROP TRIGGER IF EXISTS update_tracker_last_updated ON tracker;

-- Create triggers for account table
CREATE TRIGGER update_account_last_updated
BEFORE UPDATE ON account
FOR EACH ROW
EXECUTE FUNCTION update_last_updated_column();

-- Create triggers for tracker table  
CREATE TRIGGER update_tracker_last_updated
BEFORE UPDATE ON tracker
FOR EACH ROW
EXECUTE FUNCTION update_last_updated_column();

-- Verify the changes
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('account', 'tracker') 
AND column_name IN ('created', 'last_updated')
ORDER BY table_name, column_name;

COMMIT;