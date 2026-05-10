#!/bin/bash
# noslice-detector.sh - Automatically detects hosts that don't support HTTP Range requests
# and adds them to the noslice blocklist after NOSLICE_THRESHOLD failures.
#
# This script monitors the nginx error log for "invalid range in slice response" errors,
# tracks failures per host, and triggers nginx reload when a host is blocklisted.

set -e

# Configuration
NOSLICE_THRESHOLD=${NOSLICE_THRESHOLD:-3}
ERROR_LOG="/data/logs/error.log"
STATE_FILE="/data/noslice-state.json"
BLOCKLIST_FILE="/data/noslice-hosts.map"
LOCK_FILE="/tmp/noslice-detector.lock"

# Logging helper
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [noslice-detector] $1"
}

# Initialize state file if it doesn't exist
init_state() {
    if [[ ! -f "$STATE_FILE" ]]; then
        echo '{}' > "$STATE_FILE"
        log "Initialized state file"
    fi
}

# Initialize blocklist file if it doesn't exist
init_blocklist() {
    if [[ ! -f "$BLOCKLIST_FILE" ]]; then
        echo "# Auto-generated noslice hosts blocklist" > "$BLOCKLIST_FILE"
        echo "# Hosts here are routed to @noslice location (slice disabled)" >> "$BLOCKLIST_FILE"
        echo "# Format: \"hostname\" 1;" >> "$BLOCKLIST_FILE"
        log "Initialized blocklist file"
    fi
}

# Get failure count for a host from state
get_failure_count() {
    local host="$1"
    if [[ -f "$STATE_FILE" ]]; then
        local count=$(jq -r --arg h "$host" '.[$h] // 0' "$STATE_FILE" 2>/dev/null)
        echo "${count:-0}"
    else
        echo "0"
    fi
}

# Increment failure count for a host
increment_failure_count() {
    local host="$1"
    local current=$(get_failure_count "$host")
    local new=$((current + 1))
    
    # Update state file atomically
    local tmp=$(mktemp)
    jq --arg h "$host" --argjson c "$new" '.[$h] = $c' "$STATE_FILE" > "$tmp" && mv "$tmp" "$STATE_FILE"
    
    echo "$new"
}

# Check if host is already in blocklist
is_blocklisted() {
    local host="$1"
    grep -q "\"$host\" 1;" "$BLOCKLIST_FILE" 2>/dev/null
}

# Add host to blocklist
add_to_blocklist() {
    local host="$1"
    
    if is_blocklisted "$host"; then
        log "Host $host is already in blocklist"
        return 0
    fi
    
    # Add to blocklist
    echo "\"$host\" 1;" >> "$BLOCKLIST_FILE"
    log "Added $host to noslice blocklist"
    
    # Reload nginx to pick up the change
    reload_nginx
}

# Reload nginx configuration
reload_nginx() {
    log "Reloading nginx configuration..."
    if nginx -t 2>/dev/null; then
        nginx -s reload
        log "Nginx reloaded successfully"
    else
        log "ERROR: Nginx config test failed, not reloading"
    fi
}

# Process a single error line
process_error_line() {
    local line="$1"
    
    # Extract hostname from the error line
    # Format: ... host: "hostname"
    local host=$(echo "$line" | grep -oP 'host:\s*"\K[^"]+')
    
    if [[ -z "$host" ]]; then
        return
    fi
    
    # Skip if already blocklisted
    if is_blocklisted "$host"; then
        return
    fi
    
    # Increment failure count
    local count=$(increment_failure_count "$host")
    log "Slice error for host '$host' (failure $count of $NOSLICE_THRESHOLD)"
    
    # Check if threshold reached
    if [[ "$count" -ge "$NOSLICE_THRESHOLD" ]]; then
        log "Threshold reached for host '$host' - adding to blocklist"
        add_to_blocklist "$host"
    fi
}

# Main monitoring loop
monitor_logs() {
    log "Starting noslice-detector (threshold: $NOSLICE_THRESHOLD failures)"
    log "Monitoring: $ERROR_LOG"
    log "Blocklist: $BLOCKLIST_FILE"
    
    # Use tail -F to follow the log file (handles rotation)
    tail -n 0 -F "$ERROR_LOG" 2>/dev/null | while read -r line; do
        # Check for slice-related errors
        if echo "$line" | grep -q "invalid range in slice response\|unexpected range in slice response\|unexpected status code.*in slice response"; then
            process_error_line "$line"
        fi
    done
}

# Cleanup on exit
cleanup() {
    rm -f "$LOCK_FILE"
    log "noslice-detector stopped"
}

# Main entry point
main() {
    # Ensure only one instance runs
    if [[ -f "$LOCK_FILE" ]]; then
        pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if kill -0 "$pid" 2>/dev/null; then
            log "Another instance is already running (PID: $pid)"
            exit 1
        fi
    fi
    
    echo $$ > "$LOCK_FILE"
    trap cleanup EXIT
    
    init_state
    init_blocklist
    
    # Wait for error log to exist
    while [[ ! -f "$ERROR_LOG" ]]; do
        log "Waiting for error log to be created..."
        sleep 5
    done
    
    monitor_logs
}

main "$@"
