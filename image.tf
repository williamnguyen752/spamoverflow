resource "docker_image" "spamoverflow" {
    name = "${aws_ecr_repository.spamoverflow.repository_url}:latest"
    build {
        context = "./app"
    }
}

resource "docker_registry_image" "spamoverflow" {
    name = docker_image.spamoverflow.name
}

resource "docker_image" "celery_worker" {
  name = "${aws_ecr_repository.celery_worker.repository_url}:latest"
  build {
    context = "./app"
    dockerfile = "Dockerfile.celery"
  }
}

resource "docker_registry_image" "celery_worker" {
  name = docker_image.celery_worker.name
}