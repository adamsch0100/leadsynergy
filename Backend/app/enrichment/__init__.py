"""
Enrichment module for lead data enhancement using Endato API.
Ported from Leaddata.

Provides 7 search types:
1. Contact Enrichment - Enhance contact details with additional data
2. Reverse Phone Search - Find person from phone number
3. Reverse Email Search - Find person from email address
4. Criminal History Search - Background check with category filters
5. DNC Checker - Do Not Call registry verification
6. Owner Search - Property owner from address
7. Advanced Person Search - Multi-field comprehensive search
"""

from flask import Blueprint

enrichment_bp = Blueprint('enrichment', __name__)

from app.enrichment import routes
