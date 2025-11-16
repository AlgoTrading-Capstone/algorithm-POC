# PostgreSQL + TimescaleDB Installation Guide (Windows)

## Database Overview

This project uses a **PostgreSQL + TimescaleDB** stack for storing and managing time-series market data for Bitcoin algorithmic trading.

### Technologies & Versions

| Component | Version | Purpose |
|-----------|---------|---------|
| **PostgreSQL** | 16.11 | Primary relational database |
| **TimescaleDB** | 2.23.1 | Time-series extension for PostgreSQL |
| **Python** | 3.11.7 | Application runtime |
| **psycopg2-binary** | 2.9.9 | PostgreSQL adapter for Python |
| **SQLAlchemy** | 2.0.23 | SQL toolkit and ORM |

### Why PostgreSQL + TimescaleDB?

- **PostgreSQL**: ACID-compliant, production-proven relational database with excellent reliability
- **TimescaleDB**: Specialized extension that optimizes PostgreSQL for time-series workloads
  - Automatic partitioning (hypertables)
  - Built-in resampling and aggregation functions
  - Up to 90% storage compression for historical data
  - Native support for time-bucketing queries
  - Maintains full SQL compatibility

This combination provides:
- Fast ingestion of OHLCV candle data
- Efficient lookback window queries for trading strategies
- Easy timeframe resampling (5m → 1h, 15m, etc.)
- Reliable storage for trade execution history
- Support for both time-series and relational data in one system

---

## Installation Steps

### Step 1: Download PostgreSQL

1. Visit: [https://www.enterprisedb.com/downloads/postgres-postgresql-downloads](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)

2. Select **PostgreSQL 16.11** for **Windows x86-64**

3. Download the installer: `postgresql-16.11-1-windows-x64.exe`

---

### Step 2: Install PostgreSQL

1. **Run the installer** (right-click → Run as Administrator)

2. **Component Selection** - Select all:
   - ☑️ PostgreSQL Server
   - ☑️ pgAdmin 4
   - ☑️ Stack Builder
   - ☑️ Command Line Tools

3. **Data Directory** - Keep default:
   ```
   C:\Program Files\PostgreSQL\16\data
   ```

4. **Password** - Set a password for the `postgres` superuser
   ```
   Example: postgres123
   ```
   ⚠️ **Write this down!** You'll need it later.

5. **Port** - Keep default:
   ```
   5432
   ```

6. **Locale** - Keep "Default locale"

7. **Finish Installation**
   - When prompted about Stack Builder, check the box (we'll use it for TimescaleDB)
   - Click Finish

---

### Step 3: Add PostgreSQL to System PATH

1. Press **Win + R**, type `sysdm.cpl`, press Enter

2. Go to **Advanced** tab → **Environment Variables**

3. Under **System variables**, find **Path** → Click **Edit**

4. Click **New** and add:
   ```
   C:\Program Files\PostgreSQL\16\bin
   ```

5. Click **OK** on all windows

6. **Restart any open Command Prompt/Terminal windows**

7. **Verify** - Open CMD and run:
   ```cmd
   pg_config --version
   ```
   Should output: `PostgreSQL 16.11`

---

### Step 4: Download TimescaleDB

1. Visit: [https://github.com/timescale/timescaledb/releases](https://github.com/timescale/timescaledb/releases)

2. Find the latest release (v2.23.1 or newer)

3. Download the Windows installer for PostgreSQL 16:
   - Look for: `timescaledb-postgresql-16-windows-X.X.X-amd64.zip`
   - Or direct installer: `timescaledb-windows-setup.exe`

4. Extract to a temporary location:
   ```
   C:\temp\timescaledb\
   ```

---

### Step 5: Install TimescaleDB

#### Option A: Using the Installer (Recommended)

1. **Stop PostgreSQL Service**:
   ```cmd
   # Open CMD as Administrator
   net stop postgresql-x64-16
   ```

2. **Run the setup**:
   ```cmd
   cd C:\temp\timescaledb
   setup.exe
   ```

3. **Follow prompts**:
   - When asked for `postgresql.conf` path:
     ```
     C:\Program Files\PostgreSQL\16\data\postgresql.conf
     ```
   - Tune settings? → **y** (yes)
   - The installer will:
     - Copy DLL files
     - Modify `postgresql.conf`
     - Optimize settings for your hardware

4. **Start PostgreSQL**:
   ```cmd
   net start postgresql-x64-16
   ```

#### Option B: Manual Installation

If the installer fails:

1. **Stop PostgreSQL**:
   ```cmd
   net stop postgresql-x64-16
   ```

2. **Copy files manually**:
   
   From `C:\temp\timescaledb\` to PostgreSQL directories:
   
   ```
   timescaledb.control → C:\Program Files\PostgreSQL\16\share\extension\
   timescaledb.dll → C:\Program Files\PostgreSQL\16\lib\
   timescaledb--*.sql → C:\Program Files\PostgreSQL\16\share\extension\
   ```

3. **Edit postgresql.conf**:
   
   Open: `C:\Program Files\PostgreSQL\16\data\postgresql.conf`
   
   Find and modify:
   ```
   shared_preload_libraries = 'timescaledb'
   ```

4. **Start PostgreSQL**:
   ```cmd
   net start postgresql-x64-16
   ```

---

### Step 6: Create Database

1. **Open pgAdmin 4** (installed with PostgreSQL)

2. **Connect** - Enter your postgres password

3. **Create Database**:
   - Right-click on **Databases** → **Create** → **Database**
   - Database name: `bitcoin_rl`
   - Owner: `postgres`
   - Click **Save**

---

### Step 7: Enable TimescaleDB Extension

1. **Right-click on `bitcoin_rl`** → **Query Tool**

2. **Run**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS timescaledb;
   ```

3. **Verify installation**:
   ```sql
   SELECT default_version, installed_version 
   FROM pg_available_extensions 
   WHERE name = 'timescaledb';
   ```
   
   Should return:
   | default_version | installed_version |
   |----------------|-------------------|
   | 2.23.1 | 2.23.1 |

✅ **TimescaleDB is now active!**

---

## Verification Checklist

- [ ] PostgreSQL 16.11 installed
- [ ] `pg_config` works from command line
- [ ] TimescaleDB extension files copied
- [ ] `postgresql.conf` configured with `shared_preload_libraries = 'timescaledb'`
- [ ] PostgreSQL service running
- [ ] Database `bitcoin_rl` created
- [ ] TimescaleDB extension enabled and version verified

---

## Next Steps

After successful installation:

1. Install Python dependencies:
   ```bash
   pip install psycopg2-binary sqlalchemy
   ```

2. Test connection from Python (see project documentation)

3. Create schema and hypertables (see project documentation)

---

## Troubleshooting

### "extension timescaledb is not available"
- Verify files were copied to `share/extension/` and `lib/`
- Check `postgresql.conf` has `shared_preload_libraries = 'timescaledb'`
- Restart PostgreSQL service

### "pg_config not found"
- Add `C:\Program Files\PostgreSQL\16\bin` to system PATH
- Restart terminal/CMD

### "Access is denied" during TimescaleDB installation
- Stop PostgreSQL service first: `net stop postgresql-x64-16`
- Run installer as Administrator
- Start service after: `net start postgresql-x64-16`

### PostgreSQL won't start
- Check Windows Event Viewer for errors
- Verify `postgresql.conf` syntax is correct
- Check port 5432 isn't already in use

---

## Additional Resources

- PostgreSQL Documentation: https://www.postgresql.org/docs/16/
- TimescaleDB Documentation: https://docs.timescale.com/
- Project GitHub: (your repository link)

---

**Last Updated**: November 16, 2025  
**PostgreSQL Version**: 16.11  
**TimescaleDB Version**: 2.23.1
