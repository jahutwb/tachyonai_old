#!/bin/bash

# Script to set up a dedicated test environment for the RoundResult schema changes

# Exit on error
set -e

echo "Setting up test environment for RoundResult schema changes..."

# Create a test directory if it doesn't exist
TEST_DIR="test_environment"
if [ ! -d "$TEST_DIR" ]; then
    echo "Creating test directory: $TEST_DIR"
    mkdir -p "$TEST_DIR"
fi

# Clone the repository (if this is a fresh setup)
if [ ! -d "$TEST_DIR/tachyonai" ]; then
    echo "Cloning repository..."
    git clone git@github.com:yourusername/tachyonai.git "$TEST_DIR/tachyonai"
fi

# Navigate to the repository
cd "$TEST_DIR/tachyonai"

# Create a new branch for testing
TEST_BRANCH="test/round-result-schema-updates"
echo "Creating test branch: $TEST_BRANCH"
git checkout -b "$TEST_BRANCH"

# Apply the changes
echo "Applying RoundResult schema changes..."

# Copy the updated files
cp -r ../../backend/schemas.py backend/
cp -r ../../backend/routers/rounds.py backend/routers/
cp -r ../../frontend/static/js/game.js frontend/static/js/
cp -r ../../frontend/static/js/summary.js frontend/static/js/
cp -r ../../frontend/static/js/stats.js frontend/static/js/
cp -r ../../frontend/static/js/main.js frontend/static/js/
cp -r ../../backend/tests/test_round_processing.py backend/tests/

# Create a virtual environment
echo "Setting up Python virtual environment..."
python -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations if needed
echo "Running database migrations..."
alembic upgrade head

# Load test data
echo "Loading test data..."
python scripts/load_test_data.py

# Run tests to verify setup
echo "Running tests to verify setup..."
python -m pytest backend/tests/test_round_processing.py -v
python -m pytest tests/integration/test_api_sessions.py -v

# Start the application
echo "Starting the application..."
python -m backend.main &
APP_PID=$!

echo "Test environment setup complete!"
echo "The application is running at http://localhost:8000"
echo "Use the following test accounts:"
echo "  - Username: test_user, Password: test_password"
echo "  - Username: admin_user, Password: admin_password"
echo ""
echo "To stop the application, run: kill $APP_PID"
echo "To access the test environment, navigate to the $TEST_DIR/tachyonai directory"
echo "To activate the virtual environment, run: source venv/bin/activate"

# Copy test documentation to the test environment
echo "Copying test documentation..."
mkdir -p "$TEST_DIR/tachyonai/docs"
cp ../../docs/user_testing_plan.md "$TEST_DIR/tachyonai/docs/"
cp ../../docs/round_result_test_script.md "$TEST_DIR/tachyonai/docs/"
cp ../../docs/future_improvements.md "$TEST_DIR/tachyonai/docs/"
cp ../../docs/api_documentation.md "$TEST_DIR/tachyonai/docs/"
cp ../../docs/rounds_choice_endpoint.md "$TEST_DIR/tachyonai/docs/"
cp ../../docs/round_result_schema_changes.md "$TEST_DIR/tachyonai/docs/"

echo "Documentation copied to $TEST_DIR/tachyonai/docs/"
