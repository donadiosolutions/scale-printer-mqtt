# https://docs.docker.com/build/bake/reference/

# Inherit from the default "docker-container" driver
# https://docs.docker.com/build/drivers/
driver "docker-container" {
  # Set the image name for the build
  image = "moby/buildkit:buildx-stable-1"
}

# Define a group of targets
group "default" {
  targets = ["scale-daemon", "printer-daemon"]
}

# Define a variable for the image tag
variable "IMAGE_TAG" {
  default = "latest"
}

# Define the "meta" target for building the base image
target "meta" {
  dockerfile = "Containerfile"
  tags = ["meta:${IMAGE_TAG}"]
  target = "final"
}

# Define the "scale-daemon" target
target "scale-daemon" {
  inherits = ["meta"]
  tags = ["scale-daemon:${IMAGE_TAG}"]
  dockerfile = "Containerfile"
  target = "final"
  args = {
    APP_NAME = "scale_daemon"
  }
}

# Define the "printer-daemon" target
target "printer-daemon" {
  inherits = ["meta"]
  tags = ["printer-daemon:${IMAGE_TAG}"]
  dockerfile = "Containerfile"
  target = "final"
  args = {
    APP_NAME = "printer_daemon"
  }
}

# Define the "tester" target
target "tester" {
  inherits = ["meta"]
  tags = ["tester:${IMAGE_TAG}"]
  dockerfile = "Containerfile"
  target = "tester"
}
