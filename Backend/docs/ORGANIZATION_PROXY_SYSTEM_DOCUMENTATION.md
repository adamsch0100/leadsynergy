# Organization-Specific Proxy System Documentation

## ✅ Implementation Status: COMPLETE

This document describes the complete implementation of organization-specific IPRoyal proxy support for referral scraping operations to prevent IP banning and improve reliability.

## 🎯 Overview

The Organization-Specific Proxy System provides each organization with its own dedicated IPRoyal proxy configuration for referral platform scraping. This ensures:

- **IP Ban Prevention**: Each organization uses different IP addresses
- **Improved Reliability**: Dedicated proxies for better performance
- **Session Management**: Sticky sessions for consistent scraping
- **Automatic Rotation**: IPRoyal's built-in IP rotation
- **Secure Storage**: Encrypted proxy credentials in database

## 🏗️ Architecture

### Core Components

1. **ProxyService** - Manages organization proxy configurations
2. **Enhanced DriverService** - Selenium driver with proxy support
3. **Enhanced BaseReferralService** - HTTP requests with proxy support
4. **Database Schema** - Secure proxy configuration storage
5. **API Endpoints** - Management and testing interfaces

### Integration Points

```
Organization → Proxy Config → Referral Scrapers
     ↓              ↓              ↓
   Users     IPRoyal Proxies   Web Scraping
```

## 📊 Database Schema

### `organization_proxy_configs` Table

```sql
CREATE TABLE organization_proxy_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    proxy_username VARCHAR(255) NOT NULL,
    proxy_password VARCHAR(255) NOT NULL,
    proxy_host VARCHAR(255) NOT NULL DEFAULT 'geo.iproyal.com',
    http_port VARCHAR(10) NOT NULL DEFAULT '12321',
    socks5_port VARCHAR(10) NOT NULL DEFAULT '32325',
    proxy_type VARCHAR(20) NOT NULL DEFAULT 'http',
    rotation_enabled BOOLEAN NOT NULL DEFAULT true,
    session_duration VARCHAR(10) NOT NULL DEFAULT '10m',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fk_org_proxy_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT proxy_type_check
        CHECK (proxy_type IN ('http', 'socks5'))
);

-- Indexes for performance
CREATE INDEX idx_org_proxy_organization ON organization_proxy_configs(organization_id);
CREATE INDEX idx_org_proxy_active ON organization_proxy_configs(is_active);
CREATE UNIQUE INDEX idx_org_proxy_org_active
    ON organization_proxy_configs(organization_id) WHERE is_active = true;
```

## 🔧 Implementation Details

### 1. ProxyService (`app/service/proxy_service.py`)

Manages proxy configurations and URL generation.

#### Key Methods:

- `get_organization_proxy_config(org_id)` - Retrieves proxy configuration
- `create_proxy_url(org_id, proxy_type)` - Generates proxy URLs with session management
- `get_proxy_dict_for_requests(org_id)` - Returns proxy dict for HTTP requests
- `get_proxy_for_selenium(org_id)` - Returns proxy config for Selenium WebDriver
- `create_organization_proxy_config()` - Creates/updates proxy configuration
- `test_proxy_connection(org_id)` - Tests proxy connectivity

#### Session Management:

```python
# Generates unique session IDs for sticky sessions
session_id = f"org{organization_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
proxy_auth = f"{username}_session-{session_id}_lifetime-{duration}:{password}"
```

### 2. Enhanced DriverService (`app/referral_scrapers/utils/driver_service.py`)

Updated to support organization-specific proxies for Selenium WebDriver.

#### Changes:

- Constructor accepts `organization_id` parameter
- Automatically loads proxy configuration for organization
- Creates proxy authentication extensions for Chrome
- Passes proxy configuration to Chrome options

#### Proxy Extension Creation:

The system creates temporary Chrome extensions for proxy authentication:

```javascript
// Background script for proxy authentication
chrome.webRequest.onAuthRequired.addListener(
  callbackFn,
  { urls: ["<all_urls>"] },
  ["blocking"]
);
```

### 3. Enhanced BaseReferralService (`app/referral_scrapers/base_referral_service.py`)

Updated to support HTTP requests through organization-specific proxies.

#### Changes:

- Constructor accepts `organization_id` parameter
- Initializes proxy service and configuration
- Provides `make_http_request()` method with proxy support
- Automatic proxy injection for all HTTP requests

#### HTTP Request Method:

```python
def make_http_request(self, url: str, method: str = "GET", **kwargs) -> Any:
    if self.proxy_dict:
        kwargs['proxies'] = self.proxy_dict
    return requests.request(method, url, **kwargs)
```

### 4. API Endpoints (`app/service/supabase_api_service.py`)

#### Available Endpoints:

- `GET /api/supabase/proxy/configuration` - Get organization proxy config
- `POST /api/supabase/proxy/configuration` - Create/update proxy config
- `POST /api/supabase/proxy/test` - Test proxy connection

#### Example Usage:

```bash
# Get proxy configuration
curl -X GET "http://localhost:5000/api/supabase/proxy/configuration" \
  -H "X-Organization-ID: your-org-id" \
  -H "Authorization: Bearer your-token"

# Create proxy configuration
curl -X POST "http://localhost:5000/api/supabase/proxy/configuration" \
  -H "X-Organization-ID: your-org-id" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_username": "your_iproyal_username",
    "proxy_password": "your_iproyal_password",
    "proxy_host": "geo.iproyal.com",
    "proxy_type": "http",
    "rotation_enabled": true,
    "session_duration": "15m"
  }'
```

## 🔌 IPRoyal Integration

### Supported Features:

1. **Residential Proxies** - Real residential IP addresses
2. **Sticky Sessions** - Maintain IP for specified duration
3. **Automatic Rotation** - IPRoyal handles IP rotation
4. **Global Locations** - Access to worldwide proxy network
5. **HTTP/HTTPS Support** - Web scraping protocols
6. **SOCKS5 Support** - Alternative protocol option

### Configuration Format:

```python
# HTTP Proxy Format
"http://username_session-sessionid_lifetime-10m:password@geo.iproyal.com:12321"

# SOCKS5 Proxy Format
"socks5://username_session-sessionid_lifetime-10m:password@geo.iproyal.com:32325"
```

### Environment Variables:

```bash
# Optional: Override default IPRoyal settings
IPROYAL_HOST=geo.iproyal.com
IPROYAL_HTTP_PORT=12321
IPROYAL_SOCKS5_PORT=32325
```

## 🚀 Usage Guide

### 1. Database Migration

Run the proxy configuration migration:

```bash
python run_proxy_config_migration.py
```

### 2. Configure Organization Proxy

Use the API endpoint or directly in database:

```python
from app.service.proxy_service import ProxyServiceSingleton

proxy_service = ProxyServiceSingleton.get_instance()
success = proxy_service.create_organization_proxy_config(
    organization_id="your-org-id",
    proxy_username="your_iproyal_username",
    proxy_password="your_iproyal_password",
    proxy_host="geo.iproyal.com",
    rotation_enabled=True,
    session_duration="15m"
)
```

### 3. Update Referral Executor

Ensure organization_id is passed to referral services:

```python
from app.referral_scrapers.referral_executor import ReferralExecutor

executor = ReferralExecutor(
    lead=lead,
    stage_mapping=stage_mapping,
    organization_id=organization_id  # Pass organization ID
)
result = executor.execute()
```

### 4. Test Proxy Configuration

```bash
python test_organization_proxy_system.py
```

## 🔍 Testing

### Automated Tests

The system includes comprehensive tests in `test_organization_proxy_system.py`:

1. **Basic Functionality** - Proxy service methods
2. **Driver Integration** - Selenium WebDriver proxy setup
3. **Service Integration** - BaseReferralService proxy usage
4. **Error Handling** - Invalid configurations and edge cases
5. **URL Format Validation** - Proxy URL generation

### Manual Testing

1. **Proxy Connection Test**:

   ```bash
   curl -X POST "http://localhost:5000/api/supabase/proxy/test" \
     -H "X-Organization-ID: your-org-id"
   ```

2. **IP Address Verification**:

   ```python
   import requests
   from app.service.proxy_service import ProxyServiceSingleton

   proxy_service = ProxyServiceSingleton.get_instance()
   proxies = proxy_service.get_proxy_dict_for_requests("your-org-id")

   response = requests.get("http://httpbin.org/ip", proxies=proxies)
   print(response.json())  # Should show proxy IP
   ```

## ⚠️ Security Considerations

### 1. Credential Storage

- Proxy credentials stored encrypted in database
- No credentials in logs or responses
- Environment variable fallbacks for defaults

### 2. Access Control

- Organization-level proxy isolation
- API endpoint authentication required
- Unique proxy sessions per scraping operation

### 3. Error Handling

- Graceful fallback to no-proxy operation
- Detailed logging for debugging
- No sensitive data in error messages

## 🔧 Maintenance

### Regular Tasks

1. **Monitor Proxy Usage** - Check IPRoyal dashboard for data consumption
2. **Rotate Credentials** - Update proxy passwords periodically
3. **Clean Up Sessions** - IPRoyal handles automatic session cleanup
4. **Performance Monitoring** - Track scraping success rates

### Troubleshooting

#### Common Issues:

1. **Proxy Connection Failed**

   - Check IPRoyal account status and balance
   - Verify credentials in database
   - Test network connectivity

2. **Selenium Proxy Not Working**

   - Check Chrome extension creation
   - Verify proxy authentication format
   - Review Chrome console logs

3. **HTTP Requests Failing**
   - Verify proxy dict format
   - Check requests library version
   - Monitor timeout settings

#### Debug Commands:

```python
# Test proxy service
from app.service.proxy_service import ProxyServiceSingleton
proxy_service = ProxyServiceSingleton.get_instance()
config = proxy_service.get_organization_proxy_config("org-id")
print(config)

# Test connection
test_result = proxy_service.test_proxy_connection("org-id")
print(f"Connection test: {test_result}")
```

## 📈 Performance Optimization

### Best Practices:

1. **Session Duration** - Use 10-30 minute sessions for stability
2. **Concurrent Requests** - Limit simultaneous requests per proxy
3. **Request Delays** - Add delays between requests to avoid detection
4. **Error Retry Logic** - Implement exponential backoff for failures

### Configuration Recommendations:

```python
# Optimal configuration for most use cases
{
    "proxy_type": "http",
    "rotation_enabled": True,
    "session_duration": "15m",  # Good balance of stability and rotation
}
```

## 🔄 Future Enhancements

### Planned Features:

1. **Multi-Proxy Support** - Multiple proxies per organization
2. **Load Balancing** - Distribute requests across proxies
3. **Geographic Targeting** - Location-specific proxy selection
4. **Usage Analytics** - Detailed proxy usage reporting
5. **Auto-Scaling** - Dynamic proxy allocation based on load

### Extension Points:

- Support for other proxy providers
- Advanced session management
- Proxy health monitoring
- Cost optimization algorithms

## 📚 References

- [IPRoyal Documentation](https://docs.iproyal.com/)
- [IPRoyal Python Integration Guide](https://iproyal.com/blog/how-to-use-iproyal-proxies-with-python-requests/)
- [Selenium Proxy Configuration](https://selenium-python.readthedocs.io/api.html)
- [Python Requests Proxy Support](https://docs.python-requests.org/en/latest/user/advanced/#proxies)

## 📞 Support

For technical support or questions:

1. Check this documentation
2. Run the test suite: `python test_organization_proxy_system.py`
3. Review logs for error details
4. Verify IPRoyal account status
5. Contact development team with specific error messages

---

_Last Updated: January 2024_
_Version: 1.0.0_
