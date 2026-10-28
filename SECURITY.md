# Security policy

## Scope

The 0.5.0 Research Preview runs a local Electron window and a Python API bound to localhost. The desktop shell uses a per-session token, checks loopback Host/Origin, restricts renderer network requests and stores experiments in the user's profile. The application does not require cloud accounts. These controls reduce accidental local exposure; they are not a guarantee against a compromised user account or malicious local software.

## Reporting

Do not publish a suspected credential, exploit or private experiment file in a public issue. Until a dedicated security contact is confirmed, contact the repository owner **Anton Volos** through a private GitHub channel if available. If no private channel is configured, request a secure reporting route without attaching sensitive details to a public issue. No email address is invented here.

Include the affected version, Windows version, reproduction steps and impact. Remove user data and tokens from logs before sharing. Security fixes should be tested against the packaged backend and renderer restrictions before release.

## Support status

0.5.0 is a local Research Preview candidate; the owner has not yet announced a public support or update schedule. The unsigned Windows package and Windows 10 compatibility remain release limitations.
