resource "aws_ecs_cluster" "celery_worker" {
  name = "celery_worker"
}

resource "aws_cloudwatch_log_group" "celery_worker" {
  name = "/ecs/celery-worker"
  retention_in_days = 7
}

data "aws_iam_role" "celery_worker" {
  name = "LabRole"
}

# Add ECS task definition for the Celery worker
resource "aws_ecs_task_definition" "celery_worker" {
    family                   = "celery_worker"
    network_mode             = "awsvpc"
    requires_compatibilities = ["FARGATE"]
    cpu                      = 1024
    memory                   = 2048
    execution_role_arn       = data.aws_iam_role.lab.arn
    task_role_arn            = data.aws_iam_role.celery_worker.arn
    container_definitions = <<DEFINITION
[
  {
    "name": "celery_worker",
    "image": "${aws_ecr_repository.celery_worker.repository_url}:latest",
    "cpu": 1024,
    "memory": 2048,
    "essential": true,
    "environment": [
      {
        "name": "SQLALCHEMY_DATABASE_URI",
        "value": "postgresql://${local.database_username}:${local.database_password}@${aws_db_instance.database.address}:${aws_db_instance.database.port}/${aws_db_instance.database.db_name}"
      },
      {
        "name": "BROKER_URL",
        "value": "${aws_sqs_queue.email_queue.url}"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/celery-worker",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "celery"
      }
    }
  }
]
DEFINITION
}

# Add ECS service for the Celery worker
resource "aws_ecs_service" "celery_worker" {
  name            = "celery-worker"
  cluster         = aws_ecs_cluster.celery_worker.id
  task_definition = aws_ecs_task_definition.celery_worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = data.aws_subnets.private.ids
    security_groups  = [aws_security_group.celery_worker_sg.id]
    assign_public_ip = true
  }
}

resource "aws_security_group" "celery_worker_sg" {
  name        = "celery-worker-sg"
  description = "Security group for the Celery worker"

  # Allow outbound traffic on port 443 (HTTPS)
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "celery-worker-sg"
  }
}

resource "aws_security_group_rule" "celery_worker_to_rds" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.celery_worker_sg.id
  source_security_group_id = aws_security_group.database.id
}
