#!/bin/bash

# Data Automation Stack Manager
# Consolidated management for Streamlit app + ELK stack

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if docker-compose --version &>/dev/null; then
    COMPOSE_CMD="docker-compose %s"
elif command -v nix-shell &>/dev/null; then
    COMPOSE_CMD='nix-shell -p docker-compose.out --run "docker-compose %s"'
else
    echo "Error: docker-compose is required but not available"
    echo "Install it or run with nix-shell -p docker-compose.out"
    exit 1
fi

show_help() {
    echo "Data Automation Stack Manager"
    echo ""
    echo "Usage: ./manage_stack.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start all services (ELK + Streamlit)"
    echo "  stop     - Stop all services"
    echo "  restart  - Restart all services"
    echo "  status   - Check service status"
    echo "  logs     - View logs from all services"
    echo "  rebuild  - Rebuild containers and restart"
    echo ""
    echo "Services available at:"
    echo "  - Streamlit App: http://localhost:8501"
    echo "  - Kibana:        http://localhost:5601"
    echo "  - Elasticsearch: http://localhost:9200"
}

write_resource_status() {
    local MEM_GB=0
    local CPU_COUNT=0
    local DOCKER_VER="unknown"
    local SOURCE="unknown"
    
    # Use 'colima list' for reliable memory/cpu detection (handles different output formats)
    if command -v colima &>/dev/null; then
        local LIST_LINE=$(colima list 2>/dev/null | grep -E "default|Running" | head -1)
        if [ -n "$LIST_LINE" ]; then
            # Parse: PROFILE STATUS ARCH CPUS MEMORY DISK RUNTIME ADDRESS
            CPU_COUNT=$(echo "$LIST_LINE" | awk '{print $4}' | grep -oE '[0-9]+' || echo 0)
            MEM_GB=$(echo "$LIST_LINE" | awk '{print $5}' | grep -oE '[0-9]+' || echo 0)
            SOURCE="colima_list"
        fi
    fi
    
    if command -v docker &>/dev/null; then
        DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
    fi
    
    cat > "$PROJECT_DIR/.resources.json" << EOF
{
  "timestamp": $(date +%s),
  "colima_memory_gb": $MEM_GB,
  "colima_cpu_count": $CPU_COUNT,
  "docker_version": "$DOCKER_VER",
  "source": "$SOURCE"
}
EOF
}

wait_for_healthy() {
    echo "⏳ Waiting for services to become healthy (this may take 2-3 minutes)..."
    local timeout=300
    local start_time=$(date +%s)
    local EXPECTED_COUNT=4

    # Phase 1: Wait for containers to actually exist in docker ps
    echo -n "   Initializing containers"
    for i in {1..10}; do
        local current_count=$(docker ps -a --filter name=quick-log --filter name=quick-log --format "{{.Names}}" | wc -l | tr -d ' ')
        if [ "$current_count" -ge "$EXPECTED_COUNT" ]; then
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""

    # Phase 2: Wait for all to be running AND healthy
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo ""
            echo "❌ Timeout reached. Some services may not be healthy."
            echo "Current status:"
            docker ps --filter name=quick-log --filter name=quick-log --format "table {{.Names}}\t{{.Status}}\t{{.State}}"
            return 1
        fi

        local running_count=$(docker ps --filter name=quick-log --filter name=quick-log --format "{{.State}}" | grep -c "running")
        local healthy_count=$(docker ps --filter name=quick-log --filter name=quick-log --format "{{.Status}}" | grep -c "healthy")
        local unhealthy_count=$(docker ps --filter name=quick-log --filter name=quick-log --format "{{.Status}}" | grep -c "unhealthy")

        # We need all 4 running, and at least 3 healthy (ES, Kibana, Stremlit have healthchecks, Logstash might take longer)
        if [ "$running_count" -ge "$EXPECTED_COUNT" ] && [ "$healthy_count" -ge 3 ] && [ "$unhealthy_count" -eq 0 ]; then
            echo ""
            echo "✅ All $running_count services are running and healthy!"
            return 0
        fi

        echo -n "."
        sleep 5
    done
}

if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

case "$1" in
    start)
        echo "🚀 Starting Data Automation Stack..."
        write_resource_status
        mkdir -p "$PROJECT_DIR/uploads/.tracking"
        chmod 777 "$PROJECT_DIR/uploads/.tracking"
        cmd=$(printf "$COMPOSE_CMD" "up -d")
        cd "$PROJECT_DIR" && eval "$cmd"
        wait_for_healthy
        echo ""
        echo "🎉 Services are ready!"
        echo "   📊 Streamlit:   http://localhost:8501"
        echo "   🔍 Kibana:      http://localhost:5601"
        echo "   🔌 Elastic:     http://localhost:9200"
        ;;
    stop)
        echo "🛑 Stopping Data Automation Stack..."
        cmd=$(printf "$COMPOSE_CMD" "down")
        cd "$PROJECT_DIR" && eval "$cmd"
        echo "✅ Services stopped."
        ;;
    restart)
        echo "🔄 Restarting Data Automation Stack..."
        write_resource_status
        mkdir -p "$PROJECT_DIR/uploads/.tracking"
        chmod 777 "$PROJECT_DIR/uploads/.tracking"
        cd "$PROJECT_DIR"
        cmd_down=$(printf "$COMPOSE_CMD" "down")
        cmd_up=$(printf "$COMPOSE_CMD" "up -d")
        eval "$cmd_down" && eval "$cmd_up"
        wait_for_healthy
        echo "✅ Services restarted."
        ;;
    status)
        echo "📊 Service Status:"
        docker ps --filter name=quick-log --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    logs)
        echo "📜 Fetching logs from all services..."
        cmd=$(printf "$COMPOSE_CMD" "logs -f")
        cd "$PROJECT_DIR" && eval "$cmd"
        ;;
    rebuild)
        echo "🏗️  Rebuilding containers..."
        write_resource_status
        mkdir -p "$PROJECT_DIR/uploads/.tracking"
        chmod 777 "$PROJECT_DIR/uploads/.tracking"
        cd "$PROJECT_DIR"
        cmd_down=$(printf "$COMPOSE_CMD" "down")
        cmd_build=$(printf "$COMPOSE_CMD" "build --no-cache")
        cmd_up=$(printf "$COMPOSE_CMD" "up -d")
        eval "$cmd_down" && eval "$cmd_build" && eval "$cmd_up"
        wait_for_healthy
        echo "✅ Containers rebuilt and restarted."
        ;;
    *)
        show_help
        exit 1
        ;;
esac
