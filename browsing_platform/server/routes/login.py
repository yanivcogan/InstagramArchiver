import traceback

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from browsing_platform.server.services.password_authenticator import login_with_password
from browsing_platform.server.services.token_manager import remove_token

router = APIRouter(
    prefix="/login",
    tags=["login"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


class LoginCredentialsPass(BaseModel):
    email: str
    password: str


@router.post('/')
async def login_with_pass(data: LoginCredentialsPass):
    try:
        login_res = login_with_password(data.email, data.password)
        return login_res
    except Exception as e:
        print(traceback.format_exc())
        return {"error": str(e)}


@router.post('/logout')
async def logout(request: Request):
    """verify that user has a valid session"""
    print(request.cookies)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401)
    token = auth_header.split(":")[1]
    if not token:
        raise HTTPException(status_code=401)
    remove_token(token)
    return True
