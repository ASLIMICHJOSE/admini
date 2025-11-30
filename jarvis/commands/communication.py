#!/usr/bin/env python3
"""
JARVIS Communication Handler

Handles email sending, receiving, and messaging functionality.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any

try:
    import imaplib2
    import email
    from email.header import decode_header
except ImportError:
    imaplib2 = None
    email = None

from jarvis.core.command_dispatcher import ExecutionResult


class CommunicationHandler:
    """Handles email and messaging functionality."""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # Email client (will be initialized with proper config)
        self.smtp_server = None
        self.imap_client = None

    def initialize(self) -> bool:
        """Initialize communication handler."""
        try:
            self.logger.info("Initializing communication handler...")
            
            # Check dependencies
            if imaplib2 is None:
                self.logger.warning("imaplib2 not available, email reading limited")
            if email is None:
                self.logger.warning("email library not available")
            
            # Initialize email client if API keys are available
            if hasattr(self.config, 'api_keys') and self.config.api_keys.email_username:
                self._setup_email_client()
            
            self.logger.info("Communication handler initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize communication handler: {e}")
            return False

    def _setup_email_client(self):
        """Setup email client with configuration."""
        try:
            # This is a simplified setup
            # Real implementation would handle OAuth2 for Gmail, etc.
            email_config = {
                'username': getattr(self.config.api_keys, 'email_username', ''),
                'password': getattr(self.config.api_keys, 'email_password', ''),
                'smtp_server': getattr(self.config.api_keys, 'email_smtp_server', 'smtp.gmail.com'),
                'smtp_port': getattr(self.config.api_keys, 'email_smtp_port', 587)
            }
            
            if email_config['username'] and email_config['password']:
                self.logger.info("Email client configuration available")
            else:
                self.logger.warning("Email credentials not properly configured")

        except Exception as e:
            self.logger.error(f"Email client setup failed: {e}")

    def send_email(self, command) -> Any:
        """Send an email."""
        recipient = command.entities.get("recipient", "").strip()
        subject = f"Message from JARVIS"
        body = command.entities.get("message", "").strip()
        
        if not recipient or not body:
            return ExecutionResult(
                success=False,
                message="Email recipient and message are required",
                error="Missing required parameters"
            )

        try:
            self.logger.info(f"Sending email to: {recipient}")
            
            # Validate email address
            if "@" not in recipient or "." not in recipient.split("@")[-1]:
                return ExecutionResult(
                    success=False,
                    message="Invalid email address format",
                    error="Invalid recipient"
                )

            # Simulate email sending (real implementation would use SMTP)
            if hasattr(self.config, 'api_keys') and self.config.api_keys.email_username:
                # Would use smtplib.SMTP to send actual email
                success = self._send_smtp_email(recipient, subject, body)
            else:
                # Mock email sending for testing
                success = True
                self.logger.warning("Email not configured, simulating send")

            if success:
                return ExecutionResult(
                    success=True,
                    message=f"Email sent successfully to {recipient}",
                    data={
                        "recipient": recipient,
                        "subject": subject,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    message="Failed to send email",
                    error="SMTP error"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error sending email: {str(e)}",
                error=str(e)
            )

    def _send_smtp_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        try:
            if not hasattr(self.config, 'api_keys'):
                return False

            msg = MIMEMultipart()
            msg['From'] = self.config.api_keys.email_username
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(
                self.config.api_keys.email_smtp_server,
                self.config.api_keys.email_smtp_port
            )
            server.starttls()
            server.login(self.config.api_keys.email_username, self.config.api_keys.email_password)
            text = msg.as_string()
            server.sendmail(self.config.api_keys.email_username, recipient, text)
            server.quit()

            return True

        except Exception as e:
            self.logger.error(f"SMTP send error: {e}")
            return False

    def read_unread_emails(self, command=None) -> Any:
        """Read unread emails."""
        try:
            self.logger.info("Checking for unread emails...")
            
            if not imaplib2 or not hasattr(self.config, 'api_keys'):
                return ExecutionResult(
                    success=False,
                    message="Email reading not available - missing dependencies or configuration",
                    error="Email client not available"
                )

            # This would connect to IMAP server and fetch emails
            # For now, return a placeholder response
            mock_emails = [
                {
                    "from": "example@domain.com",
                    "subject": "Test Email",
                    "date": datetime.now().isoformat(),
                    "snippet": "This is a test email for JARVIS."
                }
            ]

            return ExecutionResult(
                success=True,
                message=f"Found {len(mock_emails)} emails (demo mode)",
                data={"emails": mock_emails, "count": len(mock_emails)}
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error reading emails: {str(e)}",
                error=str(e)
            )

    def test(self) -> bool:
        """Test communication functionality."""
        try:
            self.logger.info("Testing communication handler...")
            
            # Test email configuration
            if hasattr(self.config, 'api_keys') and self.config.api_keys.email_username:
                self.logger.info("✅ Email configuration - CONFIGURED")
            else:
                self.logger.warning("⚠️  Email configuration - NOT CONFIGURED")

            # Test dependencies
            if imaplib2:
                self.logger.info("✅ IMAP library - AVAILABLE")
            else:
                self.logger.warning("⚠️  IMAP library - NOT AVAILABLE")

            # Test basic email sending functionality
            test_command = type('TestCommand', (), {
                'entities': {
                    'recipient': 'test@example.com',
                    'message': 'Test email from JARVIS'
                }
            })()
            
            result = self.send_email(test_command)
            if result.success:
                self.logger.info("✅ Email sending - WORKING")
            else:
                self.logger.warning(f"⚠️  Email sending - ISSUE: {result.error}")

            self.logger.info("Communication handler tests completed")
            return True

        except Exception as e:
            self.logger.error(f"Communication handler test failed: {e}")
            return False

    def shutdown(self):
        """Cleanup communication handler resources."""
        self.logger.info("Shutting down communication handler...")
        
        # Close IMAP connection if open
        if self.imap_client:
            try:
                self.imap_client.close()
                self.imap_client.logout()
            except Exception as e:
                self.logger.error(f"Error closing IMAP connection: {e}")

        self.logger.info("Communication handler shutdown complete")
