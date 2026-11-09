import datetime as dt

from django.db import models
from rest_framework import serializers

from .jalali import parse_date_string, to_jalali_str


class JalaliDateField(serializers.DateField):
    default_error_messages = {
        "invalid": "Invalid date. Use a Jalali date such as 1405-02-15.",
    }

    def to_representation(self, value):
        if not value:
            return None
        return to_jalali_str(value)

    def to_internal_value(self, value):
        if isinstance(value, dt.datetime):
            self.fail("datetime")
        if isinstance(value, dt.date):
            return value
        try:
            return parse_date_string(value)
        except (ValueError, TypeError):
            self.fail("invalid")


class JalaliModelSerializer(serializers.ModelSerializer):

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.DateField: JalaliDateField,
    }