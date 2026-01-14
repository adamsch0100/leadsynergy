"""
Lead Source Mappings module for managing source aliases and merging duplicates.
"""

from flask import Blueprint

lead_source_mappings_bp = Blueprint('lead_source_mappings', __name__)

from app.lead_source_mappings import routes
