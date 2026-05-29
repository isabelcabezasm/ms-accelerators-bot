variable "name" {
  description = "Name of the Container App."
  type        = string
}

variable "environment_name" {
  description = "Optional name for the Container Apps environment. Defaults to <name>-env."
  type        = string
  default     = null
  nullable    = true
}

variable "location" {
  description = "Azure region for the Container Apps environment and app."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name for the Container Apps resources."
  type        = string
}

variable "container_name" {
  description = "Container name inside the Container App revision template."
  type        = string
  default     = "app"
}

variable "container_image" {
  description = "Container image to deploy in the Container App."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "container_cpu" {
  description = "vCPU allocation for the container."
  type        = number
  default     = 0.25
}

variable "container_memory" {
  description = "Memory allocation for the container."
  type        = string
  default     = "0.5Gi"
}

variable "target_port" {
  description = "Container port exposed through ingress."
  type        = number
  default     = 80
}

variable "external_enabled" {
  description = "Whether the Container App ingress is internet-accessible."
  type        = bool
  default     = true
}

variable "max_replicas" {
  description = "Maximum replica count for KEDA-managed scale-out."
  type        = number
  default     = 3
}

variable "tags" {
  description = "Tags applied to resources created by the module."
  type        = map(string)
  default     = {}
}
