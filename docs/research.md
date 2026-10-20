# Research notes

Paste research blocks here. One block per research session, newest first.

# Research: Groq models (2026-10-20)
- llama-3.3-70b-versatile and llama-3.1-8b-instant were shut down on 2026-08-16 (free and developer tiers). Groq names openai/gpt-oss-120b as the replacement. https://console.groq.com/docs/deprecations
- Production text models left: openai/gpt-oss-120b (131k context, $0.15 in / $0.60 out per 1M tokens, ~500 tok/s) and openai/gpt-oss-20b. https://console.groq.com/docs/models
- json_object mode works on all models; strict json_schema works on gpt-oss-120b/20b. https://console.groq.com/docs/structured-outputs
- No retention of inference data by default; ZDR available in Data Controls. Training terms (Services Agreement/DPA) not yet re-checked. https://console.groq.com/docs/your-data

# Research: blockers (2026-10-19)

## Job sources: access verdict
| Source | Verdict | Why | Use instead |
|---|---|---|---|
| LinkedIn | PASTE TEXT ONLY | User Agreement §8.2 bans scrapers, crawlers, bots and browser plugins; enforced (hiQ, Mantheos); ~95M scrape attempts blocked/day | Job alert emails (daily/weekly, 10 free); follow the posting to the company's ATS page |
| JobStreet / JobsDB (SEEK) | PASTE TEXT ONLY | SG terms (21 Apr 2026) ban data mining, robots, screen scraping without written consent; SEEK API is employer-side only | Saved-search email alerts (unverified) |
| Indeed | PASTE TEXT ONLY | Publisher API closed; ToS (17 Jul 2026) covers API access; anti-scraping tech + Cloudflare | Paste text |
| MyCareersFuture | PASTE until ToU checked | Undocumented public search API (api.mycareersfuture.gov.sg/v2/search); ToU not verified | Check ToU manually first |
| Greenhouse | FETCH OK | Official Job Board API; GET is unauthenticated; no published rate limit | boards-api.greenhouse.io/v1/boards/{token}/jobs |
| Lever | FETCH OK | Official Postings API; postings "may be scraped by third parties"; 1 req/s | api.lever.co/v0/postings/{site}?mode=json |
| Workday | FETCH per link, expect breakage | /wday/cxs endpoint is public but undocumented; can change; maintenance redirects | Fall back to pasting text |

Rule: a server-side fetch of a URL counts as automated access. "Paste a link" is only allowed for FETCH OK sources.

## LLM data handling (free tiers)
| Option | Trains on / retains your data? | Note |
|---|---|---|
| Gemini API free | YES: used to improve products; human review possible | Paid tier: not used. Do not use free tier |
| Mistral Experiment (free) | YES by default | Opt-out toggle available |
| OpenRouter :free | Depends on provider (9/19 free models may train) | Set "no training providers" in privacy settings |
| Groq free | No training; no retention by default; ZDR on request | Preferred hosted option |
| Ollama (local) | Never leaves machine | Weaker models; test quality |
Always strip contact details before sending.

## PDF
WeasyPrint (pure Python, print CSS, no Chrome) as default.
Playwright page.pdf() only if PDF must exactly match the React preview (needs Chromium binaries).

## Biggest non-legal risk
Model may invent facts. The in-app review/edit step is mandatory.

## Sources
- LinkedIn §8.2 analysis: https://contentin.io/blog/linkedin-mcp-terms-of-service/
- hiQ v LinkedIn (9th Cir.): https://www.fr.com/uploads/4878-hiq-labs-inc-v-linkedin-corp-ninth-circuit-september-9-2019.pdf
- hiQ breach ruling: https://www.metaverselaw.com/hiq-v-linkedin-user-agreements-in-the-age-of-data-scraping/
- LinkedIn job alerts: https://www.loopcv.pro/guides/linkedin-job-alerts-setup/
- JobStreet SG terms: https://sg.jobstreet.com/terms
- SEEK API scope: https://jobspipe.dev/blog/seek-api
- Indeed: https://webscraping.ai/blog/how-to-scrape-indeed ; https://www.itechguides.com/?p=871547
- MCF endpoint: https://glama.ai/mcp/servers/@gabrielchua/mcf-mcp ; MCF FAQ: https://static.mycareersfuture.gov.sg/docs/mycareersfuture_sg_user_faqs.pdf
- Greenhouse Job Board API: https://developers.greenhouse.io/job-board
- Lever: https://100hires.com/lever-api.html ; https://apify.com/factpipe/lever-jobs-api
- Workday: https://dev.to/udaninn/workday-job-boards-have-a-json-api-too-its-just-better-hidden-23fl
- PDF: https://apryse.com/blog/html-to-pdf-conversion-methods
- Gemini terms: https://simonwillison.net/2024/Oct/17/gemini-terms-of-service
- Gemini billing: https://discuss.ai.google.dev/t/clarification-on-gemini-api-free-tier-vs-paid-tier-after-billing-activation/96995
- Groq / free API survey: https://aireiter.com/blog/best-free-ai-api
- Mistral: https://help.mistral.ai/en/articles/347617
- OpenRouter: https://www.truefoundry.com/blog/openrouter-free-models-whats-actually-free-and-what-it-costs-you ; https://openrouter.ai/docs/guides/privacy/provider-logging
- Ollama: https://docs.ccs.kaitran.ca/providers/ollama
