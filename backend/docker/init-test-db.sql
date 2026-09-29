-- Runs once when the compose database volume is first created.
-- The test suite wipes and re-migrates this database on every run.
CREATE DATABASE envex_test OWNER envex;
