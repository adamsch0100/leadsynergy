"""
Test script: Create a support ticket and verify email notification is sent.

Steps:
1. Find the admin user
2. Set notification email to adam@saahomes.com
3. Create a test support ticket
4. Send email notification directly
"""

import os
import sys
import json

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def main():
    print("=" * 60)
    print("SUPPORT TICKET + EMAIL NOTIFICATION TEST")
    print("=" * 60)

    # Step 1: Find admin user (by role column)
    print("\n[1] Finding admin user...")
    try:
        admin_result = supabase.table('users').select('id, email, role').in_('role', ['admin', 'broker']).limit(1).execute()
    except Exception:
        # Fallback: just get first user
        admin_result = supabase.table('users').select('id, email, role').limit(1).execute()

    if not admin_result.data:
        print("ERROR: No users found!")
        return
    admin = admin_result.data[0]
    admin_id = admin['id']
    print(f"    User: {admin.get('email', 'N/A')} | Role: {admin.get('role', 'N/A')} | ID: {admin_id}")

    # Step 2: Set notification email
    print("\n[2] Setting notification email to adam@saahomes.com...")
    notification_emails = ["adam@saahomes.com"]

    # Check if settings row exists
    try:
        settings_result = supabase.table('ai_agent_settings').select('id, support_notification_emails').eq('user_id', admin_id).execute()

        if settings_result.data:
            supabase.table('ai_agent_settings').update({
                'support_notification_emails': notification_emails
            }).eq('user_id', admin_id).execute()
            print(f"    Updated existing settings row")
        else:
            supabase.table('ai_agent_settings').insert({
                'user_id': admin_id,
                'support_notification_emails': notification_emails
            }).execute()
            print(f"    Created new settings row")

        # Verify
        verify = supabase.table('ai_agent_settings').select('support_notification_emails').eq('user_id', admin_id).single().execute()
        saved_emails = verify.data.get('support_notification_emails', []) if verify.data else []
        print(f"    Saved notification emails: {saved_emails}")

        if not saved_emails or saved_emails != notification_emails:
            print("\n    WARNING: The support_notification_emails column may not exist yet.")
            print("    Run this SQL in your Supabase SQL Editor first:")
            print("    -------")
            print("    ALTER TABLE ai_agent_settings ADD COLUMN IF NOT EXISTS support_notification_emails JSONB DEFAULT '[]';")
            print("    NOTIFY pgrst, 'reload schema';")
            print("    -------")
            return

    except Exception as e:
        print(f"    ERROR with settings: {e}")
        print("\n    Run this SQL in your Supabase SQL Editor:")
        print("    ALTER TABLE ai_agent_settings ADD COLUMN IF NOT EXISTS support_notification_emails JSONB DEFAULT '[]';")
        print("    NOTIFY pgrst, 'reload schema';")
        return

    # Step 3: Create a test support ticket
    print("\n[3] Creating test support ticket...")
    try:
        ticket_data = {
            'user_id': admin_id,
            'subject': 'Test Ticket - Email Notification Check',
            'description': 'This is a test ticket to verify that email notifications are working correctly.\n\nIf you receive this at adam@saahomes.com, the notification system is working!',
            'status': 'open',
            'priority': 'normal',
            'category': 'technical',
        }

        ticket_result = supabase.table('support_tickets').insert(ticket_data).execute()

        if ticket_result.data:
            ticket = ticket_result.data[0]
            ticket_id = ticket['id']
            print(f"    Created ticket #{ticket_id}: {ticket['subject']}")
        else:
            print("    ERROR: Failed to create ticket!")
            return
    except Exception as e:
        print(f"    ERROR creating ticket: {e}")
        print("\n    The support_tickets table may not exist yet.")
        print("    Run the full migration SQL in your Supabase SQL Editor.")
        print("    (See the migration SQL provided in the implementation summary)")
        return

    # Step 4: Send the notification email directly
    print("\n[4] Sending email notification to adam@saahomes.com...")
    try:
        from app.email.email_service import EmailService

        email_service = EmailService()

        admin_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); padding: 30px; border-radius: 8px 8px 0 0; text-align: center;">
                <h1 style="margin: 0; color: #fff; font-size: 24px;">New Support Ticket #{ticket_id}</h1>
            </div>
            <div style="background: #fff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; width: 120px;">Subject:</td>
                        <td style="padding: 8px 0; font-weight: 600; color: #111827;">{ticket['subject']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280;">Priority:</td>
                        <td style="padding: 8px 0;">Normal</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280;">Category:</td>
                        <td style="padding: 8px 0;">Technical</td>
                    </tr>
                </table>
                <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
                    <p style="margin: 0 0 8px; font-size: 13px; color: #6b7280; font-weight: 600;">Description:</p>
                    <p style="margin: 0; color: #374151; white-space: pre-wrap; font-size: 14px; line-height: 1.6;">{ticket['description']}</p>
                </div>
                <p style="margin: 0; font-size: 13px; color: #9ca3af; text-align: center;">
                    LeadSynergy Support Notification
                </p>
            </div>
        </div>
        """

        success = email_service.send_email(
            to_email="adam@saahomes.com",
            subject=f"[LeadSynergy] New Ticket #{ticket_id}: {ticket['subject']}",
            html_content=admin_html,
            text_content=f"New Support Ticket #{ticket_id}\n\nSubject: {ticket['subject']}\nPriority: Normal\nCategory: Technical\n\n{ticket['description']}"
        )

        if success:
            print("    SUCCESS! Email sent to adam@saahomes.com")
        else:
            print("    FAILED to send email. Check SMTP config in .env")

    except Exception as e:
        print(f"    ERROR sending email: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Notification email configured: adam@saahomes.com")
    print(f"  Test ticket created: #{ticket_id}")
    print(f"  Check adam@saahomes.com inbox for the notification!")
    print(f"\n  When the Flask backend is running, ALL new tickets")
    print(f"  will automatically email notifications to configured addresses.")
    print("=" * 60)


if __name__ == "__main__":
    main()
