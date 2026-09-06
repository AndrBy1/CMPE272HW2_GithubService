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

