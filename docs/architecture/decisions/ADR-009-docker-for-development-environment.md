# ADR-009: Use of Docker for Development Environment

- **Status**: Accepted
- **Date**: 2025-11-04

## Context

As the project evolves, it introduces dependencies on external services, with the first and most critical being a PostgreSQL database. To develop and test the application reliably, we need a way to manage these dependencies that is consistent, reproducible, and isolated from the developer's operating system.

Alternatives for managing these dependencies include:
1.  **Local installation**: Each developer manually installs and configures PostgreSQL on their machine.
2.  **Shared cloud database**: All developers point to a single remote database.
3.  **Containerization**: A container technology is used to package services and run them locally.

## Decision

We have decided to adopt **Docker** and **Docker Compose** as the standard tool for managing the local development environment.

This implies:
-   A `Dockerfile` that defines the image of our Python/FastAPI application.
-   A `docker-compose.yml` that orchestrates the startup of necessary services: the application (`app`) and the PostgreSQL database (`db`).
-   The use of a `.env` file to manage credentials and configuration, keeping them out of version control.

## Justification

This decision is based on the following key advantages:

1.  **Environment Consistency**: Ensures that all developers, as well as continuous integration systems, run the application and its dependencies (such as the exact version of PostgreSQL) in an identical environment. This completely eliminates "works on my machine" problems.

2.  **Isolation**: Services run in isolated containers, which prevents conflicts with other databases or other versions of services that a developer may have locally installed for other projects.

3.  **Ease of Setup (Onboarding)**: A new developer can have the entire development environment running with a single command (`docker-compose up`). This drastically reduces the time and complexity of initial setup.

4.  **Development-Production Parity**: Allows us to develop in an environment that closely resembles the final production environment, following DevOps best practices.

5.  **Portability**: The configuration is completely portable across different operating systems (macOS, Windows, Linux) without requiring changes.

## Consequences

-   **Positive**:
    -   Greater reliability and reproducibility of builds.
    -   Simplified onboarding process for new team members.
    -   Clean development environment without conflicts.

-   **Negative**:
    -   Introduces a dependency on Docker Desktop, which must be installed by each developer.
    -   Slight overhead in resource usage (CPU/RAM) compared to native execution, although it is marginal on modern hardware.