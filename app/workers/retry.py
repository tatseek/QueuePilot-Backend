def retry_delay_seconds(attempt_count: int) -> int:
    return 2 ** min(attempt_count, 5)
