from enum import StrEnum


class WorkspaceKind(StrEnum):
    personal = "personal"
    organization = "organization"


class WorkspaceRole(StrEnum):
    viewer = "viewer"
    member = "member"
    manager = "manager"
    admin = "admin"
    owner = "owner"


class MembershipStatus(StrEnum):
    invited = "invited"
    active = "active"
    departed = "departed"


class CompanyType(StrEnum):
    client = "client"
    partner = "partner"
    vendor = "vendor"
    government = "government"
    prospect = "prospect"
    other = "other"


class RelationshipType(StrEnum):
    client = "client"
    partner = "partner"
    vendor = "vendor"
    colleague = "colleague"
    government = "government"
    other = "other"


class ContactVisibility(StrEnum):
    private = "private"
    team = "team"


class ContactStatus(StrEnum):
    active = "active"
    follow_up = "follow_up"
    needs_attention = "needs_attention"
    drifting = "drifting"
    archived = "archived"


class FactCategory(StrEnum):
    preference = "preference"
    dislike = "dislike"
    interest = "interest"
    personal = "personal"
    professional = "professional"
    communication_style = "communication_style"
    ambition = "ambition"
    family = "family"
    risk = "risk"
    other = "other"


class FactSource(StrEnum):
    manual = "manual"
    note = "note"
    voice = "voice"
    email = "email"
    calendar = "calendar"
    crm = "crm"
    ai = "ai"


class InteractionKind(StrEnum):
    note = "note"
    meeting = "meeting"
    call = "call"
    email = "email"
    message = "message"
    event = "event"
    introduction = "introduction"
    gift = "gift"
    other = "other"


class InteractionDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"
    mutual = "mutual"


class InteractionSource(StrEnum):
    manual = "manual"
    voice = "voice"
    gmail = "gmail"
    outlook = "outlook"
    google_calendar = "google_calendar"
    ms_calendar = "ms_calendar"
    crm = "crm"
    import_ = "import"


class AiStatus(StrEnum):
    none = "none"
    pending = "pending"
    processed = "processed"
    failed = "failed"
    skipped = "skipped"


class TaskStatus(StrEnum):
    open = "open"
    done = "done"
    snoozed = "snoozed"
    cancelled = "cancelled"


class TaskSource(StrEnum):
    manual = "manual"
    ai = "ai"
    voice = "voice"
    cadence = "cadence"


class OpportunityStatus(StrEnum):
    open = "open"
    won = "won"
    lost = "lost"
    on_hold = "on_hold"


class OpportunityRole(StrEnum):
    decision_maker = "decision_maker"
    influencer = "influencer"
    champion = "champion"
    blocker = "blocker"
    user = "user"
    other = "other"


class EdgeKind(StrEnum):
    knows = "knows"
    reports_to = "reports_to"
    works_with = "works_with"
    introduced_by = "introduced_by"
    former_colleague = "former_colleague"
    other = "other"


class InsightKind(StrEnum):
    follow_up = "follow_up"
    at_risk = "at_risk"
    opportunity_signal = "opportunity_signal"
    introduction_path = "introduction_path"
    trend = "trend"
    briefing = "briefing"
    common_ground = "common_ground"


class InsightStatus(StrEnum):
    new = "new"
    seen = "seen"
    acted = "acted"
    dismissed = "dismissed"
    expired = "expired"


class InsightSeverity(StrEnum):
    info = "info"
    notice = "notice"
    warning = "warning"


class CaptureStatus(StrEnum):
    uploaded = "uploaded"
    transcribing = "transcribing"
    transcribed = "transcribed"
    extracting = "extracting"
    proposed = "proposed"
    confirmed = "confirmed"
    discarded = "discarded"
    failed = "failed"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    dead = "dead"


class IntegrationProvider(StrEnum):
    gmail = "gmail"
    outlook = "outlook"
    google_calendar = "google_calendar"
    ms_calendar = "ms_calendar"
    salesforce = "salesforce"
    hubspot = "hubspot"
    slack = "slack"
    linkedin = "linkedin"


class IntegrationStatus(StrEnum):
    connected = "connected"
    needs_reauth = "needs_reauth"
    disabled = "disabled"
    error = "error"


class SentimentLabel(StrEnum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    mixed = "mixed"


class Band(StrEnum):
    strong = "strong"
    steady = "steady"
    weak = "weak"
    drifting = "drifting"
