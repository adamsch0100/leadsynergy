# Lead Personalization - Using Full FUB Data

## Before vs After: Millard Jones Example

### BEFORE (Generic):
**SMS:** "Hey Millard! Nadia here. Noticed you're considering selling in Arvada. Want a quick market analysis?"
**Email:** "I saw you're thinking about selling your home in Arvada..."

### AFTER (Personalized):
**SMS:** "Hey Millard! Nadia here. Saw you're thinking about selling your home at **9556 Juniper Way** - want to chat about what it could fetch?"
**Email:** "Top Agents Ranked connected us because you're thinking about selling your home at **9556 Juniper Way, Arvada, CO**. I'd love to send you a free comparative market analysis showing what other homes on **Juniper Way** and nearby have sold for recently..."

## Rich FUB Data Now Being Used

### 1. **Specific Property Address** (CRITICAL for Sellers)
```python
property_address: "9556 Juniper Way"
property_full_address: "9556 Juniper Way, Arvada, CO"
```
**Source:** FUB `addresses` field
**Used for:** Sellers - their home they want to list
**Impact:** Massively more personal - shows you actually looked at their specific situation

### 2. **Inquiry Property** (CRITICAL for Buyers)
```python
inquiry_property: "123 Main Street, Denver, CO"
```
**Source:** FUB `events[].property` field
**Used for:** Buyers who inquired about a specific property
**Impact:** "Saw you were checking out 123 Main Street" vs generic "looking at Denver"

### 3. **Lead Type** (Buyer/Seller/Both)
```python
lead_type: "seller" | "buyer" | "both"
```
**Source:** FUB `type` field + tags
**Impact:**
- **Sellers** get: home valuation, comp analysis, listing strategy
- **Buyers** get: property search, listings, market conditions
- **Both** get: coordinated transaction timing, sell-first vs buy-first planning

### 4. **Lead Source** (with friendly names)
```python
source: "ReferralExchange" → "Top Agents Ranked"
```
**Source:** FUB `source` field with friendly mapping
**Used for:** "Top Agents Ranked connected us because..."
**Impact:** Explains HOW you were matched, builds trust

### 5. **Location Details**
```python
city: "Arvada"
state: "CO"
zip_code: "80004"
neighborhoods: ["Highlands", "Cherry Creek"]
```
**Source:** FUB `addresses`, `cities` field
**Impact:** Specific neighborhood/area mentions

### 6. **Timeline & Motivation**
```python
timeline: "Immediate" | "1-3 months" | "6-12 months" | "Just Browsing"
financing_status: "Pre-approved" | "Not Applied"
```
**Source:** FUB events `description` field (parsed)
**Impact:** Matches urgency: "Let's find you something this weekend!" vs "No rush - I'll be a resource"

### 7. **Price Range**
```python
price_min: 400000
price_max: 600000
```
**Source:** FUB `priceMin`, `priceMax` fields
**Impact:** "I see you're looking in the $400K-$600K range"

### 8. **Property Type**
```python
property_type: "Single Family" | "Condo" | "Townhouse"
```
**Source:** FUB `propertyType` field
**Impact:** "Looking for a single-family home in..."

### 9. **Buyer Type**
```python
buyer_type: "First-time" | "Investor" | "Relocating"
```
**Source:** FUB tags (parsed)
**Impact:** Different approach for first-time buyers vs investors

### 10. **Professional Context** (NEW!)
```python
company: "Metron Farnier - Smart Water Meters"
job_title: "Territory Manager"
```
**Source:** FUB `socialData` field
**Potential use:** "I know you're busy with your territory manager role - I'll keep this process smooth"

### 11. **Tags**
```python
tags: ["kts new seller machine leadngage", "Seller"]
```
**Source:** FUB `tags` field
**Impact:** Additional context for lead categorization

## How the AI Uses This Data

### AI System Prompt (updated):
```
CRITICAL RULES:
8. If "Property to Sell" or "Property They Inquired About" is provided,
   ALWAYS mention the EXACT ADDRESS in your message!

10. For SELLERS: If you have their property address, reference it specifically:
    "your home at 9556 Juniper Way" not "your home in Arvada"

11. For BUYERS: If they inquired about a specific property, mention it:
    "saw you were checking out 123 Main Street"

LEAD TYPE RULES:
- If Lead Type is "SELLER only": Focus on home valuation, market timing,
  listing strategy, comparable sales
- If Lead Type is "BUYER only": Focus on home search, listings, neighborhoods,
  market conditions
- If Lead Type is "BUYER AND SELLER": Coordinate sale and purchase timing
```

### Context Sent to AI:
```
Lead Name: Millard
Lead Type: SELLER only - looking to sell their home
Property to Sell: 9556 Juniper Way, Arvada, CO
Lead Source: Top Agents Ranked
Location Interest: Arvada, CO
Agent Name: Nadia
Brokerage: The Schwartz Team at Coldwell Banker
```

## Fallback Messages (when AI unavailable)

The fallback now also uses property-specific data:

### For Sellers with Address:
```
SMS: "Hey Millard! Nadia here. Saw you're thinking about selling your home
at 9556 Juniper Way - want to chat about what it could fetch?"

Email: "Top Agents Ranked connected us because you're thinking about selling
your home at 9556 Juniper Way, Arvada, CO. I'd love to send you a free
comparative market analysis showing what other homes on Juniper Way and
nearby have sold for recently..."
```

### For Buyers with Inquiry Property:
```
SMS: "Hey Victor! Nadia here. Saw you were checking out 123 Main Street in
Denver - great property! Want to see more like it?"
```

## Data Extraction Flow

```
FUB Webhook (peopleCreated)
  ↓
person_data = fub.get_person(person_id)
events = fub.get_events(person_id, limit=10)
  ↓
LeadContext.from_fub_data(person_data, events)
  ↓ Extracts:
  - Basic: name, email, phone
  - Type: buyer/seller/both (from 'type' field + tags)
  - Property Address: from addresses[0] (for sellers)
  - Inquiry Property: from events[].property (for buyers)
  - Location: city, state, zip
  - Timeline: from events[].description
  - Source: with friendly name mapping
  - Social: company, job_title
  ↓
generate_initial_outreach(context)
  ↓
AI generates personalized SMS + Email
  OR
Fallback generates from context
  ↓
Send via Playwright → appears in FUB
```

## Testing the Changes

### For a New Seller Lead:
1. Check FUB person data has `addresses[0].street`
2. Verify `type` = "Seller"
3. SMS should mention the exact property address
4. Email should reference the specific street

### For a New Buyer Lead:
1. Check FUB events for `property.street`
2. Verify inquiry property is extracted
3. SMS should mention the specific property they inquired about

## Future Enhancements

Additional FUB data we could use:
- **Deal stage/status** - adjust messaging based on where they are in process
- **Previous interactions** - reference past conversations
- **Assigned agent** - personalize based on who's handling them
- **Custom fields** - any custom data you're tracking in FUB
- **Notes** - mine notes for additional context
- **Website visits** - "Saw you've been checking out our listings..."

## Key Takeaway

**Generic message:** "Hey, saw you're interested in Denver"
**Personalized message:** "Hey Millard! Saw you're thinking about selling your home at 9556 Juniper Way in Arvada - want a quick comp analysis showing what other homes on Juniper Way have sold for?"

The second one feels like you actually looked at their situation, which dramatically increases response rates.
