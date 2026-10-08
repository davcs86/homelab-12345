# Operator entry points. All targets run from a pinned virtualenv.
# DIGITALOCEAN_TOKEN must be exported in the environment for DO targets.
SHELL       := /bin/bash
VENV        := .venv
PY          := $(VENV)/bin/python
ANSIBLE_DIR := ansible
COLOR       ?=

export ANSIBLE_CONFIG := $(CURDIR)/$(ANSIBLE_DIR)/ansible.cfg

.PHONY: help venv deps lint test syntax check-color provision bootstrap site inventory

help:
	@echo "make deps                      - create .venv and install pinned tooling + collections"
	@echo "make lint                      - yamllint + ansible-lint"
	@echo "make test                      - unit tests + playbook syntax check"
	@echo "make provision COLOR=blue      - create/converge DO resources for a colour"
	@echo "make bootstrap COLOR=blue      - first root login: create admin user, harden sshd (run once)"
	@echo "make site      COLOR=blue      - converge OS hardening, Docker, data volume"
	@echo "make inventory                 - show dynamic inventory groups"

$(PY):
	python3 -m venv $(VENV)

venv: $(PY)

deps: venv
	$(VENV)/bin/pip install --require-virtualenv -q -r $(ANSIBLE_DIR)/requirements.txt
	cd $(ANSIBLE_DIR) && ../$(VENV)/bin/ansible-galaxy collection install -r requirements.yml -p .collections

lint:
	$(VENV)/bin/yamllint -s .
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
