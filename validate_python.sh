#!/bin/bash
# Python validation script for code quality maintenance

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check for target argument
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: ./validate_python.sh <file_or_directory> [--fix]${NC}"
    exit 1
fi

FILE_OR_DIR=$1
FIX_MODE=false

# Set mode based on arguments
if [ "$2" == "--fix" ]; then
    FIX_MODE=true
    echo -e "${YELLOW}Fix mode enabled${NC}"
else
    echo -e "${YELLOW}Check mode only${NC}"
fi

# isort validation
validate_with_isort() {
    echo -e "\n${BLUE}isort:${NC}"
    if [ "$FIX_MODE" = true ]; then
        python -m isort "$FILE_OR_DIR"
        [ $? -eq 0 ] && echo -e "${GREEN}Import ordering fixed${NC}" || echo -e "${RED}Import fixing failed${NC}"
    else
        python -m isort --check --diff "$FILE_OR_DIR"
        [ $? -eq 0 ] && echo -e "${GREEN}Import ordering passed${NC}" || echo -e "${RED}Import ordering issues found${NC}"
    fi
}

# black validation
validate_with_black() {
    echo -e "\n${BLUE}black:${NC}"
    if [ "$FIX_MODE" = true ]; then
        black "$FILE_OR_DIR"
        [ $? -eq 0 ] && echo -e "${GREEN}Code formatting complete${NC}" || echo -e "${RED}Formatting failed${NC}"
    else
        black --check "$FILE_OR_DIR"
        [ $? -eq 0 ] && echo -e "${GREEN}Code formatting passed${NC}" || echo -e "${RED}Formatting issues found${NC}"
    fi
}

# flake8 validation
validate_with_flake8() {
    echo -e "\n${BLUE}flake8:${NC}"
    python -m flake8 "$FILE_OR_DIR"
    [ $? -eq 0 ] && echo -e "${GREEN}Linting passed${NC}" || echo -e "${RED}Linting issues found${NC}"
}

# Run django tests
run_tests() {
    APP_NAME=""
    if [[ "$FILE_OR_DIR" == *"/"* ]]; then
        APP_NAME=$(echo "$FILE_OR_DIR" | cut -d'/' -f1)
    else
        APP_NAME="$FILE_OR_DIR"
    fi
    
    if [[ "$APP_NAME" =~ ^(accounts|core|shifts|subscriptions|notifications|contact|home)$ ]]; then
        echo -e "\n${BLUE}Running $APP_NAME tests${NC}"
        python manage.py test "$APP_NAME"
        return $?
    else
        echo -e "${YELLOW}Skipping tests - no clear module path${NC}"
        return 0
    fi
}

echo -e "\n${BLUE}Validating: $FILE_OR_DIR${NC}"

# Run pre-change tests if fixing
if [ "$FIX_MODE" = true ]; then
    run_tests
    PRE_TEST_STATUS=$?
    
    if [ $PRE_TEST_STATUS -ne 0 ]; then
        echo -e "${RED}Initial tests failed - aborting${NC}"
        exit 1
    fi
fi

# Run validations
validate_with_isort
validate_with_black
validate_with_flake8

# Run post-change tests if fixes were applied
if [ "$FIX_MODE" = true ]; then
    run_tests
    POST_TEST_STATUS=$?
    
    if [ $POST_TEST_STATUS -ne 0 ]; then
        echo -e "${RED}Tests failed after changes - revert changes${NC}"
        exit 1
    fi
fi

echo -e "\n${BLUE}Validation complete${NC}"