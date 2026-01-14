"""
Support Ticket Module.
Ported from Leaddata.

Provides customer support ticket functionality:
- Create and view tickets
- Add notes/comments
- Admin ticket management
- Ticket assignment and status updates
"""

from flask import Blueprint

support_bp = Blueprint('support', __name__)

from app.support import routes
