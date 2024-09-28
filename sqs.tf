# Add SQS resource
resource "aws_sqs_queue" "email_queue" {
    name = "email-queue"
}

resource "aws_vpc_endpoint" "sqs" {
  vpc_id            = data.aws_vpc.default.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.sqs"
  vpc_endpoint_type = "Interface"

  security_group_ids = [aws_security_group.sqs_endpoint.id]

  private_dns_enabled = true
}

data "aws_region" "current" {}

resource "aws_security_group" "sqs_endpoint" {
  name_prefix = "sqs-endpoint-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
}