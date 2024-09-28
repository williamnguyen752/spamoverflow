from flask import Blueprint, request, jsonify, current_app
from spamoverflow.models.email import Email
from spamoverflow.models.email import MaliciousEmail
from spamoverflow.models.email import db
from uuid import UUID, uuid4
from sqlalchemy import text, func
import re
from datetime import datetime, timezone
import pendulum
import os
import subprocess
import json
from urllib.parse import urlparse
from ..tasks import scan_email
from spamoverflow.models.email import MaliciousEmail
from celery.result import AsyncResult 
import logging


#malicious_email_storage = MaliciousEmailStorage('your-bucket-name')

# Regular expression pattern for validating email addresses [1]
EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

api = Blueprint('api', __name__, url_prefix='/api/v1')

@api.route('/health', methods=['GET'])
def health_check():
    database_up = check_database_connection()
    external_service_up = check_external_service()

    dependencies = [
        {"name": "Database", "healthy": database_up},
        {"name": "ExternalService", "healthy": external_service_up}
    ]

    overall_health = all(dependency['healthy'] for dependency in dependencies)

    if not overall_health:
        response_status = 503
    else:
        response_status = 200

    response_headers = {
        "X-Health-SpamOverflow": "0.1",
        "depends-on": ", ".join([dependency['name'] for dependency in dependencies])
    }

    return jsonify({"healthy": overall_health, "dependencies": dependencies}), response_status, response_headers

def check_database_connection():
    try:
        #check connection to the database
        db.session.execute(text("SELECT 1"))
        return True  # The database is up
    except Exception as e:
        return False  # The database is down or unreachable

def check_external_service():
    # Check if the spamhammer is up [2]
    try:
        external_service_url = 'https://github.com/CSSE6400/SpamHammer/releases/latest'
        cmd = f"wget --spider '{external_service_url}'"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            return True
        else:
            return False
    except Exception as e:
        return False

@api.route('/customers/<customer_id>/emails', methods=['GET'])
def get_emails_by_customer(customer_id):
    #validate the customer_id
    try:
        UUID(customer_id, version=4)
    except:
        return jsonify({"error": "Invalid customer_id", "status": "Bad Request"}), 400
    # parse query parameters
    try:
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        from_email = request.args.get('from')
        to_email = request.args.get('to')
        state = request.args.get('state')
        only_malicious = request.args.get('only_malicious')

        # validate the query parameters
        if limit <= 0 or limit > 1000:
            return jsonify({"error": "Invalid limit", "status": "Bad Request"}), 400
        if offset < 0:
            return jsonify({"error": "Invalid offset", "status": "Bad Request"}), 400
        if start_date:
            try:
                pendulum.parse(start_date, strict=True)
            except pendulum.exceptions.ParserError:
                return jsonify({"error": "Invalid start date format", "status": "Bad Request"}), 400
        if end_date:
            try:
                pendulum.parse(end_date, strict=True)
            except pendulum.exceptions.ParserError:
                return jsonify({"error": "Invalid end date format", "status": "Bad Request"}), 400
        if from_email and not re.match(EMAIL_REGEX, from_email):
            return jsonify({"error": "Invalid email format for 'from' parameter", "status": "Bad Request"}), 400
        if to_email and not re.match(EMAIL_REGEX, to_email):
            return jsonify({"error": "Invalid email format for 'to' parameter", "status": "Bad Request"}), 400
        if state and state not in ['pending', 'scanned', 'failed']:
            return jsonify({"error": "Invalid state", "status": "Bad Request"}), 400
        if only_malicious and only_malicious not in ['true', 'false']:
            return jsonify({"error": "Invalid only_malicious", "status": "Bad Request"}), 400

        # build the query to retrieve emails
        query = Email.query.filter(Email.customer_id == customer_id)
        # apply filters
        if start_date:
            parsed_start_date = pendulum.parse(start_date, strict=True)
            query = query.filter(Email.created_at >= parsed_start_date)
        if end_date:
            parsed_end_date = pendulum.parse(end_date, strict=True)
            query = query.filter(Email.created_at <= parsed_end_date)
        if from_email:
            query = query.filter_by(from_email=from_email)
        if to_email:
            query = query.filter_by(to_email=to_email)
        if state:
            query = query.filter_by(status=state)
        if only_malicious and only_malicious.lower() == 'true':
            query = query.filter(Email.malicious == True)

        # apply pagination
        emails = query.order_by(Email.created_at.desc()).offset(offset).limit(limit).all()
        if not emails:
            return jsonify([]), 200

        # Prepare the response
        email_data = []
        for email in emails:
            email_data.append({
                "id": str(email.id),
                "created_at": email.created_at.isoformat(),
                "updated_at": email.updated_at.isoformat(),
                "contents": {
                    "to": email.to_email,
                    "from": email.from_email,
                    "subject": email.subject,
                },
                "status": email.status,
                "malicious": email.malicious,
                "domains": email.domains,
                "metadata": email.email_metadata
            })

        return jsonify(email_data), 200
    except Exception as e:
        return jsonify({"error": str(e), "status": "Internal Server Error"}), 500

@api.route('/customers/<customer_id>/emails/<id>', methods=['GET'])
def get_email(customer_id, id):
    try:
        # Validate the customer_id is UUIDv4, id is UUID, and request
        # contains the correct content type with required customer_id and id
        UUID(customer_id, version=4)
        UUID(id)
    except:
        return jsonify({"error": "Invalid customer_id", "status": "Bad Request"}), 400

    email = Email.query.filter_by(id=id, customer_id=customer_id).first()

    if not email:
        return jsonify({"error": "Email not found", "status": "Not Found"}), 404

    email_data = {
            "id": email.id,
            "created_at": email.created_at.isoformat(),
            "updated_at": email.updated_at.isoformat(),
            "contents": {
                "to": email.to_email,
                "from": email.from_email,
                "subject": email.subject,
            },
            "status": email.status,
            "malicious": email.malicious,
            "domains": email.domains,
            "metadata": email.email_metadata,
    }
    return jsonify(email_data), 200

def run_spamhammer(email_json):
    try:
        spamhammer_path = os.path.join(os.getcwd(), 'spamoverflow', 'spamhammer')
        result = subprocess.run([spamhammer_path, 'scan', '--input', '-'], input=email_json, capture_output=True, text=True, check=True)
        output_json = json.loads(result.stdout.strip())
        return output_json.get('malicious', False)
    except:
        return False

def extract_domains(body):
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+') # ref [3]
    urls = url_pattern.findall(body) # Extract URLs from the email body
    domains = list(set([urlparse(url).netloc for url in urls])) # Extract unique domains from the URLs
    return domains

@api.route('/customers/<customer_id>/emails', methods=['POST'])
def create_email(customer_id):
    try:
        # Validate the customer_id
        UUID(customer_id)
    except ValueError:
        return jsonify({"error": "Invalid customer_id"}), 400

    data = request.json

    if not data or 'contents' not in data or 'metadata' not in data:
        return jsonify({"error": "Invalid query request"}), 400

    try:
        email = Email(
            id=str(uuid4()),
            customer_id=customer_id,
            to_email=data['contents']['to'],
            from_email=data['contents']['from'],
            subject=data['contents']['subject'],
            body=data['contents']['body'],
            email_metadata=data['metadata'],
            status = "pending",
            malicious=False
        )
        domains = extract_domains(email.body)
        email.domains = domains

        spamhammer_metadata = data['metadata'].get('spamhammer', '0|0')
        spamhammer_data = {
            "id": email.id,
            "content": email.body,
            "metadata": spamhammer_metadata
        }
        spamhammer_output = run_spamhammer(json.dumps(spamhammer_data))
        malicious = spamhammer_output

        if malicious:
            malicious_email = MaliciousEmail(id=email.id, body=email.body)
            db.session.add(malicious_email)

        email.status = "scanned"
        email.malicious = malicious

        # Determine the priority based on customer_id
        if customer_id.startswith('1111'):
            priority = 'high'
        else:
            priority = 'standard'
        
        current_app.logger.info("Enqueuing task for email: %s", email.id)
        try:
            scan_email.apply_async(args=[email.id], queue=priority)
            current_app.logger.info("Task enqueued successfully for email: %s", email.id)
        except Exception as e:
            current_app.logger.error("Failed to enqueue task for email %s: %s", email.id, str(e))
            current_app.logger.error("credentials: %s", os.environ.get("AWS_ACCESS_KEY_ID"))
            db.session.rollback()
            return jsonify({"error": f"Failed to enqueue task: {str(e)}"}), 500

        db.session.add(email)
        db.session.commit()

        email_data = {
            "id": email.id,
            "created_at": email.created_at.isoformat(),
            "updated_at": email.updated_at.isoformat(),
            "contents": {
                "to": email.to_email,
                "from": email.from_email,
                "subject": email.subject,
            },
            "status": email.status,
            "malicious": email.malicious,
            "domains": email.domains,
            "metadata": email.email_metadata
        }

        return jsonify(email_data), 201

    except Exception as e:
        current_app.logger.error(f"An unknown error occurred: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"An unknown error occurred: {str(e)}"}), 500

@api.route('/customers/<customer_id>/reports/actors', methods=['GET'])
def get_malicious_actors(customer_id):
    try:
        # Validate the customer_id
        UUID(customer_id)
    except ValueError:
        return jsonify({"error": "Invalid customer_id"}), 400

    try:
        malicious_emails = Email.query.filter_by(customer_id=customer_id, malicious=True).all()

        actors = {}
        for email in malicious_emails:
            if email.from_email not in actors:
                actors[email.from_email] = 1
            else:
                actors[email.from_email] += 1

        actor_data = []
        for actor, count in actors.items():
            actor_data.append({
                "id": actor,
                "count": count
            })

        report_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(actor_data),
            "data": actor_data
        }

        return jsonify(report_data), 200
    except Exception as e:
        return jsonify({"error": f"An unknown error occurred: {str(e)}"}), 500


@api.route('/customers/<customer_id>/reports/domains', methods=['GET'])
def get_malicious_domains(customer_id):
    try:
        # Validate the customer_id
        UUID(customer_id)
    except ValueError:
        return jsonify({"error": "Invalid customer_id"}), 400

    try:
        malicious_emails = Email.query.filter_by(customer_id=customer_id, malicious=True).all()

        domains = {}
        for email in malicious_emails:
            for domain in email.domains:
                domains[domain] = domains.get(domain, 0) + 1

        domain_data = []
        for domain, count in domains.items():
            domain_data.append({
                "id": domain,
                "count": count
            })

        report_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(domain_data),
            "data": domain_data
        }

        return jsonify(report_data), 200
    except Exception as e:
        return jsonify({"error": f"An unknown error occurred: {str(e)}"}), 500

@api.route('/customers/<customer_id>/reports/recipients', methods=['GET'])
def get_malicious_recipients(customer_id):
    try:
        # Validate the customer_id
        UUID(customer_id)
    except ValueError:
        return jsonify({"error": "Invalid customer_id"}), 400

    try:
        malicious_emails = Email.query.filter_by(customer_id=customer_id, malicious=True).all()

        recipients = {}
        for email in malicious_emails:
            recipients[email.to_email] = recipients.get(email.to_email, 0) + 1

        recipient_data = []
        for recipient, count in recipients.items():
            recipient_data.append({
                "id": recipient,
                "count": count
            })

        report_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(recipient_data),
            "data": recipient_data
        }

        return jsonify(report_data), 200
    except Exception as e:
        return jsonify({"error": f"An unknown error occurred: {str(e)}"}), 500