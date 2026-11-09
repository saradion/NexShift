from rest_framework import serializers


class GenerateOptionsSerializer(serializers.Serializer):
    time_limit_seconds = serializers.IntegerField(min_value=5, max_value=600, default=30)
    fairness = serializers.BooleanField(default=True)