import re

# Broad capital-intensive / construction exclusion list, matched case-insensitively
# with word boundaries against the notice's title + expertise text.
#
# "build"/"building" were dropped from this list: they used to collide with the
# clearly NGO-relevant phrase "capacity building" (now also an INCLUDE_KEYWORD
# below). Plain "construction" still catches genuine construction/civil-works
# notices (e.g. "construction of school building").
EXCLUDE_KEYWORDS = [
    "construction",
    "civil works",
    "bridge",
    "road",
    "highway",
    "bypass",
    "plant",
    "pipeline",
    "irrigation works",
    "drainage works",
    "dam",
    "power transmission",
    "facility design",
]

_EXCLUDE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in EXCLUDE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Positive NGO-relevance keywords, matched the same way. The site's own Sector
# facet (Education, Health and social protection, Agriculture and natural
# resources, Multisector) doesn't reliably tag cross-cutting notices like
# "community awareness" or "poverty" work, which ADB often files under
# unrelated sectors (e.g. Public sector management, Water and Municipal
# Infrastructure). So instead of pre-filtering by Sector checkbox, every Firm
# notice is scraped and classified here by keyword.
INCLUDE_KEYWORDS = [
    # education / training
    "education", "school", "schooling", "teacher", "training",
    "capacity building", "tutor", "curriculum", "literacy",
    # health and nutrition
    "health", "medical", "nutrition", "healthcare", "vaccine", "disease",
    # women, child, and social welfare
    "gender", "women", "child", "children", "welfare", "social protection",
    "vulnerable",
    # forestry / rural development
    "forestry", "agroforestry", "agriculture", "rural development",
    "livelihood", "farmer", "farming", "pasture",
    # community / poverty / impact work (newly added)
    "community awareness", "community participation", "poverty",
    "social impact", "environmental and social impact",
    "environmental & social impact",
    "multisector",
]

_INCLUDE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in INCLUDE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def is_included(title: str, expertise: str) -> bool:
    """True if the notice's title/expertise suggests NGO-relevant work."""
    text = f"{title} {expertise}"
    return _INCLUDE_PATTERN.search(text) is not None


def is_excluded(title: str, expertise: str) -> bool:
    """True if the notice looks capital-intensive/construction-heavy and should
    be dropped, based on its title and expertise text."""
    text = f"{title} {expertise}"
    return _EXCLUDE_PATTERN.search(text) is not None
