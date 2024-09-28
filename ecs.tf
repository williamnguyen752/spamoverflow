resource "aws_ecs_cluster" "spamoverflow" {
  name = "spamoverflow"
}

resource "aws_ecs_task_definition" "spamoverflow" {
  family                   = "spamoverflow"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = data.aws_iam_role.lab.arn

  container_definitions = <<DEFINITION
[
  {
    "image": "${aws_ecr_repository.spamoverflow.repository_url}:latest",
    "cpu": 1024,
    "memory": 2048,
    "name": "spamoverflow",
    "networkMode": "awsvpc",
    "portMappings": [
      {
        "containerPort": 8080,
        "hostPort": 8080
      }
    ],
    "environment": [
      {
        "name": "SQLALCHEMY_DATABASE_URI",
        "value": "postgresql://${local.database_username}:${local.database_password}@${aws_db_instance.database.address}:${aws_db_instance.database.port}/${aws_db_instance.database.db_name}"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/spamoverflow/spamoverflow",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs",
        "awslogs-create-group": "true"
      }
    }
  }
]
DEFINITION
}

resource "aws_ecs_service" "spamoverflow" {
  name            = "spamoverflow"
  cluster         = aws_ecs_cluster.spamoverflow.id
  task_definition = aws_ecs_task_definition.spamoverflow.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets             = data.aws_subnets.private.ids
    security_groups     = [aws_security_group.todo.id]
    assign_public_ip    = true
  }

  # add load balancer
  load_balancer {
    target_group_arn = aws_lb_target_group.spamoverflow.arn
    container_name   = "spamoverflow"
    container_port   = 8080
  }
}

# add load balancer for the ECS service
resource "aws_security_group" "todo" {
  name = "todo"
  description = "spamoverflow Security Group"

  # Allow traffic from the load balancer
  ingress {
    from_port = 8080
    to_port = 8080
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow traffic from the internet, for the load balancer
  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow traffic from the internet, for the load balancer
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}