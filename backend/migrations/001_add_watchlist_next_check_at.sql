ALTER TABLE watchlist ADD COLUMN next_check_at DATETIME;
ALTER TABLE watchlist ADD COLUMN last_error TEXT;

UPDATE watchlist
SET next_check_at = COALESCE(last_checked_at, created_at, CURRENT_TIMESTAMP)
WHERE next_check_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_watchlist_next_check_at ON watchlist (next_check_at);
