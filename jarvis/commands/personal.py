#!/usr/bin/env python3
"""
JARVIS Personal Assistant

Handles personal productivity features including reminders,
timers, calendar integration, and task management.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    import schedule
except ImportError:
    schedule = None

try:
    import plyer
except ImportError:
    plyer = None

from config import PrivacyConfig


class TimerStatus(Enum):
    """Timer status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReminderPriority(Enum):
    """Reminder priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Timer:
    """Represents a timer."""
    id: str
    label: str
    duration_minutes: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TimerStatus = TimerStatus.PENDING
    thread: Optional[threading.Thread] = None


@dataclass
class Reminder:
    """Represents a reminder."""
    id: str
    message: str
    due_time: datetime
    created_at: datetime
    priority: ReminderPriority = ReminderPriority.MEDIUM
    is_completed: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    notification_sent: bool = False


class PersonalAssistant:
    """Handles personal productivity features."""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # Data storage
        self.db_path = Path("jarvis_data.db")
        self.backup_path = Path("jarvis_data_backup.json")

        # In-memory data
        self.active_timers: Dict[str, Timer] = {}
        self.pending_reminders: Dict[str, Reminder] = {}
        self.completed_tasks: List[Dict] = []

        # Background processing
        self.running = False
        self.check_thread: Optional[threading.Thread] = None
        self.notification_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Settings
        self.default_priority = ReminderPriority.MEDIUM
        self.notification_enabled = True

    def initialize(self) -> bool:
        """Initialize personal assistant."""
        try:
            self.logger.info("Initializing personal assistant...")

            # Check dependencies
            if schedule is None:
                self.logger.warning("schedule library not available, limited functionality")
            if plyer is None:
                self.logger.warning("plyer library not available, limited notifications")

            # Initialize database
            if not self._init_database():
                return False

            # Load existing data
            self._load_data()

            # Start background processing
            self._start_background_processing()

            self.logger.info("Personal assistant initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize personal assistant: {e}")
            return False

    def _init_database(self) -> bool:
        """Initialize SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create timers table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS timers (
                        id TEXT PRIMARY KEY,
                        label TEXT NOT NULL,
                        duration_minutes INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        status TEXT NOT NULL DEFAULT 'pending'
                    )
                ''')

                # Create reminders table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS reminders (
                        id TEXT PRIMARY KEY,
                        message TEXT NOT NULL,
                        due_time TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        priority TEXT NOT NULL DEFAULT 'medium',
                        is_completed BOOLEAN DEFAULT FALSE,
                        is_recurring BOOLEAN DEFAULT FALSE,
                        recurrence_pattern TEXT,
                        notification_sent BOOLEAN DEFAULT FALSE
                    )
                ''')

                # Create tasks table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT,
                        created_at TEXT NOT NULL,
                        completed BOOLEAN DEFAULT FALSE,
                        completed_at TEXT,
                        priority TEXT DEFAULT 'medium'
                    )
                ''')

                conn.commit()

            self.logger.info("Database initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return False

    def _load_data(self):
        """Load existing data from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Load active timers
                cursor.execute("SELECT * FROM timers WHERE status IN ('pending', 'running')")
                for row in cursor.fetchall():
                    timer = Timer(
                        id=row[0],
                        label=row[1],
                        duration_minutes=row[2],
                        created_at=datetime.fromisoformat(row[3]),
                        started_at=datetime.fromisoformat(row[4]) if row[4] else None,
                        completed_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        status=TimerStatus(row[6])
                    )
                    if timer.status == TimerStatus.RUNNING:
                        # Restart running timer
                        self._restart_timer(timer)
                    else:
                        self.active_timers[timer.id] = timer

                # Load pending reminders
                cursor.execute("""
                    SELECT * FROM reminders 
                    WHERE is_completed = FALSE AND due_time > datetime('now')
                    ORDER BY due_time ASC
                """)
                
                for row in cursor.fetchall():
                    reminder = Reminder(
                        id=row[0],
                        message=row[1],
                        due_time=datetime.fromisoformat(row[2]),
                        created_at=datetime.fromisoformat(row[3]),
                        priority=ReminderPriority(row[4]),
                        is_completed=bool(row[5]),
                        is_recurring=bool(row[6]),
                        recurrence_pattern=row[7],
                        notification_sent=bool(row[8])
                    )
                    self.pending_reminders[reminder.id] = reminder

                # Load completed tasks
                cursor.execute("""
                    SELECT * FROM tasks 
                    WHERE completed = TRUE 
                    ORDER BY completed_at DESC 
                    LIMIT 100
                """)
                
                for row in cursor.fetchall():
                    self.completed_tasks.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "created_at": row[3],
                        "completed_at": row[4],
                        "priority": row[5]
                    })

            self.logger.info(f"Loaded {len(self.active_timers)} timers, {len(self.pending_reminders)} reminders")

        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")

    def _start_background_processing(self):
        """Start background processing thread."""
        self.running = True
        self.stop_event.clear()

        self.check_thread = threading.Thread(
            target=self._background_check_loop,
            name="PersonalAssistantCheck",
            daemon=True
        )
        self.check_thread.start()

        self.notification_thread = threading.Thread(
            target=self._notification_loop,
            name="PersonalAssistantNotification",
            daemon=True
        )
        self.notification_thread.start()

    def _background_check_loop(self):
        """Background loop for checking timers and reminders."""
        while self.running and not self.stop_event.is_set():
            try:
                current_time = datetime.now()

                # Check timers
                for timer_id, timer in list(self.active_timers.items()):
                    if timer.status == TimerStatus.RUNNING:
                        elapsed = (current_time - timer.started_at).total_seconds() / 60
                        if elapsed >= timer.duration_minutes:
                            self._complete_timer(timer_id)

                # Check reminders
                for reminder_id, reminder in list(self.pending_reminders.items()):
                    if not reminder.notification_sent and current_time >= reminder.due_time:
                        self._trigger_reminder(reminder_id)

                # Sleep for 30 seconds
                self.stop_event.wait(30)

            except Exception as e:
                self.logger.error(f"Background check error: {e}")

    def _notification_loop(self):
        """Background loop for handling notifications."""
        notification_queue = []

        while self.running and not self.stop_event.is_set():
            try:
                # Process notification queue (simplified)
                if notification_queue and self.notification_enabled:
                    notification = notification_queue.pop(0)
                    self._send_notification(notification)

                # Sleep for 1 second
                self.stop_event.wait(1)

            except Exception as e:
                self.logger.error(f"Notification loop error: {e}")

    def set_timer(self, command) -> Any:
        """Set a new timer."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        time_value = command.entities.get("time_value")
        time_unit = command.entities.get("time_unit", "minutes").lower()
        label = command.entities.get("label", f"Timer for {time_value} {time_unit}")
        
        if time_value is None:
            return ExecutionResult(
                success=False,
                message="Timer duration is required",
                error="Missing time_value parameter"
            )

        try:
            # Convert to minutes
            if "hour" in time_unit:
                duration_minutes = int(time_value) * 60
            else:  # minutes
                duration_minutes = int(time_value)

            # Validate duration
            if duration_minutes <= 0:
                return ExecutionResult(
                    success=False,
                    message="Timer duration must be positive",
                    error="Invalid timer duration"
                )

            if duration_minutes > 1440:  # 24 hours max
                return ExecutionResult(
                    success=False,
                    message="Timer cannot exceed 24 hours",
                    error="Timer duration too long"
                )

            # Create timer
            timer_id = f"timer_{int(time.time())}"
            timer = Timer(
                id=timer_id,
                label=label,
                duration_minutes=duration_minutes,
                created_at=datetime.now()
            )

            # Save to database
            self._save_timer(timer)

            # Add to active timers
            self.active_timers[timer_id] = timer

            # Start timer
            self._start_timer(timer_id)

            # Format time display
            if duration_minutes >= 60:
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                time_str = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
            else:
                time_str = f"{duration_minutes} minute{'s' if duration_minutes != 1 else ''}"

            return ExecutionResult(
                success=True,
                message=f"Timer set for {time_str}: {label}",
                data={
                    "timer_id": timer_id,
                    "label": label,
                    "duration_minutes": duration_minutes,
                    "time_display": time_str,
                    "created_at": timer.created_at.isoformat()
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error setting timer: {str(e)}",
                error=str(e)
            )

    def _save_timer(self, timer: Timer):
        """Save timer to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO timers (id, label, duration_minutes, created_at, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    timer.id,
                    timer.label,
                    timer.duration_minutes,
                    timer.created_at.isoformat(),
                    timer.status.value
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to save timer: {e}")

    def _start_timer(self, timer_id: str):
        """Start a timer."""
        timer = self.active_timers.get(timer_id)
        if not timer or timer.status != TimerStatus.PENDING:
            return

        timer.status = TimerStatus.RUNNING
        timer.started_at = datetime.now()

        # Create timer thread
        timer.thread = threading.Thread(
            target=self._timer_worker,
            args=(timer_id,),
            name=f"Timer-{timer_id}",
            daemon=True
        )
        timer.thread.start()

        # Update database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE timers SET status = ?, started_at = ? WHERE id = ?
                ''', (
                    timer.status.value,
                    timer.started_at.isoformat(),
                    timer_id
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to update timer status: {e}")

        self.logger.info(f"Started timer: {timer.label}")

    def _timer_worker(self, timer_id: str):
        """Timer worker thread."""
        timer = self.active_timers.get(timer_id)
        if not timer:
            return

        # Wait for duration
        duration_seconds = timer.duration_minutes * 60
        timer.thread.join(timeout=duration_seconds)

        # Complete timer
        if self.running:
            self._complete_timer(timer_id)

    def _complete_timer(self, timer_id: str):
        """Complete a timer."""
        timer = self.active_timers.get(timer_id)
        if not timer or timer.status != TimerStatus.RUNNING:
            return

        timer.status = TimerStatus.COMPLETED
        timer.completed_at = datetime.now()

        # Update database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE timers SET status = ?, completed_at = ? WHERE id = ?
                ''', (
                    timer.status.value,
                    timer.completed_at.isoformat(),
                    timer_id
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to update timer completion: {e}")

        # Send notification
        self._send_notification({
            "type": "timer_completed",
            "title": "Timer Completed",
            "message": f"Timer finished: {timer.label}",
            "timer_id": timer_id
        })

        # Remove from active timers after delay
        def cleanup():
            time.sleep(300)  # Keep in completed state for 5 minutes
            if timer_id in self.active_timers:
                del self.active_timers[timer_id]

        threading.Thread(target=cleanup, daemon=True).start()

        self.logger.info(f"Timer completed: {timer.label}")

    def _restart_timer(self, timer: Timer):
        """Restart a timer that was running."""
        # Calculate elapsed time
        elapsed = (datetime.now() - timer.started_at).total_seconds() / 60
        remaining = max(1, timer.duration_minutes - elapsed)

        timer.duration_minutes = remaining
        timer.status = TimerStatus.PENDING
        timer.started_at = None

        self._start_timer(timer.id)

    def set_reminder(self, command) -> Any:
        """Set a new reminder."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        message = command.entities.get("message", "").strip()
        time_str = command.entities.get("time", "")
        
        if not message:
            return ExecutionResult(
                success=False,
                message="Reminder message is required",
                error="Missing message parameter"
            )

        try:
            # Parse time
            due_time = self._parse_reminder_time(time_str)
            if not due_time:
                return ExecutionResult(
                    success=False,
                    message="Could not parse reminder time",
                    error="Invalid time format"
                )

            # Create reminder
            reminder_id = f"reminder_{int(time.time())}"
            reminder = Reminder(
                id=reminder_id,
                message=message,
                due_time=due_time,
                created_at=datetime.now(),
                priority=self.default_priority
            )

            # Save to database
            self._save_reminder(reminder)

            # Add to pending reminders
            self.pending_reminders[reminder_id] = reminder

            # Format time display
            time_display = due_time.strftime("%I:%M %p on %A, %B %d")
            
            return ExecutionResult(
                success=True,
                message=f"Reminder set for {time_display}: {message}",
                data={
                    "reminder_id": reminder_id,
                    "message": message,
                    "due_time": due_time.isoformat(),
                    "time_display": time_display,
                    "created_at": reminder.created_at.isoformat()
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error setting reminder: {str(e)}",
                error=str(e)
            )

    def _parse_reminder_time(self, time_str: str) -> Optional[datetime]:
        """Parse reminder time string."""
        if not time_str:
            return None

        try:
            current_time = datetime.now()
            time_str = time_str.lower().strip()

            # Handle relative times
            if time_str.startswith("in "):
                time_str = time_str[3:]

            if "minute" in time_str:
                minutes = self._extract_number(time_str)
                if minutes:
                    return current_time + timedelta(minutes=minutes)
            elif "hour" in time_str:
                hours = self._extract_number(time_str)
                if hours:
                    return current_time + timedelta(hours=hours)
            elif "tomorrow" in time_str:
                return current_time.replace(hour=9, minute=0) + timedelta(days=1)
            elif "today" in time_str:
                return current_time.replace(hour=9, minute=0)
            elif time_str in ["morning", "am"]:
                return current_time.replace(hour=9, minute=0)
            elif time_str in ["afternoon", "pm", "evening"]:
                return current_time.replace(hour=17, minute=0)
            elif time_str == "tonight":
                return current_time.replace(hour=20, minute=0)

            # Try to parse as specific time
            time_formats = ["%I:%M %p", "%H:%M", "%I %p"]
            for fmt in time_formats:
                try:
                    parsed_time = datetime.strptime(time_str, fmt).time()
                    combined = current_time.replace(
                        hour=parsed_time.hour,
                        minute=parsed_time.minute,
                        second=parsed_time.second
                    )
                    
                    # If time is in the past, assume tomorrow
                    if combined <= current_time:
                        combined += timedelta(days=1)
                    
                    return combined
                except ValueError:
                    continue

        except Exception as e:
            self.logger.error(f"Time parsing error: {e}")

        return None

    def _extract_number(self, text: str) -> Optional[int]:
        """Extract a number from text."""
        import re
        match = re.search(r'\d+', text)
        return int(match.group()) if match else None

    def _save_reminder(self, reminder: Reminder):
        """Save reminder to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO reminders (
                        id, message, due_time, created_at, priority, 
                        is_completed, is_recurring
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reminder.id,
                    reminder.message,
                    reminder.due_time.isoformat(),
                    reminder.created_at.isoformat(),
                    reminder.priority.value,
                    reminder.is_completed,
                    reminder.is_recurring
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to save reminder: {e}")

    def _trigger_reminder(self, reminder_id: str):
        """Trigger a reminder."""
        reminder = self.pending_reminders.get(reminder_id)
        if not reminder:
            return

        # Mark as triggered
        reminder.notification_sent = True

        # Update database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE reminders SET notification_sent = TRUE WHERE id = ?
                ''', (reminder_id,))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to update reminder: {e}")

        # Send notification
        self._send_notification({
            "type": "reminder",
            "title": "Reminder",
            "message": reminder.message,
            "reminder_id": reminder_id,
            "priority": reminder.priority.value
        })

        self.logger.info(f"Reminder triggered: {reminder.message}")

        # Handle recurring reminders
        if reminder.is_recurring and reminder.recurrence_pattern:
            self._handle_recurring_reminder(reminder)

        # Remove from pending reminders after delay
        def cleanup():
            time.sleep(300)  # Keep for 5 minutes
            if reminder_id in self.pending_reminders:
                del self.pending_reminders[reminder_id]

        threading.Thread(target=cleanup, daemon=True).start()

    def _handle_recurring_reminder(self, reminder: Reminder):
        """Handle recurring reminder."""
        try:
            # Calculate next occurrence based on pattern
            next_time = None
            
            if "daily" in reminder.recurrence_pattern:
                next_time = reminder.due_time + timedelta(days=1)
            elif "weekly" in reminder.recurrence_pattern:
                next_time = reminder.due_time + timedelta(weeks=1)
            elif "monthly" in reminder.recurrence_pattern:
                next_time = reminder.due_time + timedelta(days=30)

            if next_time and next_time > datetime.now():
                # Create new reminder instance
                new_id = f"reminder_{int(time.time())}"
                new_reminder = Reminder(
                    id=new_id,
                    message=reminder.message,
                    due_time=next_time,
                    created_at=datetime.now(),
                    priority=reminder.priority,
                    is_recurring=True,
                    recurrence_pattern=reminder.recurrence_pattern
                )

                self._save_reminder(new_reminder)
                self.pending_reminders[new_id] = new_reminder

        except Exception as e:
            self.logger.error(f"Failed to handle recurring reminder: {e}")

    def _send_notification(self, notification: Dict):
        """Send a notification."""
        try:
            if self.notification_enabled and plyer:
                plyer.notification.notify(
                    title=notification.get("title", "JARVIS"),
                    message=notification.get("message", ""),
                    timeout=10
                )

            # Log notification
            self.logger.info(f"Notification sent: {notification}")

        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")

    def get_active_timers(self, command=None) -> Any:
        """Get list of active timers."""
        from jarvis.core.command_dispatcher import ExecutionResult

        try:
            active_list = []
            current_time = datetime.now()

            for timer_id, timer in self.active_timers.items():
                if timer.status == TimerStatus.RUNNING:
                    elapsed = (current_time - timer.started_at).total_seconds() / 60
                    remaining = max(0, timer.duration_minutes - elapsed)
                    
                    active_list.append({
                        "id": timer_id,
                        "label": timer.label,
                        "duration_minutes": timer.duration_minutes,
                        "elapsed_minutes": round(elapsed, 1),
                        "remaining_minutes": round(remaining, 1),
                        "started_at": timer.started_at.isoformat(),
                        "progress": min(100, (elapsed / timer.duration_minutes) * 100)
                    })

            return ExecutionResult(
                success=True,
                message=f"Found {len(active_list)} active timer{'s' if len(active_list) != 1 else ''}",
                data={
                    "active_timers": active_list,
                    "total_active": len(active_list)
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting timers: {str(e)}",
                error=str(e)
            )

    def get_pending_reminders(self, command=None) -> Any:
        """Get list of pending reminders."""
        from jarvis.core.command_dispatcher import ExecutionResult

        try:
            pending_list = []
            current_time = datetime.now()

            for reminder_id, reminder in self.pending_reminders.items():
                if not reminder.is_completed:
                    minutes_until = (reminder.due_time - current_time).total_seconds() / 60
                    
                    pending_list.append({
                        "id": reminder_id,
                        "message": reminder.message,
                        "due_time": reminder.due_time.isoformat(),
                        "priority": reminder.priority.value,
                        "minutes_until": round(minutes_until, 1),
                        "is_recurring": reminder.is_recurring,
                        "notification_sent": reminder.notification_sent
                    })

            # Sort by due time
            pending_list.sort(key=lambda r: r["due_time"])

            return ExecutionResult(
                success=True,
                message=f"Found {len(pending_list)} pending reminder{'s' if len(pending_list) != 1 else ''}",
                data={
                    "pending_reminders": pending_list,
                    "total_pending": len(pending_list)
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting reminders: {str(e)}",
                error=str(e)
            )

    def test(self) -> bool:
        """Test personal assistant functionality."""
        try:
            self.logger.info("Testing personal assistant...")

            # Test basic functionality
            test_commands = [
                ("get_active_timers", "Test getting active timers"),
                ("get_pending_reminders", "Test getting pending reminders")
            ]

            for method_name, description in test_commands:
                try:
                    method = getattr(self, method_name)
                    result = method(None)
                    
                    if result.success:
                        self.logger.info(f"✅ {description} - PASSED")
                    else:
                        self.logger.error(f"❌ {description} - FAILED: {result.error}")
                        return False
                        
                except Exception as e:
                    self.logger.error(f"❌ {description} - ERROR: {e}")
                    return False

            # Test dependencies
            if schedule:
                self.logger.info("✅ Schedule library - AVAILABLE")
            else:
                self.logger.warning("⚠️  Schedule library - NOT AVAILABLE")

            if plyer:
                self.logger.info("✅ Plyer library - AVAILABLE")
            else:
                self.logger.warning("⚠️  Plyer library - NOT AVAILABLE")

            self.logger.info("Personal assistant tests completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Personal assistant test failed: {e}")
            return False

    def shutdown(self):
        """Shutdown personal assistant."""
        self.logger.info("Shutting down personal assistant...")

        # Stop background threads
        self.running = False
        self.stop_event.set()

        if self.check_thread and self.check_thread.is_alive():
            self.check_thread.join(timeout=5)

        if self.notification_thread and self.notification_thread.is_alive():
            self.notification_thread.join(timeout=5)

        # Complete running timers
        for timer_id, timer in self.active_timers.items():
            if timer.status == TimerStatus.RUNNING:
                self._complete_timer(timer_id)

        # Backup data
        self._backup_data()

        self.logger.info("Personal assistant shutdown complete")

    def _backup_data(self):
        """Backup data to JSON file."""
        try:
            backup_data = {
                "timers": {
                    timer_id: {
                        "label": timer.label,
                        "duration_minutes": timer.duration_minutes,
                        "created_at": timer.created_at.isoformat(),
                        "started_at": timer.started_at.isoformat() if timer.started_at else None,
                        "completed_at": timer.completed_at.isoformat() if timer.completed_at else None,
                        "status": timer.status.value
                    }
                    for timer_id, timer in self.active_timers.items()
                },
                "reminders": {
                    reminder_id: {
                        "message": reminder.message,
                        "due_time": reminder.due_time.isoformat(),
                        "created_at": reminder.created_at.isoformat(),
                        "priority": reminder.priority.value,
                        "is_completed": reminder.is_completed,
                        "is_recurring": reminder.is_recurring,
                        "recurrence_pattern": reminder.recurrence_pattern
                    }
                    for reminder_id, reminder in self.pending_reminders.items()
                },
                "completed_tasks": self.completed_tasks[-50:],  # Last 50 tasks
                "backup_timestamp": datetime.now().isoformat()
            }

            with open(self.backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)

            self.logger.info("Data backup completed")

        except Exception as e:
            self.logger.error(f"Failed to backup data: {e}")
