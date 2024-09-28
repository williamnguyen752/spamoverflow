from kombu import Queue
from celery import Celery
import os
import logging
import boto3
from botocore.credentials import InstanceMetadataProvider, InstanceMetadataFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure AWS credentials using IAM role
credentials_provider = InstanceMetadataProvider(iam_role_fetcher=InstanceMetadataFetcher(timeout=1000, num_attempts=2))
credentials = credentials_provider.load()

broker_transport_options = {
    'region': 'us-east-1',
    'credentials': credentials,
}

# Create a Celery app instance

# broker_url = 'sqs://ASIAVRUVU5W7N33LHRMR:KboTU8cFC5VRNNY5zO+17LMlsuDvjpiV99Jopohw@us-east-1'

# broker_url = 'sqs//sqs.us-east-1.amazonaws.com/381492194750/email-queue'


# from kombu.utils.url import safequote

# aws_access_key = safequote("ASIAVRUVU5W7N33LHRMR")
# aws_secret_key = safequote("KboTU8cFC5VRNNY5zO+17LMlsuDvjpiV99Jopohw")

# broker_url = "sqs://{aws_access_key}:{aws_secret_key}@us-east-1".format(
#     aws_access_key=aws_access_key, aws_secret_key=aws_secret_key
# )

broker_url = "sqs://"
app = Celery('spamoverflow', broker=broker_url , include=['spamoverflow.tasks'])

# Configure the SQS broker transport options
app.conf.broker_transport_options = {
    'region': 'us-east-1',
    'visibility_timeout': 3600,
    'polling_interval': 1,
    'wait_time_seconds': 20,
}

# Define the task queues
app.conf.task_queues = (
    Queue('high', routing_key='high'),
    Queue('standard', routing_key='standard'),
)

# Define the task routes
app.conf.task_routes = {
    'scan_email': {'queue': 'high', 'routing_key': 'high'},
    'scan_email': {'queue': 'standard', 'routing_key': 'standard'}
}