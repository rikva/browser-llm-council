#!/bin/bash
set -e

# Chrome auto-start is handled by the server itself
echo "Starting LLM Council server..."
python -m llm_council.main
