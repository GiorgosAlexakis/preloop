# Database Migration Guide

This document explains how to apply the timestamp field migration to existing PostgreSQL databases.

## Overview

The migration adds `created` and `last_updated` timestamp fields to the `account` and `tracker` tables, which are used to track when records are created and modified. The migration also sets up triggers to automatically update the `last_updated` field whenever a record is modified.

## Migration Files

1. `migration_add_timestamps.sql` - The SQL migration script
2. `run_migration.py` - A Python script to execute the migration

## Prerequisites

- PostgreSQL database with existing SpaceModels schema
- Python 3.6+ with SQLAlchemy installed
- Database connection credentials

## Running the Migration

### Option 1: Using the Python Script

The Python script provides error handling and logging for the migration process.

1. Set the database connection URL as an environment variable:

   ```bash
   export DATABASE_URL="postgresql://username:password@hostname:port/dbname"
   ```

2. Run the migration script:

   ```bash
   python run_migration.py
   ```

3. Check the output to verify the migration was successful.

### Option 2: Direct SQL Execution

If you prefer to run the SQL directly:

1. Connect to your PostgreSQL database:

   ```bash
   psql -U username -h hostname -d dbname
   ```

2. Execute the SQL file:

   ```sql
   \i migration_add_timestamps.sql
   ```

## Verification

After running the migration, you can verify that the columns were added correctly:

```sql
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('account', 'tracker') 
AND column_name IN ('created', 'last_updated')
ORDER BY table_name, column_name;
```

You should see four rows showing the new columns.

## Testing the Triggers

To test that the triggers are working correctly:

```sql
-- Update an account record
UPDATE account 
SET full_name = 'Updated Name' 
WHERE id = 'some-account-id';

-- Check that last_updated was updated
SELECT id, full_name, last_updated 
FROM account
WHERE id = 'some-account-id';
```

The `last_updated` timestamp should reflect the time of the update.

## Rollback

If you need to roll back the migration, execute the following SQL:

```sql
BEGIN;

-- Remove triggers
DROP TRIGGER IF EXISTS update_account_last_updated ON account;
DROP TRIGGER IF EXISTS update_tracker_last_updated ON tracker;

-- Remove trigger function
DROP FUNCTION IF EXISTS update_last_updated_column() CASCADE;

-- Remove columns from account table
ALTER TABLE account DROP COLUMN IF EXISTS created;
ALTER TABLE account DROP COLUMN IF EXISTS last_updated;

-- Remove columns from tracker table
ALTER TABLE tracker DROP COLUMN IF EXISTS created;
ALTER TABLE tracker DROP COLUMN IF EXISTS last_updated;

COMMIT;
```

## Important Notes

- This migration is idempotent and can be safely run multiple times.
- The migration preserves existing data by copying values from the existing timestamp fields.
- For new installations using the updated models, these fields will be created automatically during the initial schema setup.