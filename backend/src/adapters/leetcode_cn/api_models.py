"""LeetCode CN GraphQL API 响应模型。"""

from pydantic import BaseModel, Field


class LcQuestion(BaseModel):
    """userProgressQuestionList 中的题目条目。"""

    frontend_id: str = Field(alias="frontendId")
    title: str
    title_slug: str = Field(alias="titleSlug")
    last_submitted_at: str | None = Field(alias="lastSubmittedAt", default=None)
    question_status: str = Field(alias="questionStatus")
    last_result: str = Field(alias="lastResult", default="")


class LcUserProgressList(BaseModel):
    """userProgressQuestionList 响应体。"""

    total_num: int = Field(alias="totalNum")
    questions: list[LcQuestion]


class LcSubmission(BaseModel):
    """submissionList 中的单条提交。"""

    id: str
    status_display: str = Field(alias="statusDisplay")
    lang: str
    timestamp: str


class LcSubmissionList(BaseModel):
    """submissionList 响应体。"""

    last_key: str | None = Field(alias="lastKey", default=None)
    has_next: bool = Field(alias="hasNext")
    submissions: list[LcSubmission]


class LcPublicProfile(BaseModel):
    """userProfilePublicProfile 中的 profile 字段。"""

    user_slug: str = Field(alias="userSlug")
    real_name: str = Field(alias="realName", default="")
    user_avatar: str = Field(alias="userAvatar", default="")


class LcPublicProfileData(BaseModel):
    """userProfilePublicProfile 响应体。"""

    username: str
    site_ranking: int = Field(alias="siteRanking")
    profile: LcPublicProfile
