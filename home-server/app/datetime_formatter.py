"""Datetime formatting utilities for user-friendly output."""

from datetime import datetime, timezone


def format_datetime_for_logs(dt: datetime | None = None) -> str:
    """
    Format a datetime as 'DD/MM/YYYY HH:MM AM/PM' for logs and user output.
    Omits seconds and milliseconds for cleaner output.
    
    Args:
        dt: datetime object (defaults to now in UTC if None)
    
    Returns:
        Formatted string like '13/04/2026 02:30 PM'
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return dt.strftime("%d/%m/%Y %I:%M %p")


def format_date_only(dt: datetime | None = None) -> str:
    """
    Format a datetime as 'DD/MM/YYYY' for date-only output.
    
    Args:
        dt: datetime object (defaults to now in UTC if None)
    
    Returns:
        Formatted string like '13/04/2026'
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return dt.strftime("%d/%m/%Y")


def format_time_only(dt: datetime | None = None) -> str:
    """
    Format a datetime as 'HH:MM AM/PM' for time-only output.
    
    Args:
        dt: datetime object (defaults to now in UTC if None)
    
    Returns:
        Formatted string like '02:30 PM'
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return dt.strftime("%I:%M %p")
