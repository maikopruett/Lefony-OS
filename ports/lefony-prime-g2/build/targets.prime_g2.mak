# Produce a flat image as a debugging aid. U-Boot should use epsilon.elf with
# bootelf during bring-up so every load address comes from the ELF headers.
$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf
	@echo "OBJCOPY $@"
	$(Q) $(OBJCOPY) -R .framebuffer -O binary $< $@

# Keep the full ELF for source-level debugging, but use this compact ELF for
# U-Boot transfers. Program headers and linked addresses are unchanged.
$(BUILD_DIR)/%.u-boot.elf: $(BUILD_DIR)/%.elf
	@echo "STRIP   $@"
	$(Q) $(OBJCOPY) --strip-debug $< $@

.PHONY: %_size
%_size: $(BUILD_DIR)/%.elf
	$(SIZE) $<
