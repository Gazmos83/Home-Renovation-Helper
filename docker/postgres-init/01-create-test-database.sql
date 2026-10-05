-- Runs once, on first initialisation of the data volume.
-- POSTGRES_DB already created the dev database; this adds the test one so both
-- live in a single container (CLAUDE.md §2).
CREATE DATABASE home_renovation_test;
