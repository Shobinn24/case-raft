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

    def _ensure_valid_token(self):
        """Refresh the access token if it has expired."""
        if self.token_expires_at and datetime.utcnow() >= self.token_expires_at:
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

    def _request(self, method, endpoint, params=None):
        """Make an authenticated request to the Clio Manage API."""
        self._ensure_valid_token()
        url = f"{self.base_url}/{endpoint}"
        resp = requests.request(
            method,
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
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
                      "balance,paid,paid_at,due,pending,"
                      "tax_sum,total_tax,"
                      "start_at,end_at,subject,type,"
                      "services_sub_total",
            "matter_id": matter_id,
            "limit": 200,
            "order": "issued_at(desc)",
        }
        return self._request("GET", "bills.json", params=params)
