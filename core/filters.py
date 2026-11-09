from django_filters import rest_framework as filters
from rest_framework import serializers

from .jalali import parse_date_string


class JalaliDateFilter(filters.Filter):

    def filter(self, qs, value):
        if not value:
            return qs
        try:
            parsed = parse_date_string(value)
        except (ValueError, TypeError):
            raise serializers.ValidationError({self.field_name: "Invalid date."})
        return super().filter(qs, parsed)