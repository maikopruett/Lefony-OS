PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.PHONY: help test check-public firmware firmware-vm emulator run installer
help:
	@echo 'Lefony OS: test | check-public | firmware | firmware-vm | emulator | run | installer'
test:
	$(PYTHON) -m pytest tests
check-public:
	$(PYTHON) scripts/check_public_tree.py
firmware:
	./scripts/build_lefony_prime_g2.sh
firmware-vm:
	./scripts/build_lefony_prime_g2_vm.sh
emulator:
	./vm/build-prime-g2-qemu.sh
run:
	./vm/run-native-vm.sh --direct
installer:
	$(PYTHON) scripts/lefony_installer.py
