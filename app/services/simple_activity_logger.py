"""
Simple Activity Logger - Updates user_activity table when user is authenticated
"""
from app.db.session import get_db_session
from app.core.logging_config import logger
from sqlalchemy import text
import threading


def log_activity(user_id: str, user_email: str, endpoint: str, name: str = None, provider: str = None):
    """
    Log user activity to database in background thread (non-blocking)
    Called by auth middleware after token verification
    """
    def _log_in_background():
        try:
            with get_db_session() as db:
                db.execute(
                    text("INSERT INTO user_activity (user_id, user_email, name, endpoint, provider) VALUES (:user_id, :user_email, :name, :endpoint, :provider)"),
                    {"user_id": user_id, "user_email": user_email, "name": name, "endpoint": endpoint, "provider": provider}
                )
                db.commit()
        except Exception as e:
            logger.error(f"Activity log failed: {e}")
    
    # Run in background thread - doesn't block API response
    thread = threading.Thread(target=_log_in_background, daemon=True)
    thread.start()
