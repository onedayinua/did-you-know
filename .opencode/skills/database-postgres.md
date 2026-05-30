# Skill: Postgres Database Management
- **Schema Awareness**: Run `\d+ [table_name]` before writing any JOIN queries.
- **Migration Safety**: Never manually edit the DB; always generate a migration script (Alembic/Django/etc).
- **Performance**: Use `EXPLAIN ANALYZE` for any query involving more than two joins or 10k+ rows.