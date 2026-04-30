from pydantic import BaseModel


class DevCodeRead(BaseModel):
    email_type: str
    recipient: str
    code: str
    link: str
    captured_at: float
