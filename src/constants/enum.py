from enum import StrEnum


class UserRole(StrEnum):
    USER="user"
    ADMIN="admin"
    SUPPORT_AGENT="support_agent"
    TEAM_LEAD="team_lead"

class ContactMode(StrEnum):
    EMAIL = "email"
    PORTAL = "portal"
