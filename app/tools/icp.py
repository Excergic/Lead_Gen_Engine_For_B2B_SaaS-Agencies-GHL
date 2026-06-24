from app.tools.models import Channel, ICPId, ICPProfile

CHANNEL_DOMAINS: dict[Channel, list[str]] = {
    Channel.LINKEDIN: ["linkedin.com"],
    Channel.X: ["x.com", "twitter.com"],
    Channel.REDDIT: ["reddit.com"],
    Channel.GOOGLE_MAPS: ["google.com/maps", "maps.google.com"],
    Channel.WEB: [],
}

ICP_PROFILES: list[ICPProfile] = [
    ICPProfile(
        id=ICPId.SAAS_REVENUE,
        name="B2B SaaS — declining or large revenue",
        description=(
            "B2B SaaS companies showing revenue pressure (declining, churn, layoffs) "
            "OR established SaaS with large revenue needing outbound/GTM help."
        ),
        search_queries=[
            # LinkedIn
            "B2B SaaS founder revenue declining churn 2026 site:linkedin.com",
            "enterprise SaaS $10M ARR hiring head of sales site:linkedin.com",
            # X / Twitter
            "B2B SaaS struggling churn need more pipeline site:x.com",
            "SaaS startup GTM outbound help 2026 site:x.com",
            # Reddit
            "SaaS company layoffs GTM struggling advice site:reddit.com/r/SaaS",
            "B2B SaaS revenue declining outbound strategy site:reddit.com/r/startups",
        ],
        channels=[Channel.LINKEDIN, Channel.REDDIT, Channel.X],
    ),
    ICPProfile(
        id=ICPId.MARKETING_AGENCY,
        name="Marketing agency — 5–10 people, >$25K MRR",
        description="Small marketing/outbound agencies doing $25K+ MRR, team of 5–10.",
        search_queries=[
            # LinkedIn
            "marketing agency founder 5 employees $25k MRR site:linkedin.com",
            "outbound agency 10 person team scaling revenue site:linkedin.com",
            # X / Twitter
            "cold email agency founder scaling clients revenue site:x.com",
            "B2B lead gen agency owner growing team site:x.com",
            # Reddit
            "digital marketing agency scaling cold email outreach site:reddit.com",
            "B2B outbound agency owner getting clients advice site:reddit.com/r/agency",
        ],
        channels=[Channel.LINKEDIN, Channel.X, Channel.REDDIT],
    ),
    ICPProfile(
        id=ICPId.B2B_NO_AI,
        name="B2B — marketing team without AI",
        description="B2B companies still running manual marketing/outbound, no AI tooling.",
        search_queries=[
            # LinkedIn
            "B2B company marketing team no AI manual outbound site:linkedin.com",
            "SMB B2B marketing manager hiring SDR no automation site:linkedin.com",
            # X / Twitter
            "B2B sales team manual outbound no AI tools struggling site:x.com",
            "small business marketing no automation need help site:x.com",
            # Reddit
            "looking for outbound help no automation tools site:reddit.com/r/marketing",
            "B2B company manual sales process looking for AI tools site:reddit.com/r/sales",
            # Google Maps
            "local B2B marketing agency site:google.com/maps",
        ],
        channels=[Channel.LINKEDIN, Channel.REDDIT, Channel.X, Channel.GOOGLE_MAPS],
    ),
]
