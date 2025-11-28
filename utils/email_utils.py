"""
Email Utility.

This module provides functionality to send emails using SMTP (specifically configured for Gmail).
It handles constructing the email message with subject, body, and recipients, and sending it
securely via SSL.
"""

import smtplib
import os
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

subject = "Test Email"
body = "This is the body of the text message"
recipients = ["himanshugohil234@gmail.com"]


def send_email(subject, body, recipients):
    """
    Send an email using SMTP.

    Args:
        subject (str): Subject of the email.
        body (str): Body of the email.
        recipients (list): List of recipient email addresses.

    Returns:
        dict: A dictionary with the status code and message.
              {"statusCode": 200, "body": "Email sent successfully!"} on success,
              {"statusCode": 500, "body": "Error sending email: ..."} on failure.
    """
    sender = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    # Create a MIMEText object with the body of the email.
    msg = MIMEText(body)
    # Set the subject of the email.
    msg["Subject"] = subject
    # Set the sender's email.
    msg["From"] = sender
    # Join the list of recipients into a single string separated by commas.
    msg["To"] = ", ".join(recipients)

    # Connect to Gmail's SMTP server using SSL.
    try:
        with smtplib.SMTP_SSL(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT")) as smtp_server:
            # Login to the SMTP server using the sender's credentials.
            smtp_server.login(sender, password)
            # Send the email. The sendmail function requires the sender's email, the list of recipients, and the email message as a string.
            smtp_server.sendmail(sender, recipients, msg.as_string())
            print("Email sent successfully!")
            return {
                "statusCode": 200,
                "body": "Email sent successfully!",
            }
    except Exception as e:
        print(f"Error sending email: {e}")
        return {
            "statusCode": 500,
            "body": f"Error sending email: {e}",
        }


# send_email(subject, body, recipients)
