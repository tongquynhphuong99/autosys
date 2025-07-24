# TestOps Database Setup

## 📋 Overview
This directory contains the database setup files for the TestOps system.

## 🗄️ Database Schema

### Tables
- **users** - User authentication and management
- **projects** - Project management with team information and Jenkins jobs
- **testcases** - Test case definitions
- **executions** - Test execution results
- **plans** - Test plans and schedules
- **cicd** - CI/CD task management
- **reports** - Unified test reports for all task types
- **logs** - System logs and debugging information

### Key Features
- **Unified Reports**: Single `reports` table for all task types (executions, plans, CI/CD)
- **Jenkins Integration**: Projects can have multiple Jenkins jobs stored as JSON
- **CI/CD Support**: Dedicated `cicd` table with unique identifiers
- **Task Identification**: Consistent task_id format across all task types

### Projects Table Structure
```sql
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    repo_link TEXT,                    -- Repository URL
    project_manager VARCHAR(100),      -- Project Manager name
    members TEXT[],                    -- Array of team member names
    jenkins_jobs JSON DEFAULT '[]'::json, -- Array of Jenkins job objects
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🚀 Quick Setup

### Prerequisites
- PostgreSQL installed and running
- `psql` command line tool available

### Automatic Setup
```bash
# Make script executable
chmod +x setup.sh

# Run setup script
./setup.sh
```

### Manual Setup
```bash
# 1. Create database and user
psql -U postgres -c "CREATE USER testops_user WITH PASSWORD 'testops_password';"
psql -U postgres -c "CREATE DATABASE testops OWNER testops_user;"

# 2. Grant privileges
psql -U postgres -d testops -c "GRANT ALL PRIVILEGES ON DATABASE testops TO testops_user;"
psql -U postgres -d testops -c "GRANT ALL ON SCHEMA public TO testops_user;"

# 3. Create tables
psql -U testops_user -d testops -f schema.sql

# 4. Insert sample data
psql -U testops_user -d testops -f init.sql
```

## 📊 Sample Data

The `init.sql` file includes sample projects with:
- **E-commerce Website Testing** - Active project with 4 team members
- **Mobile App Testing** - Active project with 2 team members  
- **API Testing Project** - Completed project with 3 team members
- **Performance Testing** - Paused project with 1 team member

Each project includes:
- Repository links (GitHub, GitLab, Bitbucket)
- Project Manager assignments
- Team member lists
- Realistic descriptions in Vietnamese

## 🔧 Configuration

### Database Connection
- **Host**: localhost
- **Port**: 5432
- **Database**: testops
- **User**: testops_user
- **Password**: testops_password

### Connection String
```
postgresql://testops_user:testops_password@localhost:5432/testops
```

## 📁 Files

- `schema.sql` - Complete database schema with all tables and migrations
- `init.sql` - Sample data insertion
- `setup.sh` - Automated setup script
- `config.py` - Database configuration for backend
- `README.md` - This documentation

## 🔄 Migration History

The `schema.sql` file now includes all previous migrations:
- ✅ Added `cicd_id` to CI/CD table
- ✅ Added `jenkins_jobs` JSON field to projects table
- ✅ Unified reports table for all task types
- ✅ Added proper indexes and constraints
- ✅ Added comprehensive documentation comments

## 🔄 Migration

To update the database schema:
1. Create a new migration file in `migrations/` directory
2. Update `schema.sql` if needed
3. Run the migration script
4. Update `init.sql` with new sample data if needed

## 🛠️ Troubleshooting

### Common Issues
1. **PostgreSQL not running**: Start PostgreSQL service
2. **Permission denied**: Run as postgres user or use sudo
3. **Database exists**: Script will handle existing database gracefully
4. **Connection refused**: Check PostgreSQL is listening on port 5432

### Reset Database
```bash
# Drop and recreate database
psql -U postgres -c "DROP DATABASE IF EXISTS testops;"
./setup.sh
``` 