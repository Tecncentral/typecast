# Access and unattended readiness

Verified locally November 14: fresh dev checkout, 13 baseline tests pass without credentials. The original GitHub state contains mock implementations; live integrations are not verified. No Typecast toolkit or sponsor data download was found in the Downloads inventory. Credentials were not printed or copied. Existing model keys, if any, do not establish permission to use licensed data.

## Provisioning contract
- A: documented Matterport access, a permitted model id, panorama/sweep access; SDK key only if embedding requires it.
- B: sponsor CoStar data and schema/docs, Vexcel access, verified join, data terms.
- C: chosen model/provider access and LangSmith if enabled. Use a provider already authorized by the team; don't guess endpoints or reuse unrelated app credentials.
- D: approved Matterport embed setup; Photon only after core web flow works and access is available.

Each machine owns its private .env and cache/. Share only through a sponsor-permitted private channel or a team-local authenticated service. Never commit the data or put a local cache behind a public URL. Until private transfer/access is verified, record live integration BLOCKED, continue mocks and adapter/error work, and do not claim unattended live readiness.

## Launch
Follow your owner handoff on the corresponding lane branch, merge origin/dev, create/activate .venv, install requirements.lock.txt and run `python scripts/verify.py`. Copy .env.example to .env privately. The app loads this root .env while preserving explicit shell values. Restart after changing mode: adapters currently read mode at import time.

The team must already have started each coding agent in its own checkout/session. These files do not create a persistent agent runner or keep laptops awake. No teammate sessions or collaborator invitations have been started by this repository change. Agents without push access can still fork and prepare PRs. Only an already authenticated integration captain may merge into dev.

## Honest release gate
Before saying live-ready: one matching property/interior/aerial demonstrated, three picks if supported by actual data, browser image URLs, genuine execution trace/events, working same-thread follow-up, measured timings and documented null/failure behavior. Before submission: polished two-minute demo, public repo free of data/secrets, one main track, real eligibility evidence, Discord names and a human submits. No automatic owner outreach.
