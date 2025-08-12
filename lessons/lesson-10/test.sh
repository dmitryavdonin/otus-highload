#!/bin/bash
#
# Wrapper script for Counter Service E2E Tests
# Usage: ./test.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Counter Service E2E Test Runner ===${NC}"
echo ""

# Check if test file exists
if [ ! -f "test_counters.py" ]; then
    echo -e "${RED}ERROR: test_counters.py not found in current directory${NC}"
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found${NC}"
    exit 1
fi

# Check if services are running (quick health check)
echo -e "${YELLOW}Checking services health...${NC}"
if ! curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: API service (port 8000) is not responding${NC}"
    echo -e "${YELLOW}Please start services first: ./start_service.sh${NC}"
    exit 1
fi

if ! curl -s -f http://localhost:8002/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Dialog service (port 8002) is not responding${NC}"
    echo -e "${YELLOW}Please start services first: ./start_service.sh${NC}"
    exit 1
fi

if ! curl -s -f http://localhost:8003/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Counter service (port 8003) is not responding${NC}"
    echo -e "${YELLOW}Please start services first: ./start_service.sh${NC}"
    exit 1
fi

echo -e "${GREEN}All services are healthy!${NC}"
echo ""

# Run the Python test
echo -e "${BLUE}Running Counter Service E2E Tests...${NC}"
echo ""

python3 test_counters.py

# Capture exit code
TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests completed successfully!${NC}"
else
    echo -e "${RED}❌ Tests failed with exit code: $TEST_EXIT_CODE${NC}"
fi

exit $TEST_EXIT_CODE
