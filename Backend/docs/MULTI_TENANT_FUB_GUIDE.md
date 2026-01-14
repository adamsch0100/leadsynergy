# Multi-Tenant FUB API Key System

This guide explains how to use the new multi-tenant FUB API key system that allows each user to have their own FUB API key.

## Overview

The system now supports:

- **Individual API Keys**: Each user can have their own FUB API key
- **API Key Validation**: Keys are tested before being stored
- **Automatic Routing**: Users are redirected to setup if no API key is found
- **Backward Compatibility**: Existing env-based API key still works as fallback

## Backend Implementation

### 1. FUB API Client (`app/database/fub_api_client.py`)

The `FUBApiClient` now accepts an optional API key parameter:

```python
# Old way (still works)
client = FUBApiClient()  # Uses env API key

# New way (multi-tenant)
client = FUBApiClient(user_api_key)  # Uses user's API key
```

### 2. FUB API Key Service (`app/service/fub_api_key_service.py`)

Manages user API keys:

```python
from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton

service = FUBAPIKeyServiceSingleton.get_instance()

# Store and validate API key
success = await service.validate_and_store_api_key(user_id, api_key)

# Get user's API key
api_key = service.get_api_key_for_user(user_id)

# Check if user has API key
has_key = service.has_api_key(user_id)
```

### 3. Middleware (`app/middleware/fub_api_key_middleware.py`)

Protects routes and injects API keys:

```python
from app.middleware.fub_api_key_middleware import fub_api_key_required

@app.route('/api/leads')
@fub_api_key_required
def get_leads():
    # API key is automatically injected into request context
    from app.middleware.fub_api_key_middleware import get_user_fub_api_key

    api_key = get_user_fub_api_key()
    client = FUBApiClient(api_key)
    return client.get_people()
```

### 4. Helper Utilities (`app/utils/fub_helper.py`)

Convenience functions for common patterns:

```python
from app.utils.fub_helper import get_fub_client_for_user

# Get FUB client for specific user
client = get_fub_client_for_user(user_id)
if client:
    leads = client.get_people()
```

## API Endpoints

### POST `/api/setup/fub-api-key`

Store/update a user's FUB API key.

**Request:**

```json
{
  "api_key": "your_fub_api_key",
  "user_id": "user_uuid"
}
```

**Headers:**

```
X-User-ID: user_uuid
Content-Type: application/json
```

**Response:**

```json
{
  "message": "FUB API key configured successfully"
}
```

### GET `/api/setup/fub-api-key-status`

Check if user has a valid API key.

**Query Parameters:**

- `user_id`: User's UUID

**Response:**

```json
{
  "hasApiKey": true,
  "userId": "user_uuid"
}
```

### DELETE `/api/setup/fub-api-key`

Remove a user's API key.

**Query Parameters:**

- `user_id`: User's UUID

## Frontend Implementation

### 1. API Key Setup Component (`components/ApiKeySetup.tsx`)

Form for users to enter their FUB API key:

- Validates API key with backend
- Shows helpful error messages
- Links to FUB documentation

### 2. API Key Guard (`components/ApiKeyGuard.tsx`)

Protects routes and redirects users without API keys:

- Checks API key status on app load
- Redirects to setup page if needed
- Shows loading state during checks

### 3. Setup Page (`app/setup/api-key/page.tsx`)

Dedicated page for API key configuration.

## User Flow

1. **User signs up/logs in**
2. **API Key Guard checks** if user has FUB API key
3. **If no API key**: Redirect to `/setup/api-key`
4. **User enters API key**: Form validates and stores key
5. **If valid**: Redirect to dashboard
6. **All future requests**: Use user's stored API key

## Database Schema

The system uses the existing `user_profiles` table:

```sql
-- Existing column in user_profiles table
fub_api_key TEXT  -- Stores the user's FUB API key
```

## Migration Strategy

### For Existing Users:

1. Keep environment-based API key as fallback
2. Gradually migrate users to individual keys
3. Eventually remove env fallback when all users migrated

### For New Users:

1. Must configure API key during onboarding
2. Cannot access features without valid API key

## Usage Examples

### Protecting a Route

```python
from app.middleware.fub_api_key_middleware import fub_api_key_required
from app.utils.fub_helper import get_fub_client_from_request

@app.route('/api/my-leads')
@fub_api_key_required
def get_my_leads():
    client = get_fub_client_from_request()
    leads = client.get_people()
    return jsonify(leads)
```

### Service with User-Specific API Key

```python
class MyLeadService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.fub_client = get_fub_client_for_user(user_id)

        if not self.fub_client:
            raise ValueError(f"No FUB API key for user {user_id}")

    def sync_leads(self):
        leads = self.fub_client.get_people()
        # Process leads...
```

### Frontend API Key Check

```typescript
// Check if user has API key
const checkApiKey = async (userId: string) => {
  const response = await fetch(
    `/api/setup/fub-api-key-status?user_id=${userId}`
  );
  const data = await response.json();
  return data.hasApiKey;
};

// Setup API key
const setupApiKey = async (userId: string, apiKey: string) => {
  const response = await fetch("/api/setup/fub-api-key", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": userId,
    },
    body: JSON.stringify({ api_key: apiKey, user_id: userId }),
  });

  return response.ok;
};
```

## Error Handling

- **Invalid API Key**: Returns 400 with helpful error message
- **Missing API Key**: Returns 403 with redirect suggestion
- **Authentication Required**: Returns 401 for unauthenticated requests

## Security Considerations

- API keys are stored encrypted in the database
- Keys are validated before storage
- Failed validation attempts are logged
- Users can remove their API keys at any time

## Testing

Run the backend to test the new endpoints:

```bash
cd backend
python main.py
```

The server will start on `http://localhost:5001` with the new API endpoints available.
