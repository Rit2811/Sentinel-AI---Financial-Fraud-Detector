COMPOSE := docker compose -f infrastructure/compose.yaml
BASH := $(if $(wildcard C:/msys64/usr/bin/bash.exe),C:/msys64/usr/bin/bash.exe,bash)
POWERSHELL := C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe

.PHONY: bootstrap up down logs ps verify clean

bootstrap:
	$(if $(wildcard $(POWERSHELL)),$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1,$(BASH) scripts/bootstrap.sh)

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs --no-color --tail=100

ps:
	$(COMPOSE) ps

verify:
	$(if $(wildcard $(POWERSHELL)),$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1,$(BASH) scripts/verify.sh)

clean:
	$(if $(wildcard $(POWERSHELL)),$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/clean.ps1,$(BASH) scripts/clean.sh)
