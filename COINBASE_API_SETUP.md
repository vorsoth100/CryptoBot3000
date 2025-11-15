# Coinbase API Key Setup for Portainer

## CDP (Cloud Developer Platform) API Keys

When using the new Coinbase CDP API keys with Portainer, you need to ensure the PEM private key is formatted correctly.

### API Key Format

Your API key should look like:
```
organizations/aedbede0-1baf-4c79-882d-cacf323bcd2f/apiKeys/299be78a-f00d-4321-abcd-1234567890ab
```

### API Secret Format (PEM Private Key)

The API secret is a multi-line PEM format EC private key. In Portainer environment variables, you have two options:

#### Option 1: Single Line with Escaped Newlines (Recommended)

Replace all actual newlines with `\n`:

```
-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIBKYJ1D...(your key data)...xYZ\n-----END EC PRIVATE KEY-----\n
```

The bot will automatically convert `\n` to actual newlines.

#### Option 2: Multi-line (if Portainer supports it)

Some versions of Portainer allow multi-line environment variables. Paste the key exactly as downloaded:

```
-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIBKYJ1D...(your key data)...xYZ
-----END EC PRIVATE KEY-----
```

### Portainer Environment Variable Setup

In your Portainer stack configuration, set:

```yaml
environment:
  - COINBASE_API_KEY=organizations/YOUR-ORG-ID/apiKeys/YOUR-KEY-ID
  - COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----\nYOUR-KEY-DATA\n-----END EC PRIVATE KEY-----\n
  - ANTHROPIC_API_KEY=your-claude-api-key
```

### Testing

After deployment, check the container logs. You should see:
```
Authentication type: CDP (Cloud)
Has BEGIN marker: True
Has END marker: True
```

If you see errors about key format, the newlines aren't being preserved correctly. Try the escaped `\n` format.

## Legacy API Keys (Old Format)

If you're using the older legacy API keys (simple alphanumeric strings), they will work automatically:

```yaml
environment:
  - COINBASE_API_KEY=abc123def456...
  - COINBASE_API_SECRET=xyz789uvw012...
```

The bot will automatically detect the key type and use the appropriate authentication method.
