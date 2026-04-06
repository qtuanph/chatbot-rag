# Security Policy

## Supported Versions

Security fixes are applied on the latest `main` branch.

## Reporting a Vulnerability

Please report vulnerabilities privately:

- Open a private security advisory on GitHub (preferred), or
- Email the maintainer directly.

Do not post exploit details in public issues.

Include:

- Affected component and version/commit
- Reproduction steps
- Impact assessment
- Suggested remediation (if available)

## Response Process

1. Acknowledge report within 72 hours.
2. Validate and triage severity.
3. Prepare and test patch.
4. Coordinate disclosure and release notes.

## Scope

In scope:

- Authentication and authorization
- Data leaks (PII, tokens, secrets)
- RCE, injection, path traversal
- SSRF and unsafe outbound calls
- Container and deployment misconfigurations

Out of scope:

- Social engineering
- Denial of service requiring unrealistic resources
- Issues in unsupported forks

## Safe Harbor

Good-faith security research that avoids data destruction, service disruption, or privacy violations is welcome.
