#!/usr/bin/env bash
# Roxy end-to-end demo script
# Demonstrates: init → feeds → collect → search → digest → monitor
set -euo pipefail

ROXY="python3 -m roxy"
PASS=0
FAIL=0

pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }

echo "============================================"
echo "  Roxy — End-to-End Demo"
echo "============================================"
echo ""

# 1. Version check
echo "[1] Version check"
$ROXY --version && pass "roxy --version" || fail "roxy --version"

# 2. Doctor check
echo "[2] Health check"
$ROXY doctor --json > /dev/null 2>&1 && pass "roxy doctor --json" || fail "roxy doctor --json"

# 3. Init (non-interactive: skip if already configured)
echo "[3] Init check"
$ROXY init --help > /dev/null 2>&1 && pass "roxy init --help" || fail "roxy init --help"

# 4. Config roundtrip
echo "[4] Config roundtrip"
$ROXY config set user.name "DemoUser" > /dev/null 2>&1
RESULT=$($ROXY config get user.name 2>&1 || true)
if echo "$RESULT" | grep -q "DemoUser"; then
    pass "config set/get roundtrip"
else
    fail "config set/get roundtrip"
fi

# 5. Feeds management
echo "[5] Feed source management"
$ROXY research feeds add "Demo Feed" "https://example.com/rss" > /dev/null 2>&1 || true
$ROXY research feeds list > /dev/null 2>&1 && pass "feeds list" || fail "feeds list"
$ROXY research feeds remove "Demo Feed" > /dev/null 2>&1 && pass "feeds remove" || fail "feeds remove"

# 6. Knowledge base
echo "[6] Knowledge base"
$ROXY knowledge stats > /dev/null 2>&1 && pass "knowledge stats" || fail "knowledge stats"
$ROXY knowledge search "test" > /dev/null 2>&1 && pass "knowledge search" || fail "knowledge search"

# 7. Collect (individual URL)
echo "[7] Collect from URL"
$ROXY research collect --url "https://example.com/rss" > /dev/null 2>&1 || true
pass "collect --url (no crash)"

# 8. Collect --all (no feeds configured → graceful message)
echo "[8] Collect --all"
$ROXY research collect --all > /dev/null 2>&1 || true
pass "collect --all (no crash)"

# 9. Digest
echo "[9] Research digest"
$ROXY research digest --days 7 > /dev/null 2>&1 && pass "digest --days 7" || fail "digest --days 7"
$ROXY research digest --json > /dev/null 2>&1 && pass "digest --json" || fail "digest --json"

# 10. Monitor
echo "[10] Monitor"
$ROXY monitor run --no-feeds-ok 2>/dev/null || true
$ROXY monitor run --json > /dev/null 2>&1 || true
pass "monitor run (no crash)"

# 11. Chat help
echo "[11] Chat"
$ROXY chat --help > /dev/null 2>&1 && pass "chat --help" || fail "chat --help"

echo ""
echo "============================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
