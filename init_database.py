#!/usr/bin/env python3
"""
Database initialization and management module for Live Interview App.

This module handles the creation, initialization, validation, and maintenance
of the SQLite database. It reads the schema from `database_schema.sql` and
sets up the necessary tables and relationships. It also provides utility
functions for database backups and statistics.
"""

import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages SQLite database operations for the interview application.

    This class handles the low-level database connection, creation from schema,
    validation, and maintenance tasks like backup and stats collection.
    """
    
    def __init__(self, db_path: str = "db/interview_database.db"):
        """
        Initialize the database manager.
        
        Args:
            db_path (str): Path to the SQLite database file. Defaults to "db/interview_database.db".
        """
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))
        self.db_path = db_path
        self.base_dir = Path(__file__).parent
        self.schema_path = self.base_dir / "database_schema.sql"
        
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection with foreign key enforcement enabled.

        Returns:
            sqlite3.Connection: The database connection object with row factory set to sqlite3.Row.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn
    
    def create_database(self, force_recreate: bool = False) -> bool:
        """
        Create the database and all tables from the schema file.
        
        Args:
            force_recreate (bool): If True, drops the existing database and recreates it. Defaults to False.
            
        Returns:
            bool: True if database creation was successful, False otherwise.
        """
        try:
            # Remove existing database if force_recreate is True
            if force_recreate and os.path.exists(self.db_path):
                os.remove(self.db_path)
                logger.info(f"Removed existing database: {self.db_path}")
            
            # Check if database already exists
            if os.path.exists(self.db_path) and not force_recreate:
                logger.info(f"Database already exists: {self.db_path}")
                return True
            
            # Read schema file
            if not self.schema_path.exists():
                logger.error(f"Schema file not found: {self.schema_path}")
                return False
            
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Create database and execute schema
            with self.get_connection() as conn:
                # Split schema into individual statements and execute
                statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement:
                        try:
                            conn.execute(statement)
                            logger.debug(f"Executed: {statement[:50]}...")
                        except sqlite3.Error as e:
                            logger.error(f"Error executing statement: {e}")
                            logger.error(f"Statement: {statement}")
                            return False
                
                conn.commit()
                logger.info(f"Database created successfully: {self.db_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            return False
    
    def validate_database(self) -> bool:
        """
        Validate that all required tables exist in the database.
        
        Returns:
            bool: True if all required tables exist, False otherwise.
        """
        required_tables = [
            'job_descriptions', 'resumes', 'interviews', 'match_ratings',
            'interview_recordings', 'scoring_analysis', 'final_scores',
            'interview_feedback', 'system_events'
        ]
        
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                existing_tables = [row[0] for row in cursor.fetchall()]
                
                missing_tables = set(required_tables) - set(existing_tables)
                if missing_tables:
                    logger.error(f"Missing tables: {missing_tables}")
                    return False
                
                logger.info("Database validation successful")
                return True
                
        except Exception as e:
            logger.error(f"Error validating database: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the database contents.
        
        Returns:
            Dict[str, Any]: A dictionary containing table counts, recent activity, and file size.
        """
        stats = {}
        
        try:
            with self.get_connection() as conn:
                # Get table counts
                tables = [
                    'job_descriptions', 'resumes', 'interviews', 'match_ratings',
                    'interview_recordings', 'scoring_analysis', 'final_scores',
                    'interview_feedback', 'system_events'
                ]
                
                for table in tables:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats[f"{table}_count"] = count
                
                # Get recent activity
                cursor = conn.execute("""
                    SELECT COUNT(*) as recent_interviews 
                    FROM interviews 
                    WHERE created_at > datetime('now', '-7 days')
                """)
                stats['recent_interviews'] = cursor.fetchone()[0]
                
                # Database file size
                stats['database_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """
        Create a backup of the database file.
        
        Args:
            backup_path (Optional[str]): Custom path for the backup file. If None, generates a timestamped path.
            
        Returns:
            bool: True if backup was successful, False otherwise.
        """
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"db/interview_database_backup_{timestamp}.db"
        
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = None) -> List[sqlite3.Row]:
        """
        Execute a SELECT query and return the results.
        
        Args:
            query (str): The SQL SELECT query.
            params (tuple): Optional parameters for the query.
            
        Returns:
            List[sqlite3.Row]: A list of rows returned by the query.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params or ())
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return []
    
    def execute_update(self, query: str, params: tuple = None) -> bool:
        """
        Execute an INSERT, UPDATE, or DELETE query.
        
        Args:
            query (str): The SQL query to execute.
            params (tuple): Optional parameters for the query.
            
        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        try:
            with self.get_connection() as conn:
                conn.execute(query, params or ())
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error executing update: {e}")
            return False


def main():
    """
    Main function to run the database initialization process.

    Steps:
    1. Create database tables from schema.
    2. Validate database structure.
    3. Display database statistics.
    4. Create an initial backup.

    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    print("=" * 60)
    print("Live Interview App - Database Initialization")
    print("=" * 60)
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Create database
    print("\n1. Creating database...")
    success = db_manager.create_database()
    if success:
        print("✓ Database created successfully")
    else:
        print("✗ Failed to create database")
        return False
    
    # Validate database
    print("\n2. Validating database structure...")
    valid = db_manager.validate_database()
    if valid:
        print("✓ Database validation passed")
    else:
        print("✗ Database validation failed")
        return False
    
    # Show database stats
    print("\n3. Database Statistics:")
    stats = db_manager.get_database_stats()
    for key, value in stats.items():
        print(f"   {key.replace('_', ' ').title()}: {value}")
    
    # Create backup
    print("\n4. Creating initial backup...")
    backup_success = db_manager.backup_database()
    if backup_success:
        print("✓ Backup created successfully")
    else:
        print("✗ Failed to create backup")
    
    print("\n" + "=" * 60)
    print("Database initialization completed successfully!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    main()
