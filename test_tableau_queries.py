"""
Test Tableau Query Patterns
Simulates Tableau's connection flow to test proxy functionality
"""

import pymysql
import sys
from datetime import datetime

# Connection config
PROXY_HOST = 'localhost'
PROXY_PORT = 3307
PROXY_USER = 'root'
PROXY_PASSWORD = 'your_password'  # Update this

def test_query(conn, name, query, expect_success=True):
    """Execute a test query and report results"""
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"Query: {query[:100]}...")
    print(f"Expected: {'SUCCESS' if expect_success else 'FAIL/EMPTY'}")

    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            row_count = len(results)

            print(f"✅ Result: SUCCESS - {row_count} rows returned")
            if row_count > 0 and row_count <= 5:
                for row in results:
                    print(f"   {row}")
            elif row_count > 5:
                print(f"   (showing first 3 rows)")
                for row in results[:3]:
                    print(f"   {row}")

            return True

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Result: ERROR - {error_msg}")

        if not expect_success:
            print(f"   (Expected to fail/return empty)")

        return False


def main():
    print(f"Tableau Query Pattern Test")
    print(f"Connecting to proxy at {PROXY_HOST}:{PROXY_PORT}")
    print(f"Time: {datetime.now().isoformat()}")

    # Connect to proxy
    try:
        conn = pymysql.connect(
            host=PROXY_HOST,
            port=PROXY_PORT,
            user=PROXY_USER,
            password=PROXY_PASSWORD,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor
        )
        print(f"✅ Connected to proxy")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        # Phase 1: Initial connection queries
        print(f"\n{'#'*60}")
        print(f"# PHASE 1: Initial Connection")
        print(f"{'#'*60}")

        test_query(conn, "SET NAMES", "SET NAMES utf8mb4")
        test_query(conn, "SELECT CONNECTION_ID", "SELECT CONNECTION_ID()")
        test_query(conn, "Connection Test", "SHOW STATUS LIKE 'Threads_connected'")

        # Phase 2: Database discovery
        print(f"\n{'#'*60}")
        print(f"# PHASE 2: Database Discovery")
        print(f"{'#'*60}")

        test_query(conn, "Get Database List (INFORMATION_SCHEMA)",
                  "SELECT NULL, NULL, NULL, SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME LIKE '%' ORDER BY SCHEMA_NAME")

        # Phase 3: Table discovery
        print(f"\n{'#'*60}")
        print(f"# PHASE 3: Table Discovery")
        print(f"{'#'*60}")

        # Use a specific database - UPDATE THIS
        db_name = 'test_db'  # Change to your database name

        test_query(conn, "USE Database", f"USE {db_name}")

        test_query(conn, "Get Table List (INFORMATION_SCHEMA)",
                  f"SELECT TABLE_NAME, TABLE_COMMENT, IF(TABLE_TYPE='BASE TABLE','TABLE', TABLE_TYPE), TABLE_SCHEMA "
                  f"FROM INFORMATION_SCHEMA.TABLES "
                  f"WHERE TABLE_SCHEMA LIKE '{db_name}' "
                  f"AND (TABLE_TYPE='BASE TABLE' OR TABLE_TYPE='VIEW') "
                  f"ORDER BY TABLE_SCHEMA, TABLE_NAME")

        # Phase 4: Metadata queries (should return empty gracefully)
        print(f"\n{'#'*60}")
        print(f"# PHASE 4: Metadata Queries (Expected: Empty)")
        print(f"{'#'*60}")

        test_query(conn, "SHOW KEYS (Unsupported)",
                  f"SHOW KEYS FROM {db_name}.some_table",
                  expect_success=False)

        # Phase 5: Custom SQL wrapper
        print(f"\n{'#'*60}")
        print(f"# PHASE 5: Custom SQL Wrapper")
        print(f"{'#'*60}")

        # Update this query with your actual table and cob_date
        custom_query = f"SELECT * FROM your_table WHERE cob_date = '2024-01-01' LIMIT 5"
        tableau_wrapper = f"SELECT * FROM ({custom_query}) `Custom SQL Query`"

        print(f"\n⚠️  Skipping custom SQL test - update query in script first")
        # test_query(conn, "Tableau Custom SQL Wrapper", tableau_wrapper)

        # Summary
        print(f"\n{'='*60}")
        print(f"✅ Test suite completed!")
        print(f"{'='*60}")
        print(f"\nNext steps:")
        print(f"1. Review logs/chronosproxy.log for detailed query processing")
        print(f"2. If all tests passed, try connecting Tableau")
        print(f"3. Monitor for WinError 64 during Tableau connection")

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print(f"\n🔌 Connection closed")


if __name__ == '__main__':
    main()
