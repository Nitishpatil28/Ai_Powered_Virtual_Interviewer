import sqlite3

# Check users.db first
conn = sqlite3.connect('users.db')
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
print(f'Tables in users.db: {[t[0] for t in tables]}')

# Check if companies table exists
if 'companies' in [t[0] for t in tables]:
    # Count total companies
    cur.execute('SELECT COUNT(*) FROM companies')
    total = cur.fetchone()[0]
    print(f'Total companies: {total}')

    # Get all companies with their details
    cur.execute('SELECT id, name, min_cgpa, required_skills FROM companies LIMIT 10')
    companies = cur.fetchall()

    print('\nFirst 10 Companies:')
    for company in companies:
        print(f'ID: {company[0]}, Name: {company[1]}, Min CGPA: {company[2]}, Skills: {company[3][:50] if company[3] else "None"}...')
else:
    print('No companies table in users.db')

conn.close()

# Check if companies.db exists
import os
if os.path.exists('companies.db'):
    print('\ncompanies.db exists, checking...')
    conn2 = sqlite3.connect('companies.db')
    cur2 = conn2.cursor()
    cur2.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables2 = cur2.fetchall()
    print(f'Tables in companies.db: {[t[0] for t in tables2]}')
    conn2.close()
else:
    print('\ncompanies.db does not exist')