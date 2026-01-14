# Proxy Configuration for Referral Scrapers

## Overview

The referral scraping system now supports optional proxy usage through IPRoyal.com. This feature can be enabled or disabled using an environment variable flag.

## Configuration

### Environment Variable

Set the `USE_PROXY` environment variable to control proxy usage:

```bash
# Enable proxy usage
USE_PROXY=true

# Disable proxy usage (default)
USE_PROXY=false
```

### Accepted Values

The following values are accepted for `USE_PROXY`:

- `true`, `1`, `yes` - Enable proxy usage
- `false`, `0`, `no` - Disable proxy usage
- Not set - Defaults to disabled

## How It Works

### When Proxy is Enabled (`USE_PROXY=true`)

- DriverService will attempt to load proxy configuration for the organization
- HTTP requests through BaseReferralService will use organization-specific proxies
- Selenium WebDriver will be configured with proxy settings
- IPRoyal proxy credentials must be configured in the database

### When Proxy is Disabled (`USE_PROXY=false` or not set)

- DriverService operates without proxy configuration
- HTTP requests are made directly without proxy
- Selenium WebDriver uses standard configuration
- Original scraping behavior is preserved

## Usage Examples

### Development/Testing (No Proxy)

```bash
# In your .env file or environment
USE_PROXY=false
```

### Production with Proxy

```bash
# In your .env file or environment
USE_PROXY=true

# Also ensure IPRoyal credentials are configured:
IPROYAL_HOST=geo.iproyal.com
IPROYAL_HTTP_PORT=12321
IPROYAL_SOCKS5_PORT=32325
```

## Database Configuration

When proxy is enabled, ensure organizations have proxy configurations in the `organization_proxy_configs` table:

```sql
INSERT INTO organization_proxy_configs (
    organization_id,
    proxy_username,
    proxy_password,
    is_active
) VALUES (
    'your_org_id',
    'your_iproyal_username',
    'your_iproyal_password',
    true
);
```

## Logging

The system provides clear logging about proxy status:

- `ReferralExecutor initialized - Proxy usage: ENABLED/DISABLED`
- `Driver initialized successfully with/without proxy`
- `HTTP proxy usage is disabled via USE_PROXY environment variable`
- `Proxy configuration loaded for organization {org_id}`

## Migration Strategy

1. **Current State**: Set `USE_PROXY=false` (or leave unset) to maintain existing functionality
2. **Testing**: Enable proxy for specific organizations to test IPRoyal integration
3. **Production**: Once IPRoyal subscription is active, set `USE_PROXY=true` globally

## Benefits

- **Cost Control**: Only use paid proxy services when needed
- **Testing**: Test with and without proxies easily
- **Flexibility**: Different environments can have different proxy configurations
- **Backward Compatibility**: Existing scrapers continue to work unchanged
