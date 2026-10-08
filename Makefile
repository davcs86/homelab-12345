# Operator entry points. All targets run from a pinned virtualenv.
# DIGITALOCEAN_TOKEN must be exported in the environment for DO targets.
SHELL       := /bin/bash
VENV        := .venv
PY          := $(VENV)/bin/python
ANSIBLE_DIR := ansible
COLOR       ?=

export ANSIBLE_CONFIG := $(CURDIR)/$(ANSIBLE_DIR)/ansible.cfg
export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

# sops: exact version, per-platform SHA-256 from the upstream checksums file.
SOPS_VERSION := 3.13.3
SOPS_SHA256_linux_amd64  := e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b
SOPS_SHA256_linux_arm64  := 53b0abacd38ef1b12a66d6c100956691b9cefce018d91f81e73ddf7438b94d77
SOPS_SHA256_darwin_amd64 := 42162d5cef10b74fcf80a045a70e658d7ce6e63d6ea1be6f347e44015714468d
SOPS_SHA256_darwin_arm64 := b97c0d434aab577dc40310e8d22ff9e45eef4c80638ab978daae9b4681c59286
SOPS_OS   := $(shell uname -s | tr A-Z a-z)
SOPS_ARCH := $(shell uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')
SOPS_SHA  := $(SOPS_SHA256_$(SOPS_OS)_$(SOPS_ARCH))
KEYS      ?= operator ci

.PHONY: help venv deps sops lint test check-color provision bootstrap site inventory seed-ssh-keys ssh-load

help:
	@echo "make deps                      - create .venv and install pinned tooling, collections, sops"
	@echo "make seed-ssh-keys [KEYS=...]  - generate SSH keys (private halves SOPS-encrypted)"
	@echo "make ssh-load KEY=operator     - decrypt a key straight into ssh-agent"
	@echo "make lint                      - yamllint + ansible-lint"
	@echo "make test                      - unit tests + playbook syntax check"
	@echo "make provision COLOR=blue      - create/converge DO resources for a colour"
	@echo "make bootstrap COLOR=blue      - first root login: create admin user, harden sshd (run once)"
	@echo "make site      COLOR=blue      - converge OS hardening, Docker, data volume"
	@echo "make inventory                 - show dynamic inventory groups"

$(PY):
	python3 -m venv $(VENV)

venv: $(PY)

deps: venv sops
	$(VENV)/bin/pip install --require-virtualenv -q -r $(ANSIBLE_DIR)/requirements.txt
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-galaxy collection install -r requirements.yml -p .collections

sops: venv
	@[[ -n "$(SOPS_SHA)" ]] || { echo "no pinned sops checksum for $(SOPS_OS)/$(SOPS_ARCH)"; exit 1; }
	@if [[ "$$($(VENV)/bin/sops --version 2>/dev/null | head -1)" != "sops $(SOPS_VERSION)"* ]]; then \
	  set -euo pipefail; tmp="$$(mktemp)"; \
	  curl -fsSL -o "$$tmp" https://github.com/getsops/sops/releases/download/v$(SOPS_VERSION)/sops-v$(SOPS_VERSION).$(SOPS_OS).$(SOPS_ARCH); \
	  echo "$(SOPS_SHA)  $$tmp" | sha256sum -c --quiet - 2>/dev/null || echo "$(SOPS_SHA)  $$tmp" | shasum -a 256 -c --quiet -; \
	  install -m 0755 "$$tmp" $(VENV)/bin/sops; rm -f "$$tmp"; \
	fi
	@$(VENV)/bin/sops --version | head -1

seed-ssh-keys: sops
	scripts/seed-ssh-keys.sh $(KEYS)

ssh-load:
	@[[ -n "$(KEY)" ]] || { echo "KEY=<name> required"; exit 1; }
	scripts/ssh-agent-load.sh $(KEY)

lint:
	$(VENV)/bin/yamllint -s .
	$(VENV)/bin/shellcheck scripts/*.sh
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-lint

test:
	$(PY) -m unittest discover -s $(ANSIBLE_DIR)/tests -v
	cd $(ANSIBLE_DIR) && for pb in playbooks/*.yml; do \
	  ../$(VENV)/bin/ansible-playbook --syntax-check -i localhost, -e edge_color=blue $$pb || exit 1; done

check-color:
	@[[ "$(COLOR)" == "blue" || "$(COLOR)" == "green" ]] || { echo "COLOR=blue|green required"; exit 1; }

provision: check-color
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-playbook playbooks/provision.yml -e edge_color=$(COLOR)

bootstrap: check-color
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-playbook playbooks/bootstrap.yml -e edge_color=$(COLOR)

site: check-color
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-playbook playbooks/site.yml -e edge_color=$(COLOR)

inventory:
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-inventory --graph
