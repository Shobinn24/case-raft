import time
import urllib.parse
from datetime import datetime, timedelta

import requests
from flask import current_app

from app.extensions import db


class ClioAPIClient:
    """Wraps all Clio Manage API v4 interactions. Handles auth headers and token refresh."""

    def __init__(self, access_token, refresh_token, token_expires_at, user_id):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.user_id = user_id
        self.base_url = current_app.config["CLIO_API_URL"]

    # Refresh 5 minutes early to avoid mid-request expiry during PDF generation
    TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

    def _ensure_valid_token(self):
        """Refresh the access token if it has expired or is about to expire."""
        if self.token_expires_at and datetime.utcnow() >= (self.token_expires_at - self.TOKEN_REFRESH_BUFFER):
            self._refresh_token()

    def _refresh_token(self):
        """Exchange refresh token for a new access token."""
        resp = requests.post(
            current_app.config["CLIO_TOKEN_URL"],
            data={
                "client_id": current_app.config["CLIO_CLIENT_ID"],
                "client_secret": current_app.config["CLIO_CLIENT_SECRET"],
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

        self.access_token = data["access_token"]
        self.token_expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])

        # Update tokens in the database
        from app.models.user import User

        user = User.query.get(self.user_id)
        if user:
            user.clio_access_token = self.access_token
            user.token_expires_at = self.token_expires_at
            if "refresh_token" in data:
                user.clio_refresh_token = data["refresh_token"]
                self.refresh_token = data["refresh_token"]
            db.session.commit()

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
            resp = requests.request(method, url, params=params, headers=headers)
            if resp.status_code == 429 and attempt < self.MAX_RETRIES - 1:
                retry_after = int(resp.headers.get("Retry-After", self.RETRY_DELAY))
                time.sleep(retry_after)
                continue
            if not resp.ok:
                # Include Clio's error detail in the exception message
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:500]
                raise requests.HTTPError(
                    f"{resp.status_code} {resp.reason} for url: {resp.url}\nClio response: {detail}",
                    response=resp,
                )
            return resp.json()

    def get_current_user(self):
        """GET /users/who_am_i.json — returns the authenticated user's info."""
        return self._request("GET", "users/who_am_i.json", params={"fields": "id,name,email"})

    def get_matters(self, status="open", limit=200, page_token=None):
        """GET /matters.json — list matters."""
        params = {
            "fields": "id,display_number,description,status,open_date,close_date,"
                      "pending_date,client{id,name},practice_area{name},"
                      "responsible_attorney{name},matter_stage{name},billable,billing_method",
            "status": status,
            "limit": limit,
            "order": "id(asc)",
        }
        if page_token:
            params["page_token"] = page_token
        return self._request("GET", "matters.json", params=params)

    def get_matter(self, matter_id):
        """GET /matters/{id}.json — single matter with full details."""
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
        """GET /contacts/{id}.json — single contact with details."""
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
        """GET /matters/{id}/related_contacts.json — all contacts linked to a matter.

        Returns opposing parties, opposing counsel, judges, clerks, etc.
        Each related contact includes a relationship.description that defines
        their role on the matter.
        """
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
        """GET /activities.json — time entries and expenses for a matter."""
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
        """GET /bills.json — invoices for a matter."""
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
    # Firm-wide methods (no matter_id — used for productivity reports)
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
        """GET /practice_areas.json — list all practice areas.

        Used to build an id->name lookup since practice_area is a
        second-level nest on bills->matters and only returns defaults (id).
        """
        params = {
            "fields": "id,name",
            "limit": 200,
            "order": "name(asc)",
        }
        return self._request("GET", "practice_areas.json", params=params)

    def get_users(self):
        """GET /users.json — list all firm employees."""
        params = {
            "fields": "id,name,first_name,last_name,email,rate,"
                      "subscription_type,enabled",
            "enabled": "true",
            "limit": 200,
            "order": "name(asc)",
        }
        return self._request("GET", "users.json", params=params)

    def get_all_activities(self, start_date, end_date):
        """GET /activities.json — all time entries firm-wide for a date range.

        start_date/end_date should be ISO date strings like '2026-01-01'.
        """
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
        """GET /bills.json — all invoices firm-wide for a date range.

        issued_after/issued_before should be ISO date strings.
        Includes line_items for per-user revenue attribution.

        NOTE: Clio API only allows 1 level of nested field specification.
        Second-level nests (e.g. activity{user}) return defaults only (id, etag).
        """
        params = {
            "fields": "id,number,issued_at,due_at,state,total,sub_total,"
                      "balance,paid,paid_at,"
                      "start_at,end_at,subject,type,"
                      "matters{id,display_number,practice_area},"
                      "line_items{id,type,total,quantity,price,activity}",
            "issued_after": issued_after,
            "issued_before": issued_before,
            "limit": 200,
            "order": "issued_at(desc)",
        }
        return self._request_all_pages("GET", "bills.json", params=params)

    def get_all_bills_simple(self, issued_after, issued_before):
        """GET /bills.json — lightweight bill fetch for revenue reports.

        Only requests fields needed for practice-area revenue breakdown.
        """
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
