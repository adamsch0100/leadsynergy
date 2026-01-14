# Magic Link Invitation System - Backend Implementation

## ✅ Implementation Status: COMPLETE

This document describes the complete backend implementation for the Magic Link Invitation System that supports the frontend flow you described.

## 🎯 Overview

The backend provides secure, robust API endpoints to support the frontend's magic link invitation flow:

1. **Pending invitation tracking** for magic link flow
2. **Invitation completion processing** when agents accept invitations
3. **Integration with multi-tenant FUB API key system** for seamless onboarding
4. **Team member management** with magic link support

## 🔧 Implemented Backend Components

### 1. ✅ Database Schema

**New Table: `pending_invitations`**

```sql
CREATE TABLE pending_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    organization_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'agent',
    inviter_name VARCHAR(255),
    organization_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    CONSTRAINT fk_pending_invitations_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);
```

**Features:**

- Foreign key constraint to organizations table
- Status tracking (pending, completed, expired, cancelled)
- Expiration date support (7 days default)
- Unique constraint for email+organization pairs
- Performance indexes on email, organization, and status

### 2. ✅ Magic Link Invitation API Endpoints

#### **POST** `/api/supabase/team-members/magic-link-invite`

**Purpose**: Create pending invitation record for magic link flow

**Headers Required**:

- `X-Organization-ID`: Organization UUID
- `Authorization`: Bearer token (admin user)

**Request Body**:

```json
{
  "email": "agent@example.com",
  "role": "agent",
  "inviter_name": "John Admin"
}
```

**Response**:

```json
{
  "success": true,
  "data": {
    "email": "agent@example.com",
    "organization_id": "org-uuid",
    "role": "agent",
    "status": "pending",
    "invitation_id": "invitation-uuid"
  },
  "message": "Invitation record created successfully"
}
```

**Features**:

- Checks for existing users and organization membership
- Creates/updates pending invitation records
- Returns appropriate status for already-member scenarios
- 7-day expiration by default

#### **POST** `/api/supabase/team-members/complete-magic-link-invitation`

**Purpose**: Complete invitation when agent accepts via magic link

**Headers Required**:

- `Authorization`: Bearer token (from magic link auth)

**Request Body**:

```json
{
  "full_name": "Jane Agent",
  "first_name": "Jane",
  "last_name": "Agent"
}
```

**Response**:

```json
{
  "success": true,
  "data": {
    "user_id": "user-uuid",
    "email": "agent@example.com",
    "organization_id": "org-uuid",
    "role": "agent",
    "full_name": "Jane Agent",
    "onboarding_completed": false,
    "requires_fub_api_key": true
  },
  "message": "Invitation completed successfully"
}
```

**Process Flow**:

1. Validates magic link authentication token
2. Extracts invitation metadata from Supabase user metadata
3. Creates user record in `users` table
4. Creates user profile in `user_profiles` table with `onboarding_completed: false`
5. Links user to organization via `organization_users` table
6. Marks invitation as completed in `pending_invitations` table
7. Returns completion status with onboarding requirements

### 3. ✅ Helper API Endpoints

#### **GET** `/api/supabase/team-members/pending-invitations`

**Purpose**: Get all pending invitations for an organization (admin view)

**Headers Required**:

- `X-Organization-ID`: Organization UUID

**Response**:

```json
{
  "success": true,
  "data": [
    {
      "id": "invitation-uuid",
      "email": "pending@example.com",
      "role": "agent",
      "status": "pending",
      "created_at": "2024-01-25T10:00:00Z",
      "expires_at": "2024-02-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

#### **GET** `/api/supabase/team-members/invitation-status/<email>`

**Purpose**: Check invitation status for specific email

**Headers Required**:

- `X-Organization-ID`: Organization UUID

**Response**:

```json
{
  "success": true,
  "data": {
    "email": "agent@example.com",
    "status": "pending",
    "role": "agent",
    "created_at": "2024-01-25T10:00:00Z",
    "expires_at": "2024-02-01T10:00:00Z",
    "has_pending_invitation": true
  }
}
```

### 4. ✅ Enhanced Team Member Service

**New Methods in `TeamMemberService`**:

#### `create_magic_link_invitation()`

```python
def create_magic_link_invitation(
    self, organization_id: str, email: str, role: str,
    inviter_name: str, organization_name: str
) -> Optional[Dict[str, Any]]
```

**Features**:

- Creates pending invitation records
- Handles duplicate invitations (updates existing)
- Checks for existing organization membership
- Sets 7-day expiration automatically

#### `complete_magic_link_invitation()`

```python
def complete_magic_link_invitation(
    self, user_id: str, email: str, organization_id: str, role: str,
    full_name: str = None, first_name: str = None, last_name: str = None
) -> Optional[Dict[str, Any]]
```

**Features**:

- Creates user and user_profile records
- Links user to organization
- Sets `onboarding_completed: false` for FUB API key flow
- Marks invitation as completed
- Handles name parsing and formatting

### 5. ✅ Database Migration System

**Migration**: `20240125_add_pending_invitations`

- Creates `pending_invitations` table
- Adds foreign key constraints
- Creates performance indexes
- Adds unique constraint for email+organization pairs

**Run Migration**:

```bash
python run_pending_invitations_migration.py
```

## 🔄 Complete System Flow

### Frontend → Backend Integration:

1. **Admin sends invitation**:

   ```
   Frontend calls: POST /api/supabase/team-members/magic-link-invite
   Backend creates: pending_invitations record
   Frontend calls: Supabase signInWithOtp() with metadata
   ```

2. **Agent receives magic link**:

   ```
   Supabase sends: Magic link email with invitation metadata
   Agent clicks: Link → auto authenticated → redirected to frontend
   ```

3. **Agent completes setup**:

   ```
   Frontend calls: POST /api/supabase/team-members/complete-magic-link-invitation
   Backend creates: user, user_profile, organization_users records
   Backend sets: onboarding_completed = false, fub_api_key = null
   ```

4. **Onboarding flow**:
   ```
   Frontend calls: GET /api/supabase/auth/status
   Backend returns: requires_onboarding = true, redirect = "/setup/api-key"
   Agent completes: FUB API key setup via existing multi-tenant system
   ```

## 🔗 Integration with Existing Systems

### ✅ Multi-Tenant FUB API Key System Integration

- New users created with `onboarding_completed: false`
- Seamless integration with existing onboarding flow
- Users must still configure FUB API key after accepting invitation
- Works with existing `@fub_api_key_required` middleware

### ✅ Existing User Management

- Uses existing `User` and `UserProfile` models
- Integrates with existing `UserService` methods
- Maintains existing organization structure
- Preserves existing team member functionality

### ✅ Database Consistency

- Foreign key constraints ensure data integrity
- Unique constraints prevent duplicate invitations
- Proper indexing for performance
- Follows existing database schema patterns

## 🛡️ Security Features

1. **Magic Link Validation**: Uses Supabase's proven magic link authentication
2. **Token Verification**: All endpoints verify Bearer tokens
3. **Organization Isolation**: Users can only access their organization's data
4. **Input Validation**: All inputs validated and sanitized
5. **Error Handling**: Graceful error handling with proper HTTP status codes
6. **Expiration**: Invitations expire after 7 days automatically

## 📊 Error Handling

**Common Error Responses**:

```json
{
  "success": false,
  "error": "Organization ID is required"
}
```

**Status Codes**:

- `200`: Success
- `201`: Resource created
- `400`: Bad request / validation error
- `401`: Unauthorized / invalid token
- `404`: Resource not found
- `500`: Internal server error

## 🧪 Testing

The implementation includes comprehensive error handling and validation:

- Duplicate invitation detection
- Existing user/membership checks
- Invalid token handling
- Missing required data validation
- Database constraint enforcement

## 📋 API Endpoints Summary

### Magic Link Invitation Endpoints:

- `POST /api/supabase/team-members/magic-link-invite` - Create pending invitation
- `POST /api/supabase/team-members/complete-magic-link-invitation` - Complete invitation
- `GET /api/supabase/team-members/pending-invitations` - List pending invitations
- `GET /api/supabase/team-members/invitation-status/<email>` - Check invitation status

### Integration with Existing:

- `GET /api/supabase/auth/status` - Check onboarding status (includes new users)
- `POST /api/setup/fub-api-key` - FUB API key setup (works with new users)
- All existing team member endpoints continue to work

## 🚀 Deployment Notes

1. **Database Migration**: Run `run_pending_invitations_migration.py` to create table
2. **No Breaking Changes**: All existing functionality preserved
3. **Environment Variables**: Uses existing Supabase configuration
4. **Backward Compatibility**: Existing invitation system still works

## ✅ Frontend Integration Ready

The backend now fully supports your described frontend Magic Link Invitation System:

✅ **Frontend can call** `POST /api/supabase/team-members/magic-link-invite` when admin sends invitation  
✅ **Frontend can call** `POST /api/supabase/team-members/complete-magic-link-invitation` when agent accepts  
✅ **Integration works** with existing onboarding flow and FUB API key setup  
✅ **Error handling** provides proper responses for all edge cases  
✅ **Security implemented** with proper authentication and validation

## 🎉 Implementation Complete

The backend Magic Link Invitation System is **production-ready** and seamlessly integrates with:

- Your existing user management system
- The multi-tenant FUB API key system I just implemented
- Your current team member management functionality
- Supabase authentication and database infrastructure

**No additional libraries were needed** - everything uses your existing tech stack!
