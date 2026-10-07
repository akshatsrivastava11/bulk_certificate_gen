"""
Marshmallow Schemas for request validation and serialization.
"""
import re
from datetime import date
from marshmallow import Schema, fields, validates, validates_schema, ValidationError, pre_load


class RecipientSchema(Schema):
    """Schema for a single recipient in a certificate request."""
    full_name = fields.Str(required=True, metadata={"description": "Recipient's full name"})
    email = fields.Email(required=True, metadata={"description": "Recipient's email address"})
    course_name = fields.Str(load_default=None, allow_none=True)
    grade = fields.Str(load_default=None, allow_none=True)
    extra_fields = fields.Dict(load_default=None, allow_none=True)

    @validates("full_name")
    def validate_full_name(self, value):
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValidationError("full_name must be at least 2 characters long.")
        if len(stripped) > 255:
            raise ValidationError("full_name must be at most 255 characters long.")
        if not re.match(r"^[\w\s\-'.]+$", stripped, re.UNICODE):
            raise ValidationError("full_name contains invalid characters.")
        return stripped

    @pre_load
    def strip_strings(self, data, **kwargs):
        result = {}
        for key, value in data.items():
            result[key] = value.strip() if isinstance(value, str) else value
        return result


class CreateJobSchema(Schema):
    """Schema for creating a bulk certificate generation job."""
    title = fields.Str(required=True)
    description = fields.Str(load_default=None, allow_none=True)
    event_name = fields.Str(required=True)
    event_date = fields.Date(
        load_default=None,
        allow_none=True,
        format="%Y-%m-%d",
        metadata={"description": "ISO 8601 date, e.g. 2024-06-15"},
    )
    issued_by = fields.Str(required=True)
    recipients = fields.List(
        fields.Nested(RecipientSchema),
        required=True,
        metadata={"description": "List of certificate recipients"},
    )

    @validates("title")
    def validate_title(self, value):
        if len(value.strip()) < 3:
            raise ValidationError("title must be at least 3 characters long.")
        if len(value.strip()) > 255:
            raise ValidationError("title must be at most 255 characters long.")

    @validates("issued_by")
    def validate_issued_by(self, value):
        if len(value.strip()) < 2:
            raise ValidationError("issued_by must be at least 2 characters long.")

    @validates("recipients")
    def validate_recipients(self, value):
        if len(value) == 0:
            raise ValidationError("At least one recipient is required.")
        from flask import current_app
        max_r = current_app.config.get("MAX_RECIPIENTS_PER_JOB", 1000)
        if len(value) > max_r:
            raise ValidationError(
                f"Too many recipients. Maximum allowed per job is {max_r}."
            )

    @validates_schema
    def check_unique_emails(self, data, **kwargs):
        recipients = data.get("recipients", [])
        emails = [r.get("email", "").lower() for r in recipients if r.get("email")]
        if len(emails) != len(set(emails)):
            raise ValidationError(
                {"recipients": ["Duplicate email addresses are not allowed within a single job."]}
            )


class JobFilterSchema(Schema):
    """Query parameters for listing/filtering jobs."""
    status = fields.Str(load_default=None, allow_none=True)
    page = fields.Int(load_default=1)
    per_page = fields.Int(load_default=20)

    @validates("page")
    def validate_page(self, value):
        if value < 1:
            raise ValidationError("page must be >= 1.")

    @validates("per_page")
    def validate_per_page(self, value):
        if value < 1 or value > 100:
            raise ValidationError("per_page must be between 1 and 100.")
