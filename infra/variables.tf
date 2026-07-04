variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1" # Mumbai
}

variable "instance_type" {
  description = "GPU instance type (T4)"
  type        = string
  default     = "g4dn.xlarge"
}

variable "domain" {
  description = "Public domain served with HTTPS by Caddy"
  type        = string
  default     = "chat.chatbucket.chat"
}

variable "repo_url" {
  description = "Git repo cloned onto the instance and built by CI/CD"
  type        = string
  default     = "https://github.com/abhiramcoinearth-lang/conversational_chatAgents.git"
}

variable "llama_model" {
  description = "GGUF model llama.cpp loads (repo:quant, resolved via -hf)"
  type        = string
  default     = "unsloth/gemma-3-12b-it-GGUF:Q4_K_M"
}

variable "llama_ctx" {
  description = "llama.cpp context window"
  type        = number
  default     = 8192
}

variable "root_volume_gb" {
  description = "Root EBS size (holds Docker images + model cache)"
  type        = number
  default     = 100
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH (22). Default open; tighten to your IP/32."
  type        = string
  default     = "0.0.0.0/0"
}
