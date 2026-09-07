import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from enum import Enum


load_dotenv()

app = FastAPI()

github_token = os.getenv("GITHUB_TOKEN")
github_owner = os.getenv("GITHUB_OWNER")
github_repo = os.getenv("GITHUB_REPO")

github_url = f"https://api.github.com/repos/{github_owner}/{github_repo}/issues"

Headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}"
    }

class CreateIssue(BaseModel):
    title: str  
    body: str | None = None
    labels: list[str] | None = None

class IssueState(str, Enum):
    open = "open"
    closed = "closed"
    all = "all"


@app.post("/issues")
async def create_issue(issue: CreateIssue):
    data = {
        "title": issue.title,
        "body": issue.body,
        "labels": issue.labels
    }
    if issue.title.strip() == "":
        raise HTTPException(status_code=400, detail="invalid payload")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            github_url,
            headers=Headers,
            json=data
        )
    github_issue = response.json()
    if response.status_code == 201:
        # Successfully created
        print(f"Created GitHub issue #{github_issue['number']}: {github_issue['title']}")
        return JSONResponse(
            status_code=201,
            content={
                "number": github_issue['number'], 
                "html_url": github_issue['html_url'],
                "state": github_issue['state'],
                "title": github_issue['title'], 
                "body": github_issue.get('body', ''), 
                "labels": github_issue.get('labels', []), 
                "created_at": github_issue['created_at'], 
                "updated_at": github_issue['updated_at']
            },
            headers={"Location": f"/issues/{github_issue['number']}"}
        )
    elif response.status_code == 401:
        # Invalid/missing GitHub token
        raise HTTPException(status_code=401, detail="Invalid or missing GitHub token")
    else:
        # Some other GitHub error
        raise HTTPException(status_code=response.status_code, detail="Error creating GitHub issue")

@app.get("/issues")
async def get_issues(
    state: IssueState = Query(default=IssueState.open),
    labels: str | None = Query(default=None),
    page: int | None = Query(default=None, ge=1),
    per_page: int = Query(default=30, ge=1, le=100)
):
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            github_url,
            headers=Headers,
            params={
                "state": state.value,
                "labels": labels,
                "page": page,
                "per_page": per_page
            }
        )
    link_header = response.headers.get("Link")
    if response.status_code == 200:
        issues = response.json()
        return JSONResponse(
            status_code=200,
            content=issues,
            headers={"Link": link_header} if link_header else {}
        )
    elif response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid or missing GitHub token")
    else:
        raise HTTPException(status_code=response.status_code, detail="Error fetching GitHub issues")

@app.get("/issues/{issue_number}")
async def get_issue(issue_number: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{github_url}/{issue_number}",
            headers=Headers
        )
    if response.status_code == 200:
        issue = response.json()
        return JSONResponse(
            status_code=200,
            content=issue
        )
    elif response.status_code == 404:
        raise HTTPException(status_code=404, detail="Issue not found")
    else:
        raise HTTPException(status_code=response.status_code, detail="Error fetching GitHub issue")

class UpdateIssue(BaseModel):
    title: str | None = None
    body: str | None = None
    state: str | None = None

@app.patch("/issues/{issue_number}")
async def update_issue(issue_number: int, edit_issue: UpdateIssue):
    if not edit_issue:
        raise HTTPException(status_code=400,detail="At least one field must be provided")
    if edit_issue.state is not None and edit_issue.state not in ["open", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid state value. Must be 'open' or 'closed'.")
    data = {}
    if edit_issue.title is not None:
        data["title"] = edit_issue.title
    if edit_issue.body is not None:
        data["body"] = edit_issue.body
    if edit_issue.state is not None:
        data["state"] = edit_issue.state

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{github_url}/{issue_number}",
            headers=Headers,
            json=data
        )
    if response.status_code == 200:
        updated_issue = response.json()
        return JSONResponse(
            status_code=200,
            content=updated_issue
        )
    elif response.status_code == 404:
        raise HTTPException(status_code=404, detail="Issue not found")
    else:
        raise HTTPException(status_code=response.status_code, detail="Error updating GitHub issue")