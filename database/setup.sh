#!/bin/bash

# TestOps Complete Setup and Start Script
# This script will setup database, start all services, and configure Jenkins

echo "🚀 TestOps Complete Setup and Start Script"
echo "=========================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start containers
echo "🔨 Building and starting containers..."
docker-compose up --build -d

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 15

# Database setup section
echo ""
echo "🗄️ Setting up TestOps Database..."

# Database configuration
DB_NAME="testops"
DB_USER="testops_user"
DB_PASSWORD="testops_password"

# Wait for PostgreSQL container to be healthy
echo "⏳ Waiting for PostgreSQL container to be healthy..."
for i in {1..30}; do
    if docker exec testops_postgres pg_isready -U $DB_USER -d $DB_NAME > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    echo "⏳ Waiting for PostgreSQL... ($i/30)"
    sleep 2
done

# Check if PostgreSQL is running
if ! docker exec testops_postgres pg_isready -U $DB_USER -d $DB_NAME > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not ready. Please check container logs."
    docker-compose logs postgres
    exit 1
fi

echo "✅ PostgreSQL is running"

# Create database user if not exists
echo "👤 Creating database user..."
docker exec testops_postgres psql -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || echo "User already exists"

# Create database if not exists
echo "🗄️ Creating database..."
docker exec testops_postgres psql -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo "Database already exists"

# Grant privileges
echo "🔐 Granting privileges..."
docker exec testops_postgres psql -U postgres -d $DB_NAME -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
docker exec testops_postgres psql -U postgres -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

# Run schema and init scripts
echo "📋 Creating tables..."
docker exec testops_postgres psql -U $DB_USER -d $DB_NAME -f /docker-entrypoint-initdb.d/01-schema.sql

echo "📊 Inserting sample data..."
docker exec testops_postgres psql -U $DB_USER -d $DB_NAME -f /docker-entrypoint-initdb.d/02-init.sql

echo "✅ Database setup completed!"
echo ""
echo "📋 Database Information:"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo "   Password: $DB_PASSWORD"
echo "   Host: localhost"
echo "   Port: 5432"
echo ""
echo "🔗 Connection string:"
echo "   postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"

# Check if containers are running
echo ""
echo "📊 Checking container status..."
docker-compose ps

# Test database connection
echo ""
echo "🔍 Testing database connection..."
sleep 5
curl -f http://localhost:8000/db-test || echo "Backend not ready yet, retrying..."

# Wait a bit more and test again
sleep 10
echo "🔍 Final database connection test..."
curl -f http://localhost:8000/db-test

# Jenkins setup section
echo ""
echo "🔧 Setting up Jenkins..."

# Check if Jenkins container exists
if docker ps -a --format "table {{.Names}}" | grep -q "testops_jenkins"; then
    echo "✅ Jenkins container found"
    
    # Wait for Jenkins to be ready
    echo "⏳ Waiting for Jenkins to start..."
    sleep 30
    
    # Get initial admin password
    echo "🔑 Getting initial admin password..."
    JENKINS_PASSWORD=$(docker exec testops_jenkins cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "admin")
    
    echo "📋 Jenkins Information:"
    echo "   URL: http://localhost:8080"
    echo "   Username: admin"
    echo "   Initial Password: $JENKINS_PASSWORD"
    echo ""
    echo "📝 Jenkins setup steps:"
    echo "   1. Open http://localhost:8080 in your browser"
    echo "   2. Login with admin / $JENKINS_PASSWORD"
    echo "   3. Install suggested plugins"
    echo "   4. Create admin user or skip"
    echo "   5. Create sample Jenkins jobs for testing"
    echo ""
    echo "🔗 To create API token:"
    echo "   1. Go to http://localhost:8080/user/admin/configure"
    echo "   2. Add new token in 'API Token' section"
    echo "   3. Update JENKINS_TOKEN in docker-compose.yml"
    echo ""
    echo "✅ Jenkins setup completed!"
else
    echo "⚠️  Jenkins container not found. Please run 'docker-compose up -d' first."
    echo "📝 Then run this script again to get Jenkins information."
fi



echo ""
echo "✅ TestOps System is starting up!"
echo ""
echo "📋 Access URLs:"
echo "   Dashboard: http://localhost:8000"
echo "   Projects: http://localhost:8000/projects"
echo "   Executions: http://localhost:8000/executions"
echo "   API Health: http://localhost:8000/health"
echo "   Database Test: http://localhost:8000/db-test"
echo "   Jenkins: http://localhost:8080"
echo ""
echo "📊 Container Status:"
docker-compose ps
echo ""
echo "📝 Useful Commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop system: docker-compose down"
echo "   Restart: docker-compose restart"
echo ""
echo "🎉 TestOps setup and start completed!" 