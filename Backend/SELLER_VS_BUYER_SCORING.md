# Seller vs Buyer Scoring & Handoff Strategy

## The Problem

Current system scores ALL leads using buyer criteria:
- Pre-approval status (only relevant for buyers)
- "Wants to see properties" triggers handoff (only buyers)
- Budget = what they can afford to buy (wrong for sellers)

**A hot seller is NOT the same as a hot buyer!**

---

## Buyer Scoring (Current - Keep This)

### Qualification Criteria (0-100 points):
1. **Pre-Approval Status (25 points)**
   - Pre-approved: +25
   - Applied but not approved: +15
   - Not applied: +5
   - No discussion: 0

2. **Timeline (25 points)**
   - Immediate/ASAP/30 days: +25
   - 60 days: +20
   - 90 days: +15
   - 3-6 months: +10
   - 6+ months: +5
   - Just browsing: 0

3. **Engagement (20 points)**
   - Asking specific questions: +10
   - Responding quickly: +5
   - Sharing detailed needs: +5

4. **Budget Clarity (15 points)**
   - Clear price range: +15
   - General range: +10
   - Vague: +5

5. **Motivation (15 points)**
   - Job relocation/divorce/urgent: +15
   - Growing family/downsizing: +12
   - Investment: +10
   - Just looking: +3

### Hot Buyer Signals (Score 70+):
- Pre-approved for mortgage
- Wants to buy within 30-60 days
- Asking about specific properties
- Has clear budget and requirements
- Motivated reason (job, family)

### Handoff Triggers for Buyers:
✅ **Appointment Setting:**
- "I want to see that property"
- "Can we schedule a showing?"
- "When can I tour homes?"
- "I'm free Saturday to look"

✅ **Ready to Transact:**
- "I want to make an offer"
- "How do I put in a bid?"
- Discussing specific properties seriously

✅ **Qualification Complete:**
- Pre-approved, clear timeline, clear budget, ready area
- Score >70 + wants to take next step

---

## Seller Scoring (NEW - Needs Implementation)

### Qualification Criteria (0-100 points):
1. **Listing Timeline (30 points)** ← MOST IMPORTANT for sellers
   - Needs to list within 30 days: +30
   - 60 days: +25
   - 90 days: +20
   - 3-6 months: +15
   - 6+ months / just exploring: +5

2. **Price Expectations (25 points)** ← CRITICAL
   - Realistic expectations (knows comps): +25
   - Open to market feedback: +20
   - Has a number but flexible: +15
   - Unrealistic but educable: +10
   - Completely unrealistic / firm: +5

3. **Property Condition (15 points)**
   - Move-in ready / recently updated: +15
   - Good condition / minor work: +12
   - Needs some work: +8
   - Major repairs needed: +5
   - Unknown: +8 (neutral - need to see it)

4. **Motivation Strength (20 points)**
   - Already bought another home: +20 (URGENT!)
   - Job relocation / transfer: +18
   - Divorce / estate sale: +18
   - Downsizing / upsizing: +15
   - Financial distress: +15
   - Just testing market: +5

5. **Engagement & Readiness (10 points)**
   - Asking about process / timeline: +5
   - Wants valuation appointment: +5
   - Discussing commission / costs: +3
   - Responsive and engaged: +2

### Hot Seller Signals (Score 70+):
- Needs to list within 60 days
- Has realistic price expectations
- Strong motivation (already bought, relocating, etc.)
- Property in good condition
- Asking about next steps

### Warm Seller Signals (Score 40-69):
- 3-6 month timeline
- Somewhat flexible on price
- Testing the market but not urgent
- Property needs some work

### Cold Seller Signals (Score <40):
- 6+ month timeline / just curious
- Unrealistic price expectations
- Property needs major work
- No clear motivation
- Low engagement

---

## Seller Handoff Triggers (NEW)

### ✅ Appointment Setting:
- "I want a home valuation"
- "Can you come see my property?"
- "When can you do a walkthrough?"
- "I'd like to discuss listing price"
- "Can we schedule a time to meet?"

### ✅ Ready to List:
- "I want to list within [timeframe]"
- "What do I need to do to get my home on the market?"
- "How soon can we list?"
- "I already bought another house" (URGENT!)

### ✅ Price Discussion:
- "What's my home worth?"
- "What would it sell for?"
- "I saw [address] sold for $X - what about mine?"
- Asking about comparable sales

### ✅ Process Questions:
- "What's your commission?"
- "How does the listing process work?"
- "How long does it take to sell?"
- "Do I need to make repairs before listing?"

### ✅ Competition Indicators:
- "I'm talking to other agents"
- "I have another agent coming tomorrow"
- "What makes you different from [other agent]?"
- Time-sensitive decision making

### ✅ Score-Based Handoff:
- Score >70 AND asking about next steps
- Score >60 AND immediate timeline
- Score >50 AND already talking to other agents

---

## Different Qualification Conversations

### Buyer Qualification Questions:
1. "Have you talked to a lender yet?"
2. "What's your ideal timeline for moving?"
3. "What's your budget range?"
4. "What areas are you looking at?"
5. "What type of property? (SFH, condo, etc.)"

### Seller Qualification Questions:
1. "What's your ideal timeline for listing?"
2. "Have you thought about your target price?"
3. "Is your home move-in ready or does it need work?"
4. "What's motivating your move?"
5. "Are you looking to buy another home or just selling?"

---

## Implementation Changes Needed

### 1. Update LeadScorer class to detect lead type:
```python
def calculate_score(
    self,
    lead_type: str = "buyer",  # NEW: "buyer", "seller", "both"
    # ... existing params
) -> LeadScore:
    if lead_type == "seller":
        return self._calculate_seller_score(...)
    elif lead_type == "buyer":
        return self._calculate_buyer_score(...)
    elif lead_type == "both":
        # Score both aspects, use higher score
        return self._calculate_combined_score(...)
```

### 2. Add seller-specific scoring method:
```python
def _calculate_seller_score(
    self,
    listing_timeline: Optional[str] = None,
    price_expectations: Optional[str] = None,  # "realistic", "flexible", "unrealistic"
    property_condition: Optional[str] = None,  # "excellent", "good", "needs_work"
    motivation: Optional[str] = None,
    engagement_signals: Optional[Dict] = None,
) -> LeadScore:
    # Timeline: 0-30 points
    timeline_score = self._score_seller_timeline(listing_timeline)

    # Price expectations: 0-25 points
    price_score = self._score_price_expectations(price_expectations)

    # Property condition: 0-15 points
    condition_score = self._score_property_condition(property_condition)

    # Motivation: 0-20 points
    motivation_score = self._score_seller_motivation(motivation)

    # Engagement: 0-10 points
    engagement_score = self._score_engagement(engagement_signals)

    total = timeline_score + price_score + condition_score + motivation_score + engagement_score
    # ...
```

### 3. Update AI Response Generator prompt:
Add seller-specific handoff triggers and qualification extraction:

```
For BUYERS:
- Extract: pre_approved, budget, timeline, location, property_type
- Handoff when: wants showings, ready to make offer

For SELLERS:
- Extract: listing_timeline, price_expectations, property_condition, motivation, already_purchased
- Handoff when: wants valuation appointment, ready to list, discussing price/commission
```

### 4. Update extracted_info structure:
```python
# Current (buyer-focused):
"extracted_info": {
    "timeline": "30_days",
    "budget": "$400k-$600k",
    "pre_approved": true,
    "location": "Denver"
}

# NEW for sellers:
"extracted_info": {
    "listing_timeline": "60_days",
    "price_expectations": "realistic",  # or "flexible", "unrealistic", "unknown"
    "property_condition": "good",  # or "excellent", "needs_work", "unknown"
    "target_price": "$650k",  # what they think it's worth
    "motivation": "job_relocation",
    "already_purchased": true  # URGENT signal!
}

# NEW for both:
"extracted_info": {
    # Buyer side
    "buyer_timeline": "30_days",
    "budget": "$400k-$600k",
    # Seller side
    "listing_timeline": "immediate",
    "property_address": "9556 Juniper Way",
    "coordination_needed": true  # Need to coordinate sale + purchase
}
```

---

## Score Calculation Examples

### Example 1: Hot Seller
- **Profile:** Needs to list within 30 days, realistic price, already bought another home
- **Scoring:**
  - Timeline (30 days): +30
  - Price (realistic): +25
  - Condition (good): +12
  - Motivation (already bought): +20
  - Engagement (wants valuation): +5
  - **Total: 92 (HOT)**
- **Action:** Handoff immediately for valuation appointment

### Example 2: Warm Seller
- **Profile:** 3-6 month timeline, flexible on price, testing market
- **Scoring:**
  - Timeline (3-6 months): +15
  - Price (flexible): +20
  - Condition (excellent): +15
  - Motivation (downsizing): +15
  - Engagement (asking questions): +5
  - **Total: 70 (WARM)**
- **Action:** Continue nurturing, send market reports

### Example 3: Cold Seller
- **Profile:** "Just curious", wants $100k over market, 1+ year timeline
- **Scoring:**
  - Timeline (1 year): +5
  - Price (unrealistic): +5
  - Condition (unknown): +8
  - Motivation (just curious): +5
  - Engagement (low): +2
  - **Total: 25 (COLD)**
- **Action:** Monthly market updates, price education

### Example 4: Hot Buyer (for comparison)
- **Profile:** Pre-approved, 30-day timeline, clear budget, motivated
- **Scoring:**
  - Pre-approval: +25
  - Timeline (30 days): +25
  - Engagement: +15
  - Budget (clear): +15
  - Motivation (job relocation): +15
  - **Total: 95 (HOT)**
- **Action:** Handoff immediately for property showings

---

## Handoff Message Customization

### For Buyers:
> "🏠 NEW HOT BUYER LEAD - Immediate Attention Needed
>
> Name: Victor Yax
> Score: 92/100
> Timeline: Wants to buy within 30 days
> Budget: $400k-$600k
> Status: Pre-approved
>
> They're ready to schedule showings. Call them ASAP!"

### For Sellers:
> "📊 NEW HOT SELLER LEAD - Valuation Appointment Needed
>
> Name: Millard Jones
> Score: 92/100
> Property: 9556 Juniper Way, Arvada, CO
> Timeline: Wants to list within 30 days
> Motivation: Already purchased another home (URGENT!)
>
> They want a home valuation appointment. Schedule it TODAY!"

---

## Next Steps

Would you like me to:

1. **Update LeadScorer** to support seller scoring?
2. **Update AI prompts** to extract seller-specific info?
3. **Update handoff triggers** to differentiate buyers vs sellers?
4. **Create separate scoring logic** for "both" (coordinated transactions)?

The key insight: **A seller asking "what's my home worth?" is the equivalent of a buyer saying "I want to see properties" - both should trigger immediate handoff!**
