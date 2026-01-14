"""
FUB Note Generators - Rich HTML notes for FUB contacts.

Generates formatted HTML notes for each enrichment search type:
- Contact Enrichment
- Criminal History
- DNC Check
- Reverse Phone
- Reverse Email
- Owner Search
- Person Search
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk assessment levels for criminal history."""
    GREEN = "green"    # No records found
    YELLOW = "yellow"  # Minor records or older offenses
    RED = "red"        # Serious offenses or recent activity


# =============================================================================
# Common Note Styles
# =============================================================================

NOTE_STYLES = """
<style>
    .leadsynergy-note {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 13px;
        line-height: 1.5;
        color: #333;
    }
    .note-header {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 8px 8px 0 0;
        margin-bottom: 0;
    }
    .note-header h3 {
        margin: 0;
        font-size: 15px;
        font-weight: 600;
    }
    .note-header .subtitle {
        font-size: 12px;
        opacity: 0.9;
        margin-top: 4px;
    }
    .note-body {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 16px;
    }
    .section {
        margin-bottom: 16px;
    }
    .section:last-child {
        margin-bottom: 0;
    }
    .section-title {
        font-size: 12px;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .data-row {
        display: flex;
        padding: 6px 0;
        border-bottom: 1px solid #e5e7eb;
    }
    .data-row:last-child {
        border-bottom: none;
    }
    .data-label {
        font-weight: 500;
        color: #374151;
        width: 120px;
        flex-shrink: 0;
    }
    .data-value {
        color: #111827;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-green {
        background: #d1fae5;
        color: #065f46;
    }
    .badge-yellow {
        background: #fef3c7;
        color: #92400e;
    }
    .badge-red {
        background: #fee2e2;
        color: #991b1b;
    }
    .badge-blue {
        background: #dbeafe;
        color: #1e40af;
    }
    .badge-gray {
        background: #f3f4f6;
        color: #374151;
    }
    .phone-item, .email-item, .address-item {
        padding: 8px 12px;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        margin-bottom: 6px;
    }
    .phone-item:last-child, .email-item:last-child, .address-item:last-child {
        margin-bottom: 0;
    }
    .phone-type, .email-type {
        font-size: 10px;
        color: #6b7280;
        text-transform: uppercase;
    }
    .phone-number, .email-address {
        font-weight: 500;
        color: #111827;
    }
    .warning-box {
        background: #fef3c7;
        border: 1px solid #f59e0b;
        border-radius: 6px;
        padding: 12px;
        margin-top: 12px;
    }
    .warning-box .warning-icon {
        color: #f59e0b;
        font-weight: bold;
    }
    .danger-box {
        background: #fee2e2;
        border: 1px solid #ef4444;
        border-radius: 6px;
        padding: 12px;
        margin-top: 12px;
    }
    .success-box {
        background: #d1fae5;
        border: 1px solid #10b981;
        border-radius: 6px;
        padding: 12px;
        margin-top: 12px;
    }
    .offense-item {
        background: white;
        border: 1px solid #e5e7eb;
        border-left: 4px solid #ef4444;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .offense-title {
        font-weight: 600;
        color: #111827;
    }
    .offense-details {
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
    }
    .person-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .person-name {
        font-weight: 600;
        color: #111827;
        font-size: 14px;
    }
    .person-details {
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
    }
    .note-footer {
        margin-top: 16px;
        padding-top: 12px;
        border-top: 1px solid #e5e7eb;
        font-size: 11px;
        color: #9ca3af;
        text-align: center;
    }
    .disclaimer {
        font-size: 11px;
        color: #6b7280;
        font-style: italic;
        margin-top: 12px;
        padding: 8px;
        background: #f9fafb;
        border-radius: 4px;
    }
</style>
"""


# =============================================================================
# Note Generator Functions
# =============================================================================

def generate_contact_enrichment_note(data: Dict[str, Any], searched_criteria: Dict[str, Any] = None) -> str:
    """
    Generate HTML note for contact enrichment results.

    Args:
        data: The enrichment result data
        searched_criteria: The original search criteria

    Returns:
        Formatted HTML string
    """
    if not data or 'error' in data:
        return _generate_error_note("Contact Enrichment", data.get('error', {}).get('message', 'Search failed'))

    # Extract person data
    person = data.get('person', data)
    name_data = person.get('name', {})

    full_name = _format_name(name_data)
    age = person.get('age', 'Unknown')
    phones = person.get('phones', [])
    emails = person.get('emails', [])
    addresses = person.get('addresses', [])

    # Build phones section
    phones_html = ""
    if phones:
        phones_html = '<div class="section"><div class="section-title">Phone Numbers</div>'
        for phone in phones[:5]:  # Limit to 5
            phone_type = phone.get('type', 'Unknown').title()
            phone_number = phone.get('number', phone.get('phone', 'N/A'))
            is_mobile = phone.get('isMobile', False)
            phones_html += f'''
                <div class="phone-item">
                    <div class="phone-type">{phone_type} {'(Mobile)' if is_mobile else ''}</div>
                    <div class="phone-number">{phone_number}</div>
                </div>
            '''
        phones_html += '</div>'

    # Build emails section
    emails_html = ""
    if emails:
        emails_html = '<div class="section"><div class="section-title">Email Addresses</div>'
        for email in emails[:5]:  # Limit to 5
            email_addr = email.get('email', email) if isinstance(email, dict) else email
            email_type = email.get('type', 'Personal') if isinstance(email, dict) else 'Personal'
            emails_html += f'''
                <div class="email-item">
                    <div class="email-type">{email_type}</div>
                    <div class="email-address">{email_addr}</div>
                </div>
            '''
        emails_html += '</div>'

    # Build addresses section
    addresses_html = ""
    if addresses:
        addresses_html = '<div class="section"><div class="section-title">Addresses</div>'
        for addr in addresses[:3]:  # Limit to 3
            addr_str = _format_address(addr)
            addr_type = addr.get('type', 'Current') if isinstance(addr, dict) else 'Current'
            addresses_html += f'''
                <div class="address-item">
                    <div class="phone-type">{addr_type}</div>
                    <div class="data-value">{addr_str}</div>
                </div>
            '''
        addresses_html += '</div>'

    # Summary stats
    summary = f"{len(phones)} phones, {len(emails)} emails, {len(addresses)} addresses found"

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>Contact Enrichment Results</h3>
            <div class="subtitle">{full_name} - Age {age}</div>
        </div>
        <div class="note-body">
            <div class="section">
                <span class="badge badge-blue">{summary}</span>
            </div>

            {phones_html}
            {emails_html}
            {addresses_html}

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


def generate_criminal_history_note(data: Dict[str, Any], searched_name: str = None) -> str:
    """
    Generate HTML note for criminal history search results.

    Args:
        data: The criminal search result data
        searched_name: The name that was searched

    Returns:
        Formatted HTML string with risk badge
    """
    if not data or 'error' in data:
        return _generate_error_note("Criminal History", data.get('error', {}).get('message', 'Search failed'))

    # Assess risk level
    records = data.get('records', data.get('offenses', []))
    risk_level, risk_summary = _assess_criminal_risk(records)

    # Build risk badge
    badge_class = f"badge-{risk_level.value}"
    risk_labels = {
        RiskLevel.GREEN: "NO RECORDS FOUND",
        RiskLevel.YELLOW: "RECORDS FOUND - REVIEW",
        RiskLevel.RED: "SIGNIFICANT RECORDS"
    }

    # Build offenses section
    offenses_html = ""
    if records:
        offenses_html = '<div class="section"><div class="section-title">Records Found</div>'
        for record in records[:10]:  # Limit to 10
            offense_type = record.get('offenseType', record.get('type', 'Unknown'))
            offense_date = record.get('offenseDate', record.get('date', 'Unknown'))
            jurisdiction = record.get('jurisdiction', record.get('state', 'Unknown'))
            disposition = record.get('disposition', 'Unknown')

            offenses_html += f'''
                <div class="offense-item">
                    <div class="offense-title">{offense_type}</div>
                    <div class="offense-details">
                        Date: {offense_date} | Jurisdiction: {jurisdiction} | Disposition: {disposition}
                    </div>
                </div>
            '''
        offenses_html += '</div>'

    # Result box based on risk
    result_box = ""
    if risk_level == RiskLevel.GREEN:
        result_box = '''
            <div class="success-box">
                <strong>No Criminal Records Found</strong><br>
                No criminal history was found in our database search.
            </div>
        '''
    elif risk_level == RiskLevel.YELLOW:
        result_box = f'''
            <div class="warning-box">
                <span class="warning-icon">!</span> <strong>Records Found - Manual Review Recommended</strong><br>
                {risk_summary}
            </div>
        '''
    else:
        result_box = f'''
            <div class="danger-box">
                <strong>Significant Records Found</strong><br>
                {risk_summary}
            </div>
        '''

    name_display = searched_name or "Subject"

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>Criminal History Search</h3>
            <div class="subtitle">{name_display}</div>
        </div>
        <div class="note-body">
            <div class="section">
                <span class="badge {badge_class}">{risk_labels[risk_level]}</span>
            </div>

            {result_box}
            {offenses_html}

            <div class="disclaimer">
                <strong>FCRA Disclaimer:</strong> This information is provided for informational purposes only.
                Criminal background information should not be used as the sole basis for any adverse action.
                Always verify information through official channels and comply with all applicable laws.
            </div>

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


def generate_dnc_note(data: Dict[str, Any], phone: str = None) -> str:
    """
    Generate HTML note for DNC check results.

    Args:
        data: The DNC check result data
        phone: The phone number that was checked

    Returns:
        Formatted HTML string with compliance guidance
    """
    if not data or 'error' in data:
        return _generate_error_note("DNC Check", data.get('error', {}).get('message', 'Check failed'))

    # Determine DNC status
    is_dnc = data.get('isDNC', data.get('onDNC', data.get('dnc', False)))
    is_cell = data.get('isCell', data.get('isMobile', False))
    line_type = data.get('lineType', data.get('type', 'Unknown'))
    carrier = data.get('carrier', 'Unknown')

    phone_display = phone or data.get('phone', 'N/A')

    # Build status badge and box
    if is_dnc:
        badge_html = '<span class="badge badge-red">ON DO NOT CALL LIST</span>'
        status_box = '''
            <div class="danger-box">
                <strong>DO NOT CALL</strong><br>
                This number is registered on the National Do Not Call Registry.
                Calling this number may result in regulatory penalties.
            </div>
        '''
    else:
        badge_html = '<span class="badge badge-green">SAFE TO CALL</span>'
        status_box = '''
            <div class="success-box">
                <strong>Safe to Contact</strong><br>
                This number is not on the National Do Not Call Registry.
            </div>
        '''

    # TCPA warning for cell phones
    tcpa_warning = ""
    if is_cell:
        tcpa_warning = '''
            <div class="warning-box">
                <span class="warning-icon">!</span> <strong>TCPA Notice - Mobile Number</strong><br>
                This is a mobile phone. Under TCPA regulations, you must have prior express written consent
                before sending automated text messages or making autodialed calls to mobile phones.
            </div>
        '''

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>DNC Compliance Check</h3>
            <div class="subtitle">{phone_display}</div>
        </div>
        <div class="note-body">
            <div class="section">
                {badge_html}
                {' <span class="badge badge-yellow">MOBILE</span>' if is_cell else ''}
            </div>

            {status_box}

            <div class="section">
                <div class="section-title">Phone Details</div>
                <div class="data-row">
                    <div class="data-label">Line Type:</div>
                    <div class="data-value">{line_type}</div>
                </div>
                <div class="data-row">
                    <div class="data-label">Carrier:</div>
                    <div class="data-value">{carrier}</div>
                </div>
                <div class="data-row">
                    <div class="data-label">Is Mobile:</div>
                    <div class="data-value">{'Yes' if is_cell else 'No'}</div>
                </div>
            </div>

            {tcpa_warning}

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


def generate_reverse_phone_note(data: Dict[str, Any], phone: str = None) -> str:
    """
    Generate HTML note for reverse phone lookup results.

    Args:
        data: The reverse phone result data
        phone: The phone number that was searched

    Returns:
        Formatted HTML string
    """
    if not data or 'error' in data:
        return _generate_error_note("Reverse Phone", data.get('error', {}).get('message', 'Search failed'))

    phone_display = phone or data.get('phone', 'N/A')

    # Get persons associated with phone
    persons = data.get('persons', data.get('people', []))
    if not persons and 'person' in data:
        persons = [data['person']]

    # Build persons section
    persons_html = ""
    if persons:
        persons_html = '<div class="section"><div class="section-title">Associated Persons</div>'
        for person in persons[:5]:  # Limit to 5
            name = _format_name(person.get('name', {}))
            age = person.get('age', 'Unknown')
            address = _format_address(person.get('addresses', [{}])[0]) if person.get('addresses') else 'N/A'

            persons_html += f'''
                <div class="person-card">
                    <div class="person-name">{name}</div>
                    <div class="person-details">Age: {age} | {address}</div>
                </div>
            '''
        persons_html += '</div>'
    else:
        persons_html = '''
            <div class="section">
                <div class="warning-box">
                    No persons found associated with this phone number.
                </div>
            </div>
        '''

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>Reverse Phone Lookup</h3>
            <div class="subtitle">{phone_display}</div>
        </div>
        <div class="note-body">
            <div class="section">
                <span class="badge badge-blue">{len(persons)} person(s) found</span>
            </div>

            {persons_html}

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


def generate_reverse_email_note(data: Dict[str, Any], email: str = None) -> str:
    """
    Generate HTML note for reverse email lookup results.

    Args:
        data: The reverse email result data
        email: The email address that was searched

    Returns:
        Formatted HTML string
    """
    if not data or 'error' in data:
        return _generate_error_note("Reverse Email", data.get('error', {}).get('message', 'Search failed'))

    email_display = email or data.get('email', 'N/A')

    # Get persons associated with email
    persons = data.get('persons', data.get('people', []))
    if not persons and 'person' in data:
        persons = [data['person']]

    # Build persons section
    persons_html = ""
    if persons:
        persons_html = '<div class="section"><div class="section-title">Associated Persons</div>'
        for person in persons[:5]:  # Limit to 5
            name = _format_name(person.get('name', {}))
            age = person.get('age', 'Unknown')
            phones = person.get('phones', [])
            phone_display_inner = phones[0].get('number', 'N/A') if phones else 'N/A'

            persons_html += f'''
                <div class="person-card">
                    <div class="person-name">{name}</div>
                    <div class="person-details">Age: {age} | Phone: {phone_display_inner}</div>
                </div>
            '''
        persons_html += '</div>'
    else:
        persons_html = '''
            <div class="section">
                <div class="warning-box">
                    No persons found associated with this email address.
                </div>
            </div>
        '''

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>Reverse Email Lookup</h3>
            <div class="subtitle">{email_display}</div>
        </div>
        <div class="note-body">
            <div class="section">
                <span class="badge badge-blue">{len(persons)} person(s) found</span>
            </div>

            {persons_html}

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


def generate_owner_search_note(data: Dict[str, Any], address: str = None) -> str:
    """
    Generate HTML note for property owner search results.

    Args:
        data: The owner search result data
        address: The address that was searched

    Returns:
        Formatted HTML string
    """
    if not data or 'error' in data:
        return _generate_error_note("Owner Search", data.get('error', {}).get('message', 'Search failed'))

    address_display = address or data.get('address', 'N/A')

    # Get primary person
    primary = data.get('person', {})
    additional = data.get('additionalPersons', [])

    # Build primary owner section
    primary_html = ""
    if primary:
        name = _format_name(primary.get('name', {}))
        age = primary.get('age', 'Unknown')
        phones = primary.get('phones', [])
        emails = primary.get('emails', [])

        phone_list = ", ".join([p.get('number', 'N/A') for p in phones[:3]]) if phones else 'N/A'
        email_list = ", ".join([e.get('email', e) if isinstance(e, dict) else e for e in emails[:2]]) if emails else 'N/A'

        primary_html = f'''
            <div class="section">
                <div class="section-title">Primary Owner</div>
                <div class="person-card" style="border-left: 4px solid #4F46E5;">
                    <div class="person-name">{name}</div>
                    <div class="person-details">
                        Age: {age}<br>
                        Phone(s): {phone_list}<br>
                        Email(s): {email_list}
                    </div>
                </div>
            </div>
        '''

    # Build additional persons section
    additional_html = ""
    if additional:
        additional_html = '<div class="section"><div class="section-title">Additional Persons at Address</div>'
        for person in additional[:5]:
            name = _format_name(person.get('name', {}))
            age = person.get('age', 'Unknown')

            additional_html += f'''
                <div class="person-card">
                    <div class="person-name">{name}</div>
                    <div class="person-details">Age: {age}</div>
                </div>
            '''
        additional_html += '</div>'

    total_persons = 1 + len(additional) if primary else len(additional)

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>Property Owner Search</h3>
            <div class="subtitle">{address_display}</div>
        </div>
        <div class="note-body">
            <div class="section">
                <span class="badge badge-blue">{total_persons} person(s) found</span>
            </div>

            {primary_html}
            {additional_html}

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


def generate_person_search_note(data: Dict[str, Any], searched_criteria: Dict[str, Any] = None) -> str:
    """
    Generate HTML note for advanced person search results.

    Args:
        data: The person search result data
        searched_criteria: The original search criteria

    Returns:
        Formatted HTML string
    """
    if not data or 'error' in data:
        return _generate_error_note("Person Search", data.get('error', {}).get('message', 'Search failed'))

    # Get persons from results
    persons = data.get('persons', data.get('people', data.get('results', [])))
    if not persons and isinstance(data, dict):
        persons = [data]

    # Format search criteria
    criteria_display = ""
    if searched_criteria:
        parts = []
        if searched_criteria.get('firstName'):
            parts.append(searched_criteria['firstName'])
        if searched_criteria.get('lastName'):
            parts.append(searched_criteria['lastName'])
        if searched_criteria.get('city'):
            parts.append(searched_criteria['city'])
        if searched_criteria.get('state'):
            parts.append(searched_criteria['state'])
        criteria_display = " ".join(parts) if parts else "Search Results"
    else:
        criteria_display = "Search Results"

    # Build persons section
    persons_html = ""
    if persons:
        persons_html = '<div class="section"><div class="section-title">Matching Persons</div>'
        for person in persons[:10]:  # Limit to 10
            name = _format_name(person.get('name', {}))
            age = person.get('age', 'Unknown')
            phones = person.get('phones', [])
            addresses = person.get('addresses', [])

            phone_display = phones[0].get('number', 'N/A') if phones else 'N/A'
            address_display = _format_address(addresses[0]) if addresses else 'N/A'

            persons_html += f'''
                <div class="person-card">
                    <div class="person-name">{name}</div>
                    <div class="person-details">
                        Age: {age} | Phone: {phone_display}<br>
                        Address: {address_display}
                    </div>
                </div>
            '''
        persons_html += '</div>'
    else:
        persons_html = '''
            <div class="section">
                <div class="warning-box">
                    No matching persons found for the search criteria.
                </div>
            </div>
        '''

    html = f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header">
            <h3>Person Search Results</h3>
            <div class="subtitle">{criteria_display}</div>
        </div>
        <div class="note-body">
            <div class="section">
                <span class="badge badge-blue">{len(persons)} result(s) found</span>
            </div>

            {persons_html}

            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''

    return html


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_error_note(search_type: str, error_message: str) -> str:
    """Generate an error note when search fails."""
    return f'''
    {NOTE_STYLES}
    <div class="leadsynergy-note">
        <div class="note-header" style="background: #ef4444;">
            <h3>{search_type} - Error</h3>
        </div>
        <div class="note-body">
            <div class="danger-box">
                <strong>Search Failed</strong><br>
                {error_message}
            </div>
            <div class="note-footer">
                Generated by LeadSynergy | {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </div>
    '''


def _format_name(name_data: Dict[str, Any]) -> str:
    """Format a name dictionary into a full name string."""
    if not name_data:
        return "Unknown"

    if isinstance(name_data, str):
        return name_data

    parts = []
    if name_data.get('firstName'):
        parts.append(name_data['firstName'])
    if name_data.get('middleName'):
        parts.append(name_data['middleName'])
    if name_data.get('lastName'):
        parts.append(name_data['lastName'])
    if name_data.get('suffix'):
        parts.append(name_data['suffix'])

    return " ".join(parts) if parts else "Unknown"


def _format_address(addr: Dict[str, Any]) -> str:
    """Format an address dictionary into a string."""
    if not addr:
        return "N/A"

    if isinstance(addr, str):
        return addr

    parts = []

    # Street
    street = addr.get('street', addr.get('addressLine1', addr.get('streetAddress', '')))
    if street:
        parts.append(street)

    # City, State ZIP
    city = addr.get('city', '')
    state = addr.get('state', '')
    zip_code = addr.get('zip', addr.get('zipCode', addr.get('postalCode', '')))

    city_state_zip = []
    if city:
        city_state_zip.append(city)
    if state:
        city_state_zip.append(state)
    if zip_code:
        city_state_zip.append(str(zip_code))

    if city_state_zip:
        parts.append(", ".join(city_state_zip[:2]) + (" " + city_state_zip[2] if len(city_state_zip) > 2 else ""))

    return ", ".join(parts) if parts else "N/A"


def _assess_criminal_risk(records: List[Dict[str, Any]]) -> tuple:
    """
    Assess criminal risk level based on records.

    Returns:
        Tuple of (RiskLevel, summary_string)
    """
    if not records:
        return RiskLevel.GREEN, "No criminal records found."

    # Keywords indicating serious offenses
    serious_keywords = [
        'felony', 'murder', 'homicide', 'assault', 'robbery', 'burglary',
        'rape', 'sexual', 'kidnapping', 'arson', 'weapons', 'drug trafficking',
        'fraud', 'theft', 'battery'
    ]

    # Keywords indicating minor offenses
    minor_keywords = [
        'misdemeanor', 'traffic', 'dui', 'dwi', 'trespass', 'disorderly',
        'petty', 'possession'
    ]

    serious_count = 0
    minor_count = 0
    recent_offense = False

    current_year = datetime.now().year

    for record in records:
        offense_type = str(record.get('offenseType', record.get('type', ''))).lower()
        offense_date = record.get('offenseDate', record.get('date', ''))

        # Check if recent (within 5 years)
        try:
            if offense_date:
                year = int(str(offense_date)[:4])
                if current_year - year <= 5:
                    recent_offense = True
        except (ValueError, TypeError):
            pass

        # Categorize offense
        if any(keyword in offense_type for keyword in serious_keywords):
            serious_count += 1
        elif any(keyword in offense_type for keyword in minor_keywords):
            minor_count += 1
        else:
            # Unknown type - treat as moderate
            minor_count += 1

    # Determine risk level
    total_records = len(records)

    if serious_count > 0 or (total_records >= 3 and recent_offense):
        summary = f"{total_records} record(s) found including {serious_count} serious offense(s)."
        if recent_offense:
            summary += " Recent activity detected."
        return RiskLevel.RED, summary
    elif total_records > 0:
        summary = f"{total_records} record(s) found. Manual review recommended."
        return RiskLevel.YELLOW, summary
    else:
        return RiskLevel.GREEN, "No criminal records found."


# =============================================================================
# Main Note Generator
# =============================================================================

def generate_note_for_search(search_type: str, data: Dict[str, Any],
                             search_criteria: Dict[str, Any] = None) -> str:
    """
    Generate the appropriate note based on search type.

    Args:
        search_type: The type of search performed
        data: The search result data
        search_criteria: The original search criteria

    Returns:
        Formatted HTML string
    """
    generators = {
        'contact_enrichment': lambda: generate_contact_enrichment_note(data, search_criteria),
        'criminal_history_search': lambda: generate_criminal_history_note(
            data,
            f"{search_criteria.get('firstName', '')} {search_criteria.get('lastName', '')}" if search_criteria else None
        ),
        'dnc_check': lambda: generate_dnc_note(data, search_criteria.get('phone') if search_criteria else None),
        'reverse_phone_search': lambda: generate_reverse_phone_note(
            data, search_criteria.get('phone') if search_criteria else None
        ),
        'reverse_email_search': lambda: generate_reverse_email_note(
            data, search_criteria.get('email') if search_criteria else None
        ),
        'owner_search': lambda: generate_owner_search_note(
            data, search_criteria.get('address') if search_criteria else None
        ),
        'advanced_person_search': lambda: generate_person_search_note(data, search_criteria),
    }

    generator = generators.get(search_type)

    if generator:
        try:
            return generator()
        except Exception as e:
            logger.error(f"Error generating note for {search_type}: {e}", exc_info=True)
            return _generate_error_note(search_type, f"Error generating note: {str(e)}")
    else:
        logger.warning(f"Unknown search type: {search_type}")
        return _generate_error_note("Unknown Search", f"Unknown search type: {search_type}")
