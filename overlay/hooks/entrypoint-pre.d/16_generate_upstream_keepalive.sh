#!/bin/bash
set -e

# Generates upstream pools with keepalive for concrete (non-wildcard) domains
# from cache_domains.json

# Note: 'resolve' parameter not used - requires nginx 1.27.3+
# Currently DNS resolution happens at nginx startup/reload
# To enable dynamic DNS resolution when nginx >= 1.27.3, edit pools conf:
#   1. Add 'resolver ${UPSTREAM_DNS} ipv6=off;' at start of the file
#   2. Add 'resolve' parameter to each 'server' directive

IFS=' '
cd /data/cachedomains

TEMP_PATH=$(mktemp -d)
POOLS_TMP_FILE="${TEMP_PATH}/pools.conf"
POOLS_FILE="/etc/nginx/conf.d/40_upstream_pools.conf"
MAPS_TMP_FILE="${TEMP_PATH}/maps.conf"
MAPS_FILE="/etc/nginx/conf.d/35_upstream_maps.conf"

echo "Generating upstream keepalive pools from cache_domains.json"

# Initialize pools file
echo "# Auto-generated upstream pools with keepalive" > "$POOLS_TMP_FILE"
echo "# Generated from cache_domains.json at $(date)" >> "$POOLS_TMP_FILE"
echo "" >> "$POOLS_TMP_FILE"

# Initialize maps file
echo "# Map hostnames to upstream pools for keepalive routing" > "$MAPS_TMP_FILE"
echo "" >> "$MAPS_TMP_FILE"
echo "map \$http_host \$upstream_name {" >> "$MAPS_TMP_FILE"
echo "    hostnames;" >> "$MAPS_TMP_FILE"
echo "    default \$host;  # Fallback to direct proxy for unmapped domains" >> "$MAPS_TMP_FILE"
echo "    *.steamcontent.com lancache_steamcontent_com; # Redirect all steam traffic" >> "$MAPS_TMP_FILE"

# Loop through each cache service
# Using process substitution to avoid subshell context issues with pipes
while read CACHE_ENTRY; do
    # Get service name
    SERVICE_NAME=$(jq -r ".cache_domains[$CACHE_ENTRY].name" cache_domains.json)

    echo "Processing service: ${SERVICE_NAME}"

    # Loop through domain files for this service
    while read CACHEHOSTS_FILEID; do
        # Get the domain file name
        CACHEHOSTS_FILENAME=$(jq -r ".cache_domains[$CACHE_ENTRY].domain_files[$CACHEHOSTS_FILEID]" cache_domains.json)

        if [ ! -f "${CACHEHOSTS_FILENAME}" ]; then
            echo "  Warning: Domain file not found: ${CACHEHOSTS_FILENAME}"
            continue
        fi

        # Read each domain from the file
        while read DOMAIN; do
            # Skip empty lines and whitespace
            DOMAIN=$(echo "$DOMAIN" | tr -d '[:space:]')
            if [ -z "$DOMAIN" ]; then
                continue
            fi

            # Skip comments
            if [[ "$DOMAIN" =~ ^# ]]; then
                continue
            fi

            # Skip wildcards - can't create upstream for *.example.com
            if [[ "$DOMAIN" =~ \* ]]; then
                echo "  Skipping wildcard: $DOMAIN"
                continue
            fi

            # Resolve domain using external DNS to bypass local lancache DNS overrides
            # This prevents nginx from looping back to itself
            RESOLVED_IP=$(dig +short +time=2 +tries=1 "$DOMAIN" @${UPSTREAM_DNS%% *} 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
            if [ -z "$RESOLVED_IP" ]; then
                echo "  Skipping unresolvable domain: $DOMAIN"
                continue
            fi

            echo "  Adding upstream for: $DOMAIN -> $RESOLVED_IP"

            # Sanitize domain name for use as upstream name
            # Replace dots and dashes with underscores
            UPSTREAM_NAME=$(echo "$DOMAIN" | sed 's/[.-]/_/g')

            # Generate upstream block with resolved IP
            cat >> "$POOLS_TMP_FILE" <<EOF
upstream ${UPSTREAM_NAME} {
    server ${RESOLVED_IP};  # $DOMAIN
    keepalive 16;
    keepalive_timeout 5m;
}

EOF

            # Add mapping entry
            echo "    ${DOMAIN} ${UPSTREAM_NAME};" >> "$MAPS_TMP_FILE"
        done < "${CACHEHOSTS_FILENAME}"
    done < <(jq -r ".cache_domains[$CACHE_ENTRY].domain_files | to_entries[] | .key" cache_domains.json)
done < <(jq -r '.cache_domains | to_entries[] | .key' cache_domains.json)

# Close the map block
echo "}" >> "$MAPS_TMP_FILE"

# Copy to final locations
cp "$POOLS_TMP_FILE" $POOLS_FILE
cp "$MAPS_TMP_FILE" $MAPS_FILE

# Validate final configuration after copying
echo "Validating final nginx configuration..."
if nginx -t 2>/dev/null; then
    echo "✓ Nginx configuration is valid"
    echo "Output files:"
    echo "  - $POOLS_FILE"
    echo "  - $MAPS_FILE"
else
    echo "ERROR: Generated keepalive configuration caused nginx validation to fail!"
    echo "Rolling back generated files to allow nginx to start normally..."
    rm -f $POOLS_FILE
    rm -f $MAPS_FILE
fi

# Cleanup
rm -rf "$TEMP_PATH"
