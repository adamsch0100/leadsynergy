from typing import Optional, Dict, Any
import redis
import json
import os
from datetime import datetime
from app.database.supabase_client import SupabaseClientSingleton

class TenantResolver:
    """Resolves tenant context from webhook payloads"""
    
    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()
        
        # Initialize Redis for caching (optional but recommended)
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.cache_enabled = True
        except:
            print("Redis not available, running without cache")
            self.redis_client = None
            self.cache_enabled = False
            
        self.cache_ttl = 3600  # 1 hour cache
    
    def resolve_tenant_from_webhook(self, webhook_data: Dict, webhook_type: str) -> Optional[Dict]:
        """
        Resolve tenant info from webhook payload
        
        Returns:
            {
                'organization_id': str,
                'agent_id': str,
                'api_key': str,
                'tenant_metadata': dict
            }
        """
        # Extract person ID from webhook
        person_id = self._extract_person_id(webhook_data, webhook_type)
        
        if not person_id:
            print(f"Could not extract person_id from webhook type: {webhook_type}")
            return None
        
        # Check cache first
        if self.cache_enabled:
            cached = self._get_from_cache(person_id)
            if cached:
                return cached
        
        # Query database for tenant info
        tenant_info = self._query_tenant_info(person_id)
        
        if tenant_info and self.cache_enabled:
            # Cache the result
            self._set_cache(person_id, tenant_info)
        
        return tenant_info
    
    def _extract_person_id(self, webhook_data: Dict, webhook_type: str) -> Optional[str]:
        """Extract person ID based on webhook type and structure"""
        
        # Direct person ID in payload
        if 'personId' in webhook_data:
            return str(webhook_data['personId'])
        
        # From resourceIds array
        if 'resourceIds' in webhook_data and webhook_data.get('resourceIds'):
            return str(webhook_data['resourceIds'][0])
        
        # Extract from URI
        if 'uri' in webhook_data:
            uri = webhook_data['uri']
            if '/people/' in uri:
                # Extract ID from URI like "/v1/people/123456"
                parts = uri.split('/people/')
                if len(parts) > 1:
                    person_id = parts[1].split('/')[0]
                    return person_id
            elif '/notes/' in uri:
                # For note webhooks, we might need to fetch the note first
                # to get the person ID
                return self._extract_person_from_note_uri(uri)
        
        # Handle people array in webhook data
        if 'people' in webhook_data:
            people = webhook_data.get('people', [])
            if people and len(people) > 0:
                return str(people[0].get('id'))
        
        return None
    
    def _extract_person_from_note_uri(self, uri: str) -> Optional[str]:
        """Extract person ID from note URI by parsing the note ID"""
        # This would require an additional API call to FUB to get note details
        # For now, return None and handle this case differently
        return None
    
    def _query_tenant_info(self, person_id: str) -> Optional[Dict]:
        """Query database for tenant information based on person ID"""
        try:
            # First, find the lead by fub_person_id
            lead_result = self.supabase.table("leads")\
                .select("id, assigned_agent_id, organization_id, lead_source_id")\
                .eq("fub_person_id", person_id)\
                .single()\
                .execute()
            
            if not lead_result.data:
                print(f"No lead found for fub_person_id: {person_id}")
                return None
            
            lead_data = lead_result.data
            
            # Priority 1: Try assigned agent's API key
            if lead_data.get("assigned_agent_id"):
                agent_api_key = self._get_agent_api_key(lead_data["assigned_agent_id"])
                if agent_api_key:
                    return {
                        "organization_id": lead_data.get("organization_id"),
                        "agent_id": lead_data["assigned_agent_id"],
                        "api_key": agent_api_key,
                        "lead_id": lead_data["id"],
                        "resolution_method": "assigned_agent"
                    }
            
            # Priority 2: Try organization admin's API key
            if lead_data.get("organization_id"):
                org_api_key = self._get_organization_api_key(lead_data["organization_id"])
                if org_api_key:
                    return {
                        "organization_id": lead_data["organization_id"],
                        "agent_id": org_api_key["admin_id"],
                        "api_key": org_api_key["api_key"],
                        "lead_id": lead_data["id"],
                        "resolution_method": "organization_admin"
                    }
            
            # Priority 3: Try to get from lead source settings (if applicable)
            if lead_data.get("lead_source_id"):
                source_api_key = self._get_lead_source_api_key(lead_data["lead_source_id"])
                if source_api_key:
                    return {
                        "organization_id": source_api_key.get("organization_id"),
                        "agent_id": source_api_key.get("agent_id"),
                        "api_key": source_api_key["api_key"],
                        "lead_id": lead_data["id"],
                        "resolution_method": "lead_source"
                    }
            
            print(f"No API key found for lead: {person_id}")
            return None
            
        except Exception as e:
            print(f"Error querying tenant info: {str(e)}")
            return None
    
    def _get_agent_api_key(self, agent_id: str) -> Optional[str]:
        """Get API key for a specific agent"""
        try:
            # Try user_profiles table
            result = self.supabase.table("user_profiles")\
                .select("fub_api_key")\
                .eq("id", agent_id)\
                .single()\
                .execute()
            
            if result.data and result.data.get("fub_api_key"):
                return result.data["fub_api_key"]
            
            # Fallback to users table if needed
            result = self.supabase.table("users")\
                .select("fub_api_key")\
                .eq("id", agent_id)\
                .single()\
                .execute()
            
            if result.data and result.data.get("fub_api_key"):
                return result.data["fub_api_key"]
                
        except Exception as e:
            print(f"Error getting agent API key: {str(e)}")
            
        return None
    
    def _get_organization_api_key(self, organization_id: str) -> Optional[Dict]:
        """Get API key from organization admin"""
        try:
            # Get admin users for the organization
            result = self.supabase.table("organization_users")\
                .select("user_id, users!inner(id, fub_api_key)")\
                .eq("organization_id", organization_id)\
                .eq("role", "admin")\
                .execute()
            
            if result.data:
                # Find first admin with API key
                for org_user in result.data:
                    if org_user.get("users") and org_user["users"].get("fub_api_key"):
                        return {
                            "api_key": org_user["users"]["fub_api_key"],
                            "admin_id": org_user["user_id"]
                        }
            
            # Alternative query if join doesn't work
            admin_result = self.supabase.table("organization_users")\
                .select("user_id")\
                .eq("organization_id", organization_id)\
                .eq("role", "admin")\
                .execute()
            
            if admin_result.data:
                for admin in admin_result.data:
                    api_key = self._get_agent_api_key(admin["user_id"])
                    if api_key:
                        return {
                            "api_key": api_key,
                            "admin_id": admin["user_id"]
                        }
                        
        except Exception as e:
            print(f"Error getting organization API key: {str(e)}")
            
        return None
    
    def _get_lead_source_api_key(self, lead_source_id: str) -> Optional[Dict]:
        """Get API key associated with lead source (if configured)"""
        # This is for future expansion where lead sources might have
        # their own API key configurations
        return None
    
    def _get_from_cache(self, person_id: str) -> Optional[Dict]:
        """Get tenant info from Redis cache"""
        if not self.cache_enabled:
            return None
            
        try:
            key = f"tenant:{person_id}"
            cached = self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Cache get error: {str(e)}")
            
        return None
    
    def _set_cache(self, person_id: str, tenant_info: Dict):
        """Set tenant info in Redis cache"""
        if not self.cache_enabled:
            return
            
        try:
            key = f"tenant:{person_id}"
            self.redis_client.setex(
                key,
                self.cache_ttl,
                json.dumps(tenant_info)
            )
        except Exception as e:
            print(f"Cache set error: {str(e)}")
    
    def clear_cache_for_person(self, person_id: str):
        """Clear cache for a specific person (useful when assignments change)"""
        if not self.cache_enabled:
            return
            
        try:
            key = f"tenant:{person_id}"
            self.redis_client.delete(key)
        except Exception as e:
            print(f"Cache clear error: {str(e)}")
    
    def resolve_organization_from_user(self, user_id: str) -> Optional[str]:
        """Resolve organization ID from user ID"""
        try:
            result = self.supabase.table("organization_users")\
                .select("organization_id")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            if result.data:
                return result.data["organization_id"]
                
        except Exception as e:
            print(f"Error resolving organization from user: {str(e)}")
            
        return None


# Singleton instance for reuse
_tenant_resolver_instance = None

def get_tenant_resolver() -> TenantResolver:
    """Get singleton instance of TenantResolver"""
    global _tenant_resolver_instance
    if _tenant_resolver_instance is None:
        _tenant_resolver_instance = TenantResolver()
    return _tenant_resolver_instance
