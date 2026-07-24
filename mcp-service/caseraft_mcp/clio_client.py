"""Clio Manage API v4 client, ported from backend/app/services/clio_client.py.

Differences from the Flask original, and nothing else:
  * Config comes from caseraft_mcp.config.settings instead of Flask
    current_app.config.
  * Token refresh persists rotated tokens back to the users table through
    this service's own SQLAlchemy session (same table, same Fernet
    encryption via the EncryptedText column type), matching the Flask
    write-back behavior exactly.
  * No Slack alerting layer (the Flask app keeps that); failures log and
    raise instead.
  * No dev mock-data branches (mock_clio_data stays Flask-side; tests here
    mock at the HTTP layer).

Retry behavior is identical: 429s honor Retry-After, transient connection
errors retry once, everything else raises with Clio's error detail attached.
"""

import logging
import time
import urllib.parse
from datetime import datetime, timedelta

import requests

from .config import settings
from .db import User, session_scope

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = (10, 30)  # (connect, read) seconds


class ClioAPIClient:
    """Wraps Clio Manage API v4 interactions. Handles auth headers and token refresh."""

    def __init__(self, access_token, refresh_token, token_expires_at, user_id):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.user_id = user_id
        self.base_url = settings.clio_api_url

    # Refresh 5 minutes early to avoid mid-request expiry
    TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

    def _ensure_valid_token(self):
        """Refresh the access token if it has expired or is about to expire."""
        if self.token_expires_at and datetime.utcnow() >= (
            self.token_expires_at - self.TOKEN_REFRESH_BUFFER
        ):
            self._refresh_token()

    def _refresh_token(self):
        """Exchange refresh token for a new access token and WRITE the rotated
        tokens back to the users table (encrypted), like the Flask path does."""
        try:
            resp = requests.post(
                settings.clio_token_url,
                data={
                    "client_id": settings.clio_client_id,
                    "client_secret": settings.clio_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception(
                "Clio OAuth token refresh failed (user_id=%s)", self.user_id
            )
            raise

        access_token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not access_token or not isinstance(expires_in, (int, float)):
            logger.error(
                "Clio token refresh returned malformed payload keys=%s (user_id=%s)",
                list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                self.user_id,
            )
            raise RuntimeError(
                "Clio token refresh returned an unexpected payload "
                "(missing access_token or expires_in)"
            )
        self.access_token = access_token
        self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        rotated_refresh = data.get("refresh_token")
        if rotated_refresh:
            self.refresh_token = rotated_refresh

        # Persist rotated tokens (EncryptedText encrypts on write)
        if self.user_id is not None:
            with session_scope() as session:
                user = session.get(User, self.user_id)
                if user:
                    user.clio_access_token = self.access_token
                    user.token_expires_at = self.token_expires_at
                    if rotated_refresh:
                        user.clio_refresh_token = rotated_refresh

    MAX_RETRIES = 2
    RETRY_DELAY = 2  # seconds

    def _request(self, method, endpoint, params=None):
        """Make an authenticated request to the Clio Manage API.

        Automatically retries once on 429 (rate limit) responses.
        """
        self._ensure_valid_token()
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = requests.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=HTTP_TIMEOUT,
                )
            except (requests.ConnectionError, requests.Timeout):
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                raise
            if resp.status_code == 429 and attempt < self.MAX_RETRIES - 1:
                retry_after = int(resp.headers.get("Retry-After", self.RETRY_DELAY))
                time.sleep(retry_after)
                continue
            if not resp.ok:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:500]
                raise requests.HTTPError(
                    f"{resp.status_code} {resp.reason} for url: {resp.url}\n"
                    f"Clio response: {detail}",
                    response=resp,
                )
            return resp.json()

    def get_current_user(self):
        """GET /users/who_am_i.json with the firm (account) name included."""
        return self._request(
            "GET",
            "users/who_am_i.json",
            params={"fields": "id,name,email,time_zone,account{id,name}"},
        )

    def get_matters(self, status="open", limit=200, page_token=None, query=None):
        """GET /matters.json (optional full-text query filter)."""
        params = {
            "fields": "id,display_number,description,status,open_date,close_date,"
                      "pending_date,client{id,name},practice_area{name},"
                      "responsible_attorney{name},matter_stage{name},billable,billing_method",
            "status": status,
            "limit": limit,
            "order": "id(asc)",
        }
        if query:
            params["query"] = query
        if page_token:
            params["page_token"] = page_token
        return self._request("GET", "matters.json", params=params)

    def search_contacts(self, query, limit=25):
        """GET /contacts.json filtered by Clio's full-text query param."""
        params = {
            "fields": "id,name,first_name,last_name,type,title,"
                      "primary_email_address,primary_phone_number,"
                      "company{name},is_client",
            "query": query,
            "limit": limit,
            "order": "name(asc)",
        }
        return self._request("GET", "contacts.json", params=params)

    def get_matter(self, matter_id):
        """GET /matters/{id}.json"""
        params = {
            "fields": "id,display_number,description,status,open_date,close_date,"
                      "pending_date,client{id,name,first_name,last_name,type,"
                      "primary_email_address,primary_phone_number},"
                      "practice_area{name},responsible_attorney{name},"
                      "originating_attorney{name},matter_stage{name},"
                      "billable,billing_method,location,client_reference,"
                      "created_at,updated_at",
        }
        return self._request("GET", f"matters/{matter_id}.json", params=params)

    def get_contact(self, contact_id):
        """GET /contacts/{id}.json"""
        params = {
            "fields": "id,name,first_name,middle_name,last_name,type,title,prefix,"
                      "date_of_birth,primary_email_address,secondary_email_address,"
                      "primary_phone_number,secondary_phone_number,"
                      "addresses{street,city,province,postal_code,country,name},"
                      "email_addresses{address,name},"
                      "phone_numbers{number,name},"
                      "company{name},is_client,created_at,updated_at",
        }
        return self._request("GET", f"contacts/{contact_id}.json", params=params)

    def get_related_contacts(self, matter_id):
        """GET /matters/{id}/related_contacts.json"""
        params = {
            "fields": "id,name,first_name,last_name,type,title,prefix,"
                      "primary_email_address,primary_phone_number,is_matter_client,"
                      "email_addresses{address,name},"
                      "phone_numbers{number,name},"
                      "addresses{street,city,province,postal_code,country,name},"
                      "company{name},"
                      "relationship{id,description}",
            "limit": 200,
            "order": "id(asc)",
        }
        return self._request(
            "GET", f"matters/{matter_id}/related_contacts.json", params=params
        )

    def get_activities(self, matter_id):
        """GET /activities.json for a matter."""
        params = {
            "fields": "id,type,date,quantity_in_hours,rounded_quantity_in_hours,"
                      "price,total,note,flat_rate,billed,on_bill,non_billable,"
                      "non_billable_total,no_charge,"
                      "user{name},"
                      "activity_description{name},"
                      "matter{id}",
            "matter_id": matter_id,
            "limit": 200,
            "order": "date(desc)",
        }
        return self._request("GET", "activities.json", params=params)

    def get_bills(self, matter_id):
        """GET /bills.json for a matter."""
        params = {
            "fields": "id,number,issued_at,due_at,state,total,sub_total,"
                      "balance,paid,paid_at,"
                      "tax_sum,total_tax,"
                      "start_at,end_at,subject,type",
            "matter_id": matter_id,
            "limit": 200,
            "order": "issued_at(desc)",
        }
        return self._request("GET", "bills.json", params=params)

    # ------------------------------------------------------------------
    # Firm-wide methods (used by the Phase 2 report tools)
    # ------------------------------------------------------------------

    def _request_all_pages(self, method, endpoint, params=None):
        """Fetch all pages of a paginated Clio API response."""
        params = dict(params or {})
        all_data = []
        while True:
            resp = self._request(method, endpoint, params)
            all_data.extend(resp.get("data", []))
            paging = resp.get("meta", {}).get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break
            parsed = urllib.parse.urlparse(next_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            page_token = query_params.get("page_token", [None])[0]
            if not page_token:
                break
            params["page_token"] = page_token
        return all_data

    def get_practice_areas(self):
        """GET /practice_areas.json"""
        params = {
            "fields": "id,name",
            "limit": 200,
            "order": "name(asc)",
        }
        return self._request("GET", "practice_areas.json", params=params)

    def get_users(self):
        """GET /users.json (all enabled firm employees)."""
        params = {
            "fields": "id,name,first_name,last_name,email,rate,"
                      "subscription_type,enabled",
            "enabled": "true",
            "limit": 200,
            "order": "name(asc)",
        }
        return self._request("GET", "users.json", params=params)

    def get_all_activities(self, start_date, end_date):
        """GET /activities.json firm-wide for a date range."""
        params = {
            "fields": "id,type,date,quantity_in_hours,rounded_quantity_in_hours,"
                      "price,total,note,non_billable,non_billable_total,"
                      "no_charge,billed,on_bill,"
                      "user{id,name},"
                      "activity_description{name},"
                      "matter{id,display_number},"
                      "bill{id}",
            "type": "TimeEntry",
            "start_date": start_date,
            "end_date": end_date,
            "limit": 200,
            "order": "date(desc)",
        }
        return self._request_all_pages("GET", "activities.json", params=params)

    def get_all_bills(self, issued_after, issued_before):
        """GET /bills.json firm-wide for a date range."""
        params = {
            "fields": "id,number,issued_at,due_at,state,total,sub_total,"
                      "balance,paid,paid_at,"
                      "start_at,end_at,subject,type,"
                      "matters{id,display_number,practice_area}",
            "issued_after": issued_after,
            "issued_before": issued_before,
            "limit": 200,
            "order": "issued_at(desc)",
        }
        return self._request_all_pages("GET", "bills.json", params=params)

    def get_matters_with_trust_data(self):
        """GET /matters.json with trust balances, thresholds, custom fields."""
        params = {
            "fields": "id,display_number,description,status,"
                      "client{id,name},"
                      "account_balances{id,balance,type,name,currency_id},"
                      "evergreen_retainer,"
                      "custom_field_values{id,field_name,value}",
            "status": "open",
            "limit": 200,
            "order": "id(asc)",
        }
        return self._request_all_pages("GET", "matters.json", params=params)

    # ------------------------------------------------------------------
    # New in the MCP service (not in the Flask client): daily digest inputs.
    # Param names follow Clio API v4 index-filter conventions; the plan's
    # Phase 0 follow-up (b) covers verifying them (and scopes) on the first
    # live call.
    # ------------------------------------------------------------------

    def list_tasks(self, assignee_id=None, due_after=None, due_before=None,
                   complete=None, limit=200):
        """GET /tasks.json with optional assignee / due-date-range / complete
        filters. due_after and due_before are ISO date strings."""
        params = {
            "fields": "id,name,description,status,priority,due_at,"
                      "assignee{id,name},matter{id,display_number},"
                      "created_at,updated_at",
            "limit": limit,
            "order": "due_at(asc)",
        }
        if assignee_id is not None:
            params["assignee_id"] = assignee_id
            params["assignee_type"] = "User"
        if due_after:
            params["due_at_from"] = due_after
        if due_before:
            params["due_at_to"] = due_before
        if complete is not None:
            params["complete"] = "true" if complete else "false"
        return self._request("GET", "tasks.json", params=params)

    def list_calendar_entries(self, start, end, limit=200):
        """GET /calendar_entries.json for a datetime range. start and end are
        ISO 8601 datetime strings (Clio's from/to window filters)."""
        params = {
            "fields": "id,summary,description,start_at,end_at,all_day,"
                      "location,matter{id,display_number}",
            "from": start,
            "to": end,
            "limit": limit,
            "order": "start_at(asc)",
        }
        return self._request("GET", "calendar_entries.json", params=params)

    def get_all_bills_simple(self, issued_after, issued_before):
        """GET /bills.json lightweight fetch for revenue reports."""
        params = {
            "fields": "id,number,issued_at,due_at,state,total,sub_total,"
                      "balance,paid,paid_at,"
                      "matters{id,display_number,practice_area}",
            "issued_after": issued_after,
            "issued_before": issued_before,
            "limit": 200,
            "order": "issued_at(desc)",
        }
        return self._request_all_pages("GET", "bills.json", params=params)
