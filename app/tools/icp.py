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
            "B2B SaaS founder revenue declining churn 2026 site:linkedin.com",
            "SaaS company layoffs GTM struggling site:reddit.com/r/SaaS",
            "Series A B2B SaaS need more pipeline outbound site:x.com",
            "enterprise SaaS $10M ARR hiring head of sales site:linkedin.com",
        ],
        channels=[Channel.LINKEDIN, Channel.REDDIT, Channel.X],
    ),
    ICPProfile(
        id=ICPId.MARKETING_AGENCY,
        name="Marketing agency — 5–10 people, >$25K MRR",
        description="Small marketing/outbound agencies doing $25K+ MRR, team of 5–10.",
        search_queries=[
            "marketing agency founder 5 employees $25k MRR site:linkedin.com",
            "outbound agency 10 person team case study site:linkedin.com",
            "digital marketing agency scaling cold email site:reddit.com",
            "B2B lead gen agency owner site:x.com",
        ],
        channels=[Channel.LINKEDIN, Channel.X, Channel.REDDIT],
    ),
    ICPProfile(
        id=ICPId.B2B_NO_AI,
        name="B2B — marketing team without AI",
        description="B2B companies still running manual marketing/outbound, no AI tooling.",
        search_queries=[
            "B2B company marketing team no AI manual outbound site:linkedin.com",
            "looking for outbound help no automation site:reddit.com/r/marketing",
            "SMB B2B marketing manager hiring SDR no AI tools site:linkedin.com",
            "local B2B marketing agency site:google.com/maps",
        ],
        channels=[Channel.LINKEDIN, Channel.REDDIT, Channel.GOOGLE_MAPS],
    ),
]
