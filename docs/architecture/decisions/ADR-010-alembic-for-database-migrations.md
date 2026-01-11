# ADR-010: Use of Alembic for Database Migrations

- **Status**: Accepted
- **Date**: 2025-11-04

## Context

With the introduction of a persistent database (PostgreSQL) managed by SQLAlchemy, we need a systematic and controlled way to manage changes to the database schema over time. As the application evolves, we will need to add new tables, modify columns, or create indexes.

Managing these changes manually (by running SQL scripts by hand) is error-prone, difficult to version, and not reproducible across different environments (development, testing, production).

## Decision

We have decided to adopt **Alembic** as the tool for managing database migrations.

Alembic will integrate with SQLAlchemy to:
1.  **Autogenerate migration scripts**: It will compare the SQLAlchemy models defined in our code with the current state of the database to automatically generate the necessary changes.
2.  **Version the schema**: Each change to the schema will be saved in a versioned migration file, creating an auditable history of the database evolution.
3.  **Apply and revert migrations**: It will provide commands (`upgrade`, `downgrade`) to apply changes safely and predictably in any environment.

## Justification

1.  **Version Control for the Database**: Treats the database schema as code, allowing us to store it in Git alongside the rest of the application. This ensures that a specific version of the code always corresponds to a specific version of the database schema.

2.  **Automation and Reliability**: The `autogenerate` process drastically reduces the risk of human errors when writing SQL for DDL (Data Definition Language). The `upgrade` and `downgrade` commands make applying changes a repeatable and reliable process.

3.  **Ease of Deployment**: Greatly simplifies the deployment process. When deploying a new version of the application, simply run `alembic upgrade head` to bring the production database to the state required by the new code.

4.  **Integration with SQLAlchemy**: Alembic is the de facto standard for migrations in the SQLAlchemy ecosystem, which ensures seamless integration and broad community support.

## Consequences

-   **Positive**:
    -   Robust and auditable database change management process.
    -   Safer and more predictable deployments.
    -   Facilitates team collaboration, as all schema changes are in version control.

-   **Negative**:
    -   Adds a new tool and layer of complexity to the project that the team must learn and maintain.
    -   Requires careful initial configuration to integrate correctly with the project structure (as we have seen with the `PYTHONPATH` configuration).