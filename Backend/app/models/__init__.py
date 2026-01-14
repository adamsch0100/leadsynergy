"""
Models package for ReferralLink + Leaddata unified platform.
"""

from app.models.base_model import BaseModel
from app.models.user import User, UserProfile
from app.models.lead import Lead
from app.models.lead_source_settings import LeadSourceSettings
from app.models.stage_mapping import StageMapping
from app.models.commission_submission import CommissionSubmission
from app.models.activity import Activity
from app.models.reminder import Reminder
from app.models.settings import Settings
from app.models.system_settings import SystemSettings
from app.models.organization import Organization
from app.models.organization_user import OrganizationUser
from app.models.team_member import TeamMember
from app.models.subscription import Subscription
from app.models.notification_settings import NotificationSettings
from app.models.webhook_event import WebhookEvent
from app.models.fub import FUBStage, FUBPipeline

# Leaddata integration models
from app.models.credit_bundle import CreditBundle
from app.models.credit_transaction import CreditTransaction
from app.models.support_ticket import SupportTicket, TicketNote
from app.models.lookup_history import LookupHistory

__all__ = [
    # Base
    'BaseModel',

    # User models
    'User',
    'UserProfile',

    # Lead models
    'Lead',
    'LeadSourceSettings',
    'StageMapping',

    # Business models
    'CommissionSubmission',
    'Activity',
    'Reminder',

    # Settings
    'Settings',
    'SystemSettings',
    'NotificationSettings',

    # Organization models
    'Organization',
    'OrganizationUser',
    'TeamMember',

    # Subscription
    'Subscription',

    # Webhooks
    'WebhookEvent',

    # FUB models
    'FUBStage',
    'FUBPipeline',

    # Leaddata integration models
    'CreditBundle',
    'CreditTransaction',
    'SupportTicket',
    'TicketNote',
    'LookupHistory',
]
