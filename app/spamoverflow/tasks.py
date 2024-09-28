from .celery_app import app
from spamoverflow.models.email import Email, MaliciousEmail
from spamoverflow import create_app
from spamoverflow.models import db

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SimilarityChecker:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()

    def calculate_similarity(self, email_body, malicious_emails_body):
        email_vector = self.vectorizer.fit_transform([email_body])
        malicious_vectors = self.vectorizer.transform([me for me in malicious_emails_body])
        similarity_scores = cosine_similarity(email_vector, malicious_vectors)
        return similarity_scores.max()

@app.task(name='scan_email')
def scan_email(email_id):
    flask_app = create_app()
    with flask_app.app_context():
        email = Email.query.get(email_id)
        if email:
            try:
                # Run SpamHammer on the email body
                #malicious = run_spamhammer(email.body)

                # Retrieve malicious emails from the database
                malicious_emails = MaliciousEmail.query.all()

                # Calculate similarity with known bad emails
                similarity_checker = SimilarityChecker()
                similarity_score = similarity_checker.calculate_similarity(email.body, [me.body for me in malicious_emails])
                # Update email status and malicious flag
                #email.status = 'scanned'
                email.malicious = email.malicious or True if similarity_score > 0.8 else False

                # Determine the priority based on customer_id
                if email.customer_id.startswith('1111'):
                    priority = 'high'
                else:
                    priority = 'standard'

                # Enqueue the email scanning task with the appropriate priority
                scan_email.apply_async(args=[email.id], queue=priority)

                # Save the updated email
                db.session.commit()
                flask_app.logger.info("Email %s processed successfully", email.id)
            except Exception as e:
                flask_app.logger.error("Error processing email %s: %s", email.id, str(e))
                raise
        else:
            flask_app.logger.warning("Email %s not found", email_id)