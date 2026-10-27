from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)
