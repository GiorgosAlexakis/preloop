-- Migration script to change issueembedding.embedding column type to vector(1536)
-- Only runs if the pgvector extension is installed.

DO $$
BEGIN
    -- Check if the pgvector extension is installed
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        -- Check if the column type is not already vector
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' -- Adjust schema if needed
              AND table_name = 'issueembedding'
              AND column_name = 'embedding'
              AND udt_name != 'vector'
        ) THEN
            RAISE NOTICE 'Attempting to alter issueembedding.embedding column type to vector(1536)...';
            -- Alter the column type to vector(1536)
            -- The USING clause attempts to cast the existing JSONB data to text and then to vector.
            -- This assumes the JSONB stored a valid array representation like '[0.1, 0.2, ...]'.
            -- Adjust the USING clause if the previous JSON format was different.
            ALTER TABLE issueembedding
            ALTER COLUMN embedding TYPE vector(1536)
            USING embedding::text::vector;

            RAISE NOTICE 'Successfully altered issueembedding.embedding column type.';
        ELSE
            RAISE NOTICE 'issueembedding.embedding column type is already vector or table/column does not exist.';
        END IF;
    ELSE
        RAISE NOTICE 'pgvector extension not found. Skipping embedding column type migration.';
    END IF;
END $$;