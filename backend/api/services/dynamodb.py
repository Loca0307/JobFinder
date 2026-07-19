import boto3

from api.settings.config import get_settings


def get_jobs_table():
    settings = get_settings()
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    return dynamodb.Table(settings.dynamodb_jobs_table)
