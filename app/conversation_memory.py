from repositories.db_pool import get_connection, release_connection
import json

EXPIRY_MINUTES = 60


def get_state(phone: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT state, updated_at FROM conversation_memory
            WHERE phone = %s
            """,
            (phone,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        state      = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        updated_at = row[1]

        # Check if state has expired
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # Make updated_at timezone-aware if it isn't
        if updated_at.tzinfo is None:
            from datetime import timezone
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        age_minutes = (now - updated_at).total_seconds() / 60

        if age_minutes > EXPIRY_MINUTES:
            # Mark as expired — don't delete yet, let processor ask user
            state["_expired"] = True

        return state

    except Exception as e:
        print("get_state error:", e)
        return None
    finally:
        cursor.close()
        release_connection(conn)


def set_state(phone: str, data: dict):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conversation_memory (phone, state, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (phone)
            DO UPDATE SET state = EXCLUDED.state, updated_at = NOW()
            """,
            (phone, json.dumps(data))
        )
        conn.commit()
    except Exception as e:
        print("set_state error:", e)
        conn.rollback()
    finally:
        cursor.close()
        release_connection(conn)


def clear_state(phone: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM conversation_memory WHERE phone = %s",
            (phone,)
        )
        conn.commit()
    except Exception as e:
        print("clear_state error:", e)
    finally:
        cursor.close()
        release_connection(conn)