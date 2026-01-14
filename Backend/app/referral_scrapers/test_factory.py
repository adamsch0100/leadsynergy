from app.referral_scrapers.referral_service_factory import ReferralServiceFactory
from app.models.lead import Lead

lead = Lead()
lead.source = "Redfin"

service_factory = ReferralServiceFactory.get_service(source_name=lead.source, lead=lead)

if service_factory:
    result = service_factory.return_platform_name()
    print(result)
else:
    print(f"Not service found for source: {lead.source}")