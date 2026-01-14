"""
Try to decode Agent Pronto tracking links to find the real destination
"""
import base64
import urllib.parse
import re

# Example tracking link from the email
tracking_link = "http://lnx.agentpronto.com/ls/click?upn=u001.KMNQo3v4HJYgjbjQDWNvpOyZn3FXai7LciMTrkNyVjp3I2ViCD873Nvximn7eKzmn01eUMLRVt1V2j3-2BZsBNwALt5jZ-2F1ko1fxAugFWrrl-2BITq4wREPsRHqSMzd-2BGsZSkue8-2FHiQYcZh0DbIlN9lLz12vYvsaqLsZJfq64I1B2NBY1xf9BdSSgjaYAY-2Fu09RWLJNjoue3q83h-2BBcZPxJOn3RqDOoE0d-2FTMMLyD89vVv-2BQmLsmpxU7sYiBapBIt1C0qCgW4ixA7ZqlE8u7Ydg7sOQo13uGqlyHJ-2Fy97JQoXjQK5pPXWak-2Fgrl2oOCDMjKWmDLJR5JasYlzXWFY4RzMdZmeZfXkpNHA1rdKwu4UCsfwIi0cV2hlqAeW4YTryozSVAliHfUCPaAtlc4tOzVUQqkDXGZ-2BMkQ7uyvriWDmv5FUMnYwDHPCw3bW4TA8zcX-2BYgGWrpnNgxUQEPEWuZkvg-3D-3DYo34_dRWfjBGbdTQrH9MplhqgkZtaW3srVY-2BEqacNZyKpVH8QnYsu87VocWYcWweFm5yBONhTSTUFlPSUe5BONW3Rf0oOVS3HSHFeqx08Bdf0cE95yTr02yvzjfsfQPDgkRpYrET7PX4C-2FYcWm2Jag-2BH63D8AD4JAFYgfmMkZwWyVuEYclFfGHryJOOIU1hhRRkv3usHAsn-2FS5S4RyD-2BLLWXZBg-3D-3D"

print("=" * 60)
print("Trying to decode Agent Pronto tracking link")
print("=" * 60)

# Parse the URL
parsed = urllib.parse.urlparse(tracking_link)
params = urllib.parse.parse_qs(parsed.query)

print(f"\nHost: {parsed.netloc}")
print(f"Path: {parsed.path}")
print(f"\nParameters:")
for key, value in params.items():
    print(f"  {key}: {value[0][:100]}...")

# Try to decode the 'upn' parameter
upn = params.get('upn', [''])[0]

print(f"\n\nFull UPN value ({len(upn)} chars):")
print(upn[:200] + "...")

# The UPN appears to have format: u001.{base64_payload}
# Try various decodings
print("\n" + "=" * 60)
print("Attempting various decodings:")
print("=" * 60)

# First, URL decode (convert -2B back to +, -2F back to /, etc.)
url_decoded = urllib.parse.unquote(upn.replace('-2B', '+').replace('-2F', '/').replace('-3D', '='))
print(f"\n1. URL decoded: {url_decoded[:200]}...")

# Try base64 decode on the part after 'u001.'
if '.' in url_decoded:
    parts = url_decoded.split('.', 1)
    if len(parts) > 1:
        payload = parts[1]
        print(f"\n2. Payload after 'u001.': {payload[:100]}...")

        # Try base64 decode
        try:
            # Standard base64
            decoded = base64.b64decode(payload + '==')
            print(f"\n3. Base64 decoded (raw bytes): {decoded[:100]}")
        except Exception as e:
            print(f"\n3. Base64 decode failed: {e}")

        try:
            # URL-safe base64
            decoded = base64.urlsafe_b64decode(payload + '==')
            print(f"\n4. URL-safe base64 decoded: {decoded[:100]}")
        except Exception as e:
            print(f"\n4. URL-safe base64 decode failed: {e}")

# The suffix after the main payload (after underscore) might be a signature
# Let's see if we can identify the structure
print("\n" + "=" * 60)
print("Link structure analysis:")
print("=" * 60)

# Count underscores and other patterns
underscore_parts = upn.split('_')
print(f"Parts split by '_': {len(underscore_parts)}")
for i, part in enumerate(underscore_parts):
    print(f"  Part {i}: {part[:80]}...")

print("\n" + "=" * 60)
print("Conclusion:")
print("=" * 60)
print("""
The tracking links appear to be encrypted/signed, making it impossible to
extract the real destination URL without actually clicking the tracking link.

Options:
1. Accept that we need to click the tracking link BEFORE anything else does
2. See if Agent Pronto supports alternative login methods (password, OAuth)
3. Request Agent Pronto to provide non-tracking magic links

For now, the best approach is to:
- Request the magic link
- Immediately start polling for the email (before user sees it)
- Navigate to it as fast as possible
""")
