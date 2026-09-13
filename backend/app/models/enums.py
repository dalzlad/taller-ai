from enum import Enum


class DiagnosticStatus(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"


class MediaType(str, Enum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class DiagnosticEvidenceType(str, Enum):
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


class WorkOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
