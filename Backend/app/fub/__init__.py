"""
FUB (Follow Up Boss) Embedded App Module.
LeadSynergy - Combined from ReferralLink and Leaddata.

Provides the embedded app interface for FUB users to:
- Accept terms and conditions
- Perform all 7 enrichment search types
- View search results as FUB notes
- View referral source information
- Update lead status on referral platforms
- Log commissions for closed deals
"""

from flask import Blueprint

fub_bp = Blueprint('fub', __name__)

from app.fub import routes
from app.fub.note_generators import generate_note_for_search
from app.fub.note_service import (
    FUBNoteService,
    FUBNoteServiceSingleton,
    get_note_service,
    post_enrichment_note_to_fub,
    add_enrichment_contact_data
)
from app.fub.referral_actions import (
    ReferralActionsService,
    ReferralActionsServiceSingleton,
    get_referral_actions_service,
    PLATFORM_STATUS_OPTIONS
)
