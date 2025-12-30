"""
Migration 032: Add Storage Usage Fields to Repositories

This migration adds filesystem storage information fields to the repositories
table to track disk space usage and availability.
"""

from sqlalchemy import text

def upgrade(db):
    """Add storage usage fields to repositories table"""
    print("Running migration 032: Add Storage Usage Fields")

    try:
        # Add storage_total field
        db.execute(text("""
            ALTER TABLE repositories
            ADD COLUMN storage_total BIGINT
        """))
        print("✓ Added storage_total column")

        # Add storage_used field
        db.execute(text("""
            ALTER TABLE repositories
            ADD COLUMN storage_used BIGINT
        """))
        print("✓ Added storage_used column")

        # Add storage_available field
        db.execute(text("""
            ALTER TABLE repositories
            ADD COLUMN storage_available BIGINT
        """))
        print("✓ Added storage_available column")

        # Add storage_percent_used field
        db.execute(text("""
            ALTER TABLE repositories
            ADD COLUMN storage_percent_used REAL
        """))
        print("✓ Added storage_percent_used column")

        # Add last_storage_check field
        db.execute(text("""
            ALTER TABLE repositories
            ADD COLUMN last_storage_check TIMESTAMP
        """))
        print("✓ Added last_storage_check column")

        db.commit()
        print("✓ Migration 032 completed successfully")

    except Exception as e:
        print(f"✗ Migration 032 failed: {e}")
        db.rollback()
        raise

def downgrade(db):
    """Downgrade migration 032"""
    print("Running downgrade for migration 032")
    try:
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        # For now, we'll just print a message
        print("! Note: SQLite doesn't support DROP COLUMN. Manual intervention required if needed.")
        db.commit()
        print("✓ Downgrade noted for migration 032")
    except Exception as e:
        print(f"! Error during downgrade: {e}")
        db.rollback()
        raise
