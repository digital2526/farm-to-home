from pathlib import Path
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_FROM,
    ADMIN_EMAIL,
)


TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "emails"
)


class EmailService:

    @staticmethod
    def load_template(
        filename: str,
        context: dict,
    ) -> str:
        """
        Load an HTML template and replace placeholders.
        """

        template_path = TEMPLATE_DIR / filename

        html = template_path.read_text(
            encoding="utf-8"
        )

        for key, value in context.items():
            html = html.replace(
                "{{ " + key + " }}",
                str(value),
            )

        return html

    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """
        Send an HTML email using Google Workspace SMTP.
        """

        message = MIMEMultipart("alternative")

        message["From"] = SMTP_FROM
        message["To"] = to_email
        message["Subject"] = subject

        message.attach(
            MIMEText(
                html_body,
                "html",
            )
        )

        try:

            with smtplib.SMTP(
                SMTP_HOST,
                SMTP_PORT,
            ) as server:

                server.starttls()

                server.login(
                    SMTP_USERNAME,
                    SMTP_PASSWORD,
                )

                server.send_message(message)

            return True

        except Exception:


            return False

    @staticmethod
    def send_customer_reward_email(
        customer,
        reward,
    ) -> bool:
        """
        Send reward confirmation email to the customer.
        """

        context = {
            "customer_name": customer.email,
            "reward_name": reward.name,
            "reward_description": reward.description,
            "reward_cost": reward.seed_cost,
            "remaining_balance": customer.current_balance,
        }

        html = EmailService.load_template(
            "customer_reward.html",
            context,
        )

        return EmailService.send_email(
            to_email=customer.email,
            subject=f"🌱 Your Terramay Reward - {reward.name}",
            html_body=html,
        )

    @staticmethod
    def send_admin_reward_email(
        customer,
        reward,
    ) -> bool:
        """
        Send reward redemption notification to Terramay admin.
        """

        admin_actions = {
            "We plant a tree":
                "Plant one tree and send photos to the customer.",

            "Community spotlight":
                "Marketing team should contact the customer.",

            "Free week of The Weekly":
                "Credit one complimentary Recharge subscription.",

            "Private farm tour & lunch":
                "Contact the customer and arrange the farm visit.",

            "Free Bread":
                "Include one complimentary bread with the customer's next order.",

            "Free Soup":
                "Include one complimentary soup with the customer's next order.",
        }

        context = {
            "customer_name": customer.email,
            "customer_email": customer.email,
            "reward_name": reward.name,
            "reward_description": reward.description,
            "reward_cost": reward.seed_cost,
            "remaining_balance": customer.current_balance,
            "admin_action": admin_actions.get(
                reward.name,
                "Review this redemption manually.",
            ),
        }

        html = EmailService.load_template(
            "admin_reward.html",
            context,
        )

        return EmailService.send_email(
            to_email=ADMIN_EMAIL,
            subject=f"🎁 Reward Redeemed - {reward.name}",
            html_body=html,
        )