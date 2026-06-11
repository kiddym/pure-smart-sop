"""ORM 模型包。

导入全部模型以填充 Base.metadata（供 Alembic / create_all 使用）并解析关系。
"""

from __future__ import annotations

from app.models.procedure_asset import ProcedureAsset, ProcedureAssetReference
from app.models.attachment import Attachment
from app.models.audit import FolderAuditLog, ProcedureAuditLog
from app.models.base import Base
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.company import Company
from app.models.company_settings import CompanySettings
from app.models.email_outbox import EmailOutbox
from app.models.field import ProcedureField
from app.models.folder import Folder, FolderSequence
from app.models.heading_learning_event import HeadingLearningEvent
from app.models.heading_rule import HeadingStyleRule
from app.models.node import ProcedureNode
from app.models.notification import Notification, NotificationArm
from app.models.notification_preference import NotificationPreference
from app.models.numbering_profile import NumberingProfile
from app.models.password_reset_token import PasswordResetToken
from app.models.procedure import Procedure
from app.models.push_token import PushToken
from app.models.role import Role
from app.models.sequence import Sequence
from app.models.settings import ProcedureSettings
from app.models.source_docx import ProcedureSourceDocx
from app.models.super_account_relation import SuperAccountRelation
from app.models.team import Team, TeamUser
from app.models.user import User
from app.models.user_invitation import UserInvitation
from app.models.verification_token import VerificationToken

__all__ = [
    "Attachment",
    "Base",
    "BatchImportItem",
    "BatchImportJob",
    "Company",
    "CompanySettings",
    "EmailOutbox",
    "Folder",
    "FolderAuditLog",
    "FolderSequence",
    "HeadingLearningEvent",
    "HeadingStyleRule",
    "Notification",
    "NotificationArm",
    "NotificationPreference",
    "NumberingProfile",
    "PasswordResetToken",
    "Procedure",
    "ProcedureAsset",
    "ProcedureAssetReference",
    "ProcedureAuditLog",
    "ProcedureField",
    "ProcedureNode",
    "ProcedureSettings",
    "ProcedureSourceDocx",
    "PushToken",
    "Role",
    "Sequence",
    "SuperAccountRelation",
    "Team",
    "TeamUser",
    "User",
    "UserInvitation",
    "VerificationToken",
]
