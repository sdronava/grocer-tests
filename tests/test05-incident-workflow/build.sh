#!/bin/bash
# Builds Lambda deployment packages targeting Linux x86_64 (the Lambda runtime).
#
# Packages are installed into dist/ subdirectories so that macOS-compiled
# binaries from a previous run are never mixed with Linux binaries.
# handler.py is copied into dist/ so each dist/ directory is a self-contained
# deployment package ready to be zipped by Pulumi.
#
# Re-run this any time handler.py or requirements.txt changes, then
# run `pulumi up` to redeploy.
#
# Requires: uv (https://github.com/astral-sh/uv)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Cleaning previous builds..."
rm -rf "$SCRIPT_DIR/lambdas/workflow/dist"
rm -rf "$SCRIPT_DIR/slack_app/dist"
mkdir -p "$SCRIPT_DIR/lambdas/workflow/dist"
mkdir -p "$SCRIPT_DIR/slack_app/dist"

echo "Installing workflow Lambda dependencies (linux/x86_64)..."
uv pip install \
    -r "$SCRIPT_DIR/lambdas/workflow/requirements.txt" \
    --target "$SCRIPT_DIR/lambdas/workflow/dist/" \
    --python-platform x86_64-unknown-linux-gnu \
    --python-version 3.12 \
    --only-binary :all: \
    --quiet

echo "Installing Slack interactivity Lambda dependencies (linux/x86_64)..."
uv pip install \
    -r "$SCRIPT_DIR/slack_app/requirements.txt" \
    --target "$SCRIPT_DIR/slack_app/dist/" \
    --python-platform x86_64-unknown-linux-gnu \
    --python-version 3.12 \
    --only-binary :all: \
    --quiet

echo "Copying handlers into dist/..."
cp "$SCRIPT_DIR/lambdas/workflow/handler.py" "$SCRIPT_DIR/lambdas/workflow/dist/"
cp "$SCRIPT_DIR/slack_app/handler.py"        "$SCRIPT_DIR/slack_app/dist/"

echo "Done. Run 'pulumi up' to deploy the updated Lambda packages."
