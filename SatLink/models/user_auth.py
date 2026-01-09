"""
SatLink User Authentication System

This module implements user registration, login, and session management
for the SatLink web interface.
"""

import sqlite3
import hashlib
import secrets
import datetime
from typing import Optional, Dict, List


class UserAuth:
    """
    User Authentication System

    Handles user registration, login, session management, and password hashing.
    """

    def __init__(self, db_path: str = 'satlink.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database with users table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            conn.commit()

    def hash_password(self, password: str, salt: str = None) -> tuple:
        """
        Hash password with salt

        Parameters
        ----------
        password : str
            Plain text password
        salt : str, optional
            Salt to use. If None, generates new salt

        Returns
        -------
        tuple
            (password_hash, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        # Combine password and salt, then hash
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # Number of iterations
        )
        return password_hash.hex(), salt

    def register_user(self, username: str, email: str, password: str) -> bool:
        """
        Register a new user

        Parameters
        ----------
        username : str
            Username (must be unique)
        email : str
            Email address (must be unique)
        password : str
            Plain text password

        Returns
        -------
        bool
            True if registration successful, False otherwise
        """
        password_hash, salt = self.hash_password(password)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, salt)
                    VALUES (?, ?, ?, ?)
                """, (username, email, password_hash, salt))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Username or email already exists
                return False

    def authenticate_user(self, username: str, password: str) -> Optional[int]:
        """
        Authenticate user credentials

        Parameters
        ----------
        username : str
            Username or email
        password : str
            Plain text password

        Returns
        -------
        int or None
            User ID if authentication successful, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, password_hash, salt FROM users
                WHERE username = ? OR email = ?
            """, (username, username))

            row = cursor.fetchone()
            if not row:
                return None

            user_id, stored_hash, salt = row
            password_hash, _ = self.hash_password(password, salt)

            if password_hash == stored_hash:
                return user_id
            else:
                return None

    def create_session(self, user_id: int) -> str:
        """
        Create a new session for user

        Parameters
        ----------
        user_id : int
            User ID

        Returns
        -------
        str
            Session token
        """
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.now() + datetime.timedelta(days=30)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, session_token, expires_at))
            conn.commit()

        return session_token

    def validate_session(self, session_token: str) -> Optional[int]:
        """
        Validate session token

        Parameters
        ----------
        session_token : str
            Session token to validate

        Returns
        -------
        int or None
            User ID if session is valid, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM user_sessions
                WHERE session_token = ? AND expires_at > ?
            """, (session_token, datetime.datetime.now()))

            row = cursor.fetchone()
            return row[0] if row else None

    def logout_user(self, session_token: str):
        """
        Remove session (logout)

        Parameters
        ----------
        session_token : str
            Session token to remove
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_sessions WHERE session_token = ?
            """, (session_token,))
            conn.commit()

    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """
        Get user information

        Parameters
        ----------
        user_id : int
            User ID

        Returns
        -------
        dict or None
            User information if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, email, created_at FROM users
                WHERE id = ? AND is_active = 1
            """, (user_id,))

            row = cursor.fetchone()
            return dict(row) if row else None


# Test the user authentication system
if __name__ == "__main__":
    print("Testing User Authentication System")
    print("=" * 50)

    # Create user authentication instance
    auth = UserAuth('test_auth.db')

    # Test registration
    print("1. Testing registration...")
    result = auth.register_user('testuser', 'test@example.com', 'password123')
    print(f"Registration result: {result}")

    # Test duplicate registration
    result = auth.register_user('testuser', 'another@example.com', 'password123')
    print(f"Duplicate registration result: {result}")

    # Test authentication
    print("\n2. Testing authentication...")
    user_id = auth.authenticate_user('testuser', 'password123')
    print(f"Authentication result: {user_id}")

    # Test wrong password
    user_id = auth.authenticate_user('testuser', 'wrongpassword')
    print(f"Wrong password authentication result: {user_id}")

    # Test session creation
    print("\n3. Testing session management...")
    if user_id:
        session_token = auth.create_session(user_id)
        print(f"Session token created: {session_token[:10]}...")

        # Validate session
        validated_user_id = auth.validate_session(session_token)
        print(f"Session validation result: {validated_user_id}")

        # Logout
        auth.logout_user(session_token)
        validated_user_id = auth.validate_session(session_token)
        print(f"Session after logout: {validated_user_id}")

    print("\n4. Getting user info...")
    user_id = auth.authenticate_user('testuser', 'password123')
    if user_id:
        user_info = auth.get_user_info(user_id)
        print(f"User info: {user_info}")

    print("\nTest completed successfully!")