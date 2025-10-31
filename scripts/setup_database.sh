#!/bin/bash

# Script to setup the database for Ryder Cup Manager

echo "Setting up Ryder Cup Manager database..."

# Create database if it doesn't exist
createdb ryder_cup_db 2>/dev/null || echo "Database ryder_cup_db already exists"
createdb ryder_cup_test_db 2>/dev/null || echo "Test database ryder_cup_test_db already exists"

echo "Running Alembic migrations..."
alembic upgrade head

echo "Database setup completed!"