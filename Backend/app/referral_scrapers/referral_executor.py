from app.models.lead import Lead
from app.models.stage_mapping import StageMapping
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import os

from app.referral_scrapers.referral_service_factory import ReferralServiceFactory
from app.database.supabase_client import SupabaseClientSingleton
from supabase import Client


class ReferralExecutor:
    IGNORED_STATUSES = {
        "Redfin": ["Create Deal"],
        "ReferralExchange": ["We are in escrow", "We have closed escrow"],
        "HomeLight": ["Meeting Scheduled", "Coming Soon", "Listing", "In Escrow"],
        "Estately": [],
        "AgentPronto": [],
        "Agent Pronto": [],
        "MyAgentFinder": [],
        "My Agent Finder": [],
    }

    def __init__(self, lead: Lead, stage_mapping: StageMapping, organization_id: str = None) -> None:
        self.lead = lead
        self.stage_mapping = stage_mapping
        self.organization_id = organization_id
        self.logger = logging.getLogger(__name__)
        
        # Setup logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.factory = ReferralServiceFactory()
        
        # Check proxy configuration
        self.use_proxy = os.getenv("USE_PROXY", "false").lower() in ["true", "1", "yes"]
        self.logger.info(f"ReferralExecutor initialized - Proxy usage: {'ENABLED' if self.use_proxy else 'DISABLED'}")

    def should_ignore_status(self) -> bool:
        """
        Determine if the current lead status should be ignored for automation
        :returns True if the status should be ignored (skipped from automation)
        """
        if not self.lead or not self.lead.source or not self.lead.status:
            return False

        platform = self.lead.source

        # Get platform-specific stage mapping
        platform_status = None
        if self.stage_mapping and hasattr(self.stage_mapping, 'platform_stage_name'):
            platform_status = self.stage_mapping.platform_stage_name.get(self.lead.status)

        # If we can't determine the platform status, use FUB status
        self.logger.info(f"Platform Status is: {platform_status}")
        if not platform_status:
            platform_status = self.lead.status

        # Check if the mapped status should be ignored
        if platform in self.IGNORED_STATUSES and platform_status in self.IGNORED_STATUSES[platform]:
            self.logger.info(
                f"Ignoring status '{platform_status}' for {platform} - requires manual handling"
            )
            return True

        return False

    def execute(self) -> bool:
        # Check if we should ignore this status
        if self.should_ignore_status():
            self.logger.info(f"Status requires manual handling for {self.lead.source} - skipping automation")
            return False

        # Get the mapped stage for the platform
        mapped_stage = None
        if self.stage_mapping and hasattr(self.stage_mapping, 'platform_stage_name'):
            if isinstance(self.stage_mapping.platform_stage_name, dict):
                mapped_stage = self.stage_mapping.platform_stage_name.get(self.lead.status)
            elif isinstance(self.stage_mapping.platform_stage_name, str):
                mapped_stage = self.stage_mapping.platform_stage_name
        
        # Fallback to lead status if no mapping found
        if not mapped_stage:
            mapped_stage = self.lead.status
            self.logger.warning(f"No stage mapping found, using FUB stage: {mapped_stage}")

        if self.lead.source == "Redfin":
            from app.referral_scrapers.redfin.redfin_service import RedfinService
            redfin_service = RedfinService(
                lead=self.lead,
                status=mapped_stage,
                organization_id=self.organization_id
            )
            result = redfin_service.redfin_run()
            return result
        elif self.lead.source == "ReferralExchange":
            from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService
            # ReferralExchange expects status as dict
            status_dict = {"status": mapped_stage}
            referral_exchange_service = ReferralExchangeService(
                lead=self.lead,
                status=status_dict,
                organization_id=self.organization_id
            )
            result = referral_exchange_service.referral_exchange_run()
            return result
        elif self.lead.source == "HomeLight":
            from app.referral_scrapers.homelight.homelight_service import HomelightService
            homelight_service = HomelightService(
                lead=self.lead,
                status=mapped_stage,
                organization_id=self.organization_id
            )
            result = homelight_service.homelight_run()
            return result
        elif self.lead.source == "Estately":
            from app.referral_scrapers.estately.estately_service import EstatelyService
            estately_service = EstatelyService(
                lead=self.lead,
                organization_id=self.organization_id
            )
            self.logger.info("Estately service is now on")
            return False
        elif self.lead.source == "AgentPronto" or self.lead.source == "Agent Pronto":
            from app.referral_scrapers.agent_pronto.agent_pronto_service import AgentProntoService
            agent_pronto_service = AgentProntoService(
                lead=self.lead,
                status=mapped_stage,
                organization_id=self.organization_id
            )
            result = agent_pronto_service.agent_pronto_run()
            return result
        elif self.lead.source == "MyAgentFinder" or self.lead.source == "My Agent Finder":
            from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService
            my_agent_finder_service = MyAgentFinderService(
                lead=self.lead,
                status=mapped_stage,
                organization_id=self.organization_id
            )
            result = my_agent_finder_service.my_agent_finder_run()
            return result

        return False

    def notify_manual_status(self, platform, status):
        """Send notification about status requiring manual handling"""
        # Notification logic (email, Slack, etc.)
        pass
