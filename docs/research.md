# Research notes

Paste research blocks here. One block per research session, newest first.

# Research: ATS scoring and role breadth (2026-10-20)
## 1. How real ATS rank
- Workday (only vendor with official docs): Skills Match Score uses ML to compare application/resume skills with the requisition's skills; background job rescores hourly (page updated 2026-03-13). https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/candidate-skills-match/ave1604091571278.html
- Workday Candidate Ranking is a recruiter-assigned template, not automatic ranking. https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/candidate-ranking/fan1676398276582.html
- Greenhouse, Lever, iCIMS, Taleo: no primary vendor docs on match scoring found (unverified). One May 2026 blog test: Greenhouse scored against the JD; Workday, Lever, iCIMS did not by default. https://atsverification.com/blog/do-ats-read-cover-letters-workday-greenhouse-lever-tested/
- Recency or role-relevance weighting: unverified for all five.
- Keyword location (skills vs bullets vs titles): unverified; blog claims about Workday favouring exact titles are unsourced.
- 2021 HBS/Accenture survey: 88% of employers agree qualified candidates are screened out for not matching exact JD criteria (opinion survey, not measured rate). https://www.bisnow.com/news/national/top-talent/inflexible-hiring-algorithms-nick-nearly-nine-in-10-qualified-job-candidates-per-study-110266

## 2. Offline scoring methods
| Method | Dependency | Size/speed | Licence | Fit for us |
|---|---|---|---|---|
| TF-IDF / bigrams | scikit-learn | tiny, instant | unverified | Baseline; ngram_range covers phrases |
| BM25 | rank_bm25 or hand-rolled | tiny, instant | unverified | Better length normalisation than TF-IDF |
| Snowball stemming | snowballstemmer 3.1.1 (Jun 2026), pure Python | tiny | BSD-3 https://pypi.org/project/snowballstemmer/ | Cheap fix for manage/managed |
| spaCy lemmatising | spaCy + en_core_web_sm (12.8-13.6 MB) | model download, slower | MIT https://huggingface.co/spacy/en_core_web_sm/tree/main | Overkill; stemming enough |
| required/preferred detection | none | regex | n/a | Heuristic only (unverified) |
| all-MiniLM-L6-v2 | sentence-transformers + torch | ~91 MB weights (secondary source); 22.7M params, 384-dim, 256-token truncation | Apache-2.0 https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | Semantic; heavy dependency |
| bge-small-en-v1.5 | same | size unverified; 33.4M params | MIT https://huggingface.co/BAAI/bge-small-en-v1.5 | Same |
| gte-small | same | 0.07 GB; 33.4M params | MIT https://huggingface.co/thenlper/gte-small | Same |
- Embeddings need torch; macOS arm64 wheel size unverified (old Linux CPU wheels ~150-184 MB). https://discuss.pytorch.org/t/large-cpu-file-size/112709
- CPU inference speed: unverified.
- Stemming, BM25, bigrams add no heavy dependencies.

## 3. Off-topic roles: keep, shorten, drop
- Career blogs (not recruiter research): 3-5 bullets for recent roles, 1-2 for older, title/company/dates line for unrelated jobs. https://www.jobscan.co/blog/how-far-back-should-a-resume-go
- "Additional experience" section for older relevant work: common blog advice (unverified as recruiter practice).
- Students/early-career: one page is the common default, "not a universal rule". https://www.naukri.com/campus/career-guidance/how-long-should-a-resume-be
- Gap handling: unverified. No recruiter study found on whether off-topic roles hurt or help.

## 4. Keyword stuffing
- No peer-reviewed or vendor-documented evidence that ATS penalise keyword density; 1.5% threshold and 25-40% drop claims are unsourced blog figures. https://atsverification.com/blog/resume-keyword-density-how-much-too-much/
- Vendor claim: ATS treat related terms (managed projects / project management) as matches. https://www.mokahr.io/myblog/is-keyword-stuffing-ruining-ats/
- Dense keyword lists reading robotic to humans: opinion only. https://cvowl.com/post/resume-keyword-stuffing-does-it-hurt-your-ats-score
- Hidden white text shows once parsed to plain text (manipulation risk, not density). https://www.jobmentis.com/el/guide/resume-keywords
- Eye-tracking study cited by blogs: not checked (unverified).

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

Rule: a server-side fetch of a URL counts as automated access. "Paste a link" was only allowed for FETCH OK sources; on 2026-10-22 the user chose to accept the ToS risk and read any single pasted link once (spec 8c2). The verdicts above still describe each site's terms.

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
