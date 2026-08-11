#!/bin/bash

# Quick Log Stack Manager

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
    echo "Quick Log Stack Manager"
    echo ""
    echo "Usage: ./manage_stack.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       - Start all services (ES internal-only)"
    echo "  start-live  - Start with ES exposed on localhost:9200 + install ql CLI"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  status      - Check service status"
    echo "  logs        - View logs from all services"
    echo "  rebuild     - Rebuild containers and restart"
    echo "  install-cli - Install ql CLI to ~/.local/bin (on PATH)"
    echo ""
    echo "Services available at:"
    echo "  - Quick Log:   http://localhost:8501"
    echo "  - Kibana:      http://localhost:5601"
    echo "  - ES (live):   http://localhost:9200  [start-live only]"
}

write_resource_status() {
    local MEM_GB=0
    local CPU_COUNT=0
    local DOCKER_VER="unknown"
    local SOURCE="unknown"
    
    if command -v colima &>/dev/null; then
        local LIST_LINE=$(colima list 2>/dev/null | grep -E "default|Running" | head -1)
        if [ -n "$LIST_LINE" ]; then
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
    echo "⏳ Waiting for services to become healthy..."
    local timeout=300
    local start_time=$(date +%s)
    local EXPECTED_COUNT=3

    echo -n "   Initializing containers"
    for i in {1..10}; do
        local current_count=$(docker ps -a --filter name=quick-log --format "{{.Names}}" | wc -l | tr -d ' ')
        if [ "$current_count" -ge "$EXPECTED_COUNT" ]; then
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -gt $timeout ]; then
            echo ""
            echo "❌ Timeout reached. Some services may not be healthy."
            echo "Current status:"
            docker ps --filter name=quick-log --format "table {{.Names}}\t{{.Status}}\t{{.State}}"
            return 1
        fi

        local running_count=$(docker ps --filter name=quick-log --format "{{.State}}" | grep -c "running")
        local healthy_count=$(docker ps --filter name=quick-log --format "{{.Status}}" | grep -c "healthy")
        local unhealthy_count=$(docker ps --filter name=quick-log --format "{{.Status}}" | grep -c "unhealthy")

        if [ "$running_count" -ge "$EXPECTED_COUNT" ] && [ "$healthy_count" -ge 2 ] && [ "$unhealthy_count" -eq 0 ]; then
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

install_cli() {
    local SCRIPT="$PROJECT_DIR/ql"
    local TARGET="$HOME/.local/bin/ql"

    if [ ! -f "$SCRIPT" ]; then
        echo "❌ ql not found at $SCRIPT"
        exit 1
    fi

    chmod +x "$SCRIPT"
    mkdir -p "$HOME/.local/bin"

    if [ -L "$TARGET" ] || [ -f "$TARGET" ]; then
        rm "$TARGET"
    fi
    ln -s "$SCRIPT" "$TARGET"

    case ":$PATH:" in
        *":$HOME/.local/bin:"*)
            echo "✅ ql installed → $TARGET"
            ;;
        *)
            echo "✅ ql installed → $TARGET"
            echo "⚠️  ~/.local/bin is not on your PATH. Add this to your shell profile:"
            echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
    esac
}

case "$1" in
    start)
        echo "🚀 Starting Quick Log Stack..."
        write_resource_status
        mkdir -p "$PROJECT_DIR/uploads"
        cmd=$(printf "$COMPOSE_CMD" "up -d")
        cd "$PROJECT_DIR" && eval "$cmd"
        wait_for_healthy
        echo ""
        echo "🎉 Services are ready!"
        echo "   📊 Quick Log:   http://localhost:8501"
        echo "   🔍 Kibana:      http://localhost:5601"
        ;;
    start-live)
        echo "🚀 Starting Quick Log Stack (Live Mode)..."
        echo "   Elasticsearch will be exposed on localhost:9200"
        write_resource_status
        mkdir -p "$PROJECT_DIR/uploads"
        cmd=$(printf "$COMPOSE_CMD" "-f docker-compose.yml -f docker-compose.live.yml up -d")
        cd "$PROJECT_DIR" && eval "$cmd"
        wait_for_healthy
        echo ""
        echo "🎉 Services are ready! (Live mode)"
        echo "   📊 Quick Log:   http://localhost:8501"
        echo "   🔍 Kibana:      http://localhost:5601"
        echo "   🔗 Elasticsearch: http://localhost:9200"
        echo ""
        install_cli
        echo ""
        echo "   Try: myapp 2>&1 | ql stream --tag my-session"
        ;;
    stop)
        echo "🛑 Stopping Quick Log Stack..."
        cmd=$(printf "$COMPOSE_CMD" "down")
        cd "$PROJECT_DIR" && eval "$cmd"
        echo "✅ Services stopped."
        ;;
    restart)
        echo "🔄 Restarting Quick Log Stack..."
        write_resource_status
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
        cd "$PROJECT_DIR"
        cmd_down=$(printf "$COMPOSE_CMD" "down")
        cmd_build=$(printf "$COMPOSE_CMD" "build --no-cache")
        cmd_up=$(printf "$COMPOSE_CMD" "up -d")
        eval "$cmd_down" && eval "$cmd_build" && eval "$cmd_up"
        wait_for_healthy
        echo "✅ Containers rebuilt and restarted."
        ;;
    install-cli)
        install_cli
        ;;
    *)
        show_help
        exit 1
        ;;
esac
