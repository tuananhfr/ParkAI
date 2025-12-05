"""
Database Migration - Thêm columns cho P2P sync
"""
import sqlite3
import os


def migrate_database_for_p2p(db_file: str = "data/central.db"):
    """
    Migrate database để hỗ trợ P2P sync

    Thêm columns:
    - event_id: Unique ID cho mỗi event (format: central-1_timestamp_plate_id)
    - source_central: Central nào tạo event này
    - edge_id: Edge camera nào detect
    - sync_status: LOCAL (tạo ở central này) hoặc SYNCED (nhận từ peer)
    """
    if not os.path.exists(db_file):
        print(f"Database {db_file} not found, skipping migration")
        return

    print(f"🔄 Migrating database for P2P: {db_file}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(history)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add event_id column
        if "event_id" not in columns:
            print("  ➕ Adding column: event_id")
            cursor.execute("ALTER TABLE history ADD COLUMN event_id TEXT")

        # Add source_central column
        if "source_central" not in columns:
            print("  ➕ Adding column: source_central")
            cursor.execute("ALTER TABLE history ADD COLUMN source_central TEXT")

        # Add edge_id column
        if "edge_id" not in columns:
            print("  ➕ Adding column: edge_id")
            cursor.execute("ALTER TABLE history ADD COLUMN edge_id TEXT")

        # Add sync_status column
        if "sync_status" not in columns:
            print("  ➕ Adding column: sync_status")
            cursor.execute("ALTER TABLE history ADD COLUMN sync_status TEXT DEFAULT 'LOCAL'")

        # Create index for event_id
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_event_id
            ON history(event_id)
        """)
        print("  ➕ Created index: idx_history_event_id")

        # Create index for source_central
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_source_central
            ON history(source_central)
        """)
        print("  ➕ Created index: idx_history_source_central")

        # Create index for sync_status
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_sync_status
            ON history(sync_status)
        """)
        print("  ➕ Created index: idx_history_sync_status")

        # Create table for tracking last sync time with peers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS p2p_sync_state (
                peer_central_id TEXT PRIMARY KEY,
                last_sync_timestamp INTEGER NOT NULL,
                last_sync_time TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ➕ Created table: p2p_sync_state")

        conn.commit()
        print("Database migration completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    # Run migration
    migrate_database_for_p2p()
