// SPDX-License-Identifier: GPL-2.0+
/* Lefony OS emulator A/B loader for the modeled Prime G2 NAND controller. */

#include <command.h>
#include <cpu_func.h>
#include <vsprintf.h>
#include <linux/string.h>
#include <asm/io.h>
#include <u-boot/crc.h>
#include <u-boot/sha256.h>

#define GPMI_BASE               0x01806000UL
#define GPMI_COMMAND            (GPMI_BASE + 0x100)
#define GPMI_PAGE               (GPMI_BASE + 0x104)
#define GPMI_STATUS             (GPMI_BASE + 0x10c)
#define GPMI_GEOMETRY_PAGE      (GPMI_BASE + 0x110)
#define GPMI_GEOMETRY_OOB       (GPMI_BASE + 0x114)
#define GPMI_GEOMETRY_ERASE     (GPMI_BASE + 0x118)
#define GPMI_GEOMETRY_BLOCKS    (GPMI_BASE + 0x11c)
#define GPMI_GEOMETRY_ECC       (GPMI_BASE + 0x120)
#define GPMI_BAD_BLOCK          (GPMI_BASE + 0x128)
#define GPMI_UNCORRECTABLE      (GPMI_BASE + 0x148)
#define GPMI_FIFO32             (GPMI_BASE + 0x14c)

#define PAGE_BYTES              2048U
#define PAGES_PER_BLOCK         64U
#define SLOT_BLOCKS             64U
#define SLOT_A_FIRST_BLOCK      32U
#define SLOT_B_FIRST_BLOCK      3968U
#define SLOT_BYTES_MAX          (8U * 1024U * 1024U)
#define METADATA_BLOCK_A        104U
#define METADATA_BLOCK_B        105U
#define METADATA_MAGIC          0x314d4241U /* ABM1 */
#define METADATA_COMMITTED      0x434f4d4dU
#define NO_SLOT                 0xffffffffU
#define LOAD_ADDRESS            0x80800000UL
#define HANDOFF_ADDRESS         0x87fff000UL
#define HANDOFF_MAGIC           0x3142464cU /* LFB1 */
#define ZIMAGE_MAGIC            0x016f2818U

struct slot_metadata {
	u32 bytes;
	u32 version[4];
	u8 sha256[SHA256_SUM_LEN];
};

struct ab_metadata {
	u32 magic;
	u32 schema;
	u32 bytes;
	u32 generation;
	u32 active;
	u32 pending;
	u32 attempts;
	u32 boot_limit;
	struct slot_metadata slots[2];
	u32 committed;
	u32 crc;
};

struct boot_handoff {
	u32 magic;
	u32 booted_slot;
	u32 active_slot;
	u32 pending_slot;
	u32 attempts;
	u32 boot_limit;
	u32 generation;
	u32 schema;
	u32 version[4];
	u32 reserved[4];
};

static u8 page_buffer[PAGE_BYTES] __aligned(4);

static bool geometry_valid(void)
{
	return readl(GPMI_GEOMETRY_PAGE) == PAGE_BYTES &&
		readl(GPMI_GEOMETRY_OOB) == 64 &&
		readl(GPMI_GEOMETRY_ERASE) == PAGE_BYTES * PAGES_PER_BLOCK &&
		readl(GPMI_GEOMETRY_BLOCKS) == 4096 &&
		readl(GPMI_GEOMETRY_ECC) >= 8;
}

static bool block_bad(u32 block)
{
	writel(block * PAGES_PER_BLOCK, GPMI_PAGE);
	return readl(GPMI_BAD_BLOCK) != 0;
}

static bool erase_block(u32 block)
{
	writel(block * PAGES_PER_BLOCK, GPMI_PAGE);
	writel(0xd0, GPMI_COMMAND);
	return !(readl(GPMI_STATUS) & 1);
}

static bool read_page(u32 page, void *destination)
{
	u32 *words = destination;
	u32 i;

	writel(0, GPMI_COMMAND);
	writel(page, GPMI_PAGE);
	for (i = 0; i < PAGE_BYTES / sizeof(u32); i++)
		words[i] = readl(GPMI_FIFO32);
	return readl(GPMI_UNCORRECTABLE) == 0;
}

static bool program_page(u32 page, const void *source)
{
	const u32 *words = source;
	u32 i;

	writel(page, GPMI_PAGE);
	writel(0x80, GPMI_COMMAND);
	for (i = 0; i < PAGE_BYTES / sizeof(u32); i++)
		writel(words[i], GPMI_FIFO32);
	writel(0x10, GPMI_COMMAND);
	return !(readl(GPMI_STATUS) & 1);
}

static u32 metadata_crc(const struct ab_metadata *metadata)
{
	struct ab_metadata copy = *metadata;

	copy.crc = 0;
	return crc32(0, (const unsigned char *)&copy, sizeof(copy));
}

static bool metadata_valid(const struct ab_metadata *metadata)
{
	return metadata->magic == METADATA_MAGIC && metadata->schema == 1 &&
		metadata->bytes == sizeof(*metadata) &&
		metadata->committed == METADATA_COMMITTED &&
		metadata->boot_limit && metadata->boot_limit <= 10 &&
		metadata->active <= 1 &&
		(metadata->pending <= 1 || metadata->pending == NO_SLOT) &&
		metadata->slots[0].bytes <= SLOT_BYTES_MAX &&
		metadata->slots[1].bytes <= SLOT_BYTES_MAX &&
		metadata->crc == metadata_crc(metadata);
}

static bool read_metadata_copy(int copy, struct ab_metadata *metadata)
{
	u32 block = copy ? METADATA_BLOCK_B : METADATA_BLOCK_A;

	if (block_bad(block) || !read_page(block * PAGES_PER_BLOCK, page_buffer))
		return false;
	memcpy(metadata, page_buffer, sizeof(*metadata));
	return metadata_valid(metadata);
}

static bool read_metadata(struct ab_metadata *metadata, int *source)
{
	struct ab_metadata copies[2];
	bool valid[2];

	valid[0] = read_metadata_copy(0, &copies[0]);
	valid[1] = read_metadata_copy(1, &copies[1]);
	if (!valid[0] && !valid[1]) {
		*source = -1;
		return false;
	}
	*source = valid[1] && (!valid[0] ||
		copies[1].generation > copies[0].generation) ? 1 : 0;
	*metadata = copies[*source];
	return true;
}

static bool write_metadata_copy(const struct ab_metadata *metadata, int copy)
{
	struct ab_metadata verify;
	u32 block = copy ? METADATA_BLOCK_B : METADATA_BLOCK_A;

	if (block_bad(block) || !erase_block(block))
		return false;
	memset(page_buffer, 0xff, sizeof(page_buffer));
	memcpy(page_buffer, metadata, sizeof(*metadata));
	if (!program_page(block * PAGES_PER_BLOCK, page_buffer) ||
	    !read_page(block * PAGES_PER_BLOCK, page_buffer))
		return false;
	memcpy(&verify, page_buffer, sizeof(verify));
	return metadata_valid(&verify) &&
		!memcmp(&verify, metadata, sizeof(verify));
}

static bool commit_metadata(struct ab_metadata *metadata, int *source)
{
	int previous = *source;
	int first = previous == 0 ? 1 : 0;

	metadata->crc = metadata_crc(metadata);
	if (!write_metadata_copy(metadata, first)) {
		first = 1 - first;
		if (!write_metadata_copy(metadata, first))
			return false;
	}
	*source = first;
	/* The first verified copy is the atomic commit. Mirroring may fail safely. */
	(void)write_metadata_copy(metadata, 1 - first);
	return true;
}

static bool write_slot(u32 slot, const u8 *source, u32 bytes)
{
	u32 first = slot ? SLOT_B_FIRST_BLOCK : SLOT_A_FIRST_BLOCK;
	u32 block, page;
	u32 cursor = 0;
	u32 capacity = 0;

	for (block = 0; block < SLOT_BLOCKS; block++)
		if (!block_bad(first + block))
			capacity += PAGE_BYTES * PAGES_PER_BLOCK;
	if (!bytes || bytes > capacity)
		return false;
	for (block = 0; block < SLOT_BLOCKS; block++)
		if (!block_bad(first + block) && !erase_block(first + block))
			return false;
	for (block = 0; block < SLOT_BLOCKS && cursor < bytes; block++) {
		if (block_bad(first + block))
			continue;
		for (page = 0; page < PAGES_PER_BLOCK && cursor < bytes; page++) {
			u32 amount = min(bytes - cursor, PAGE_BYTES);

			memset(page_buffer, 0xff, sizeof(page_buffer));
			memcpy(page_buffer, source + cursor, amount);
			if (!program_page((first + block) * PAGES_PER_BLOCK + page,
					  page_buffer))
				return false;
			cursor += amount;
		}
	}
	return cursor == bytes;
}

static bool load_slot(u32 slot, const struct slot_metadata *record)
{
	u32 first = slot ? SLOT_B_FIRST_BLOCK : SLOT_A_FIRST_BLOCK;
	u8 *destination = (u8 *)LOAD_ADDRESS;
	u8 digest[SHA256_SUM_LEN];
	u32 block, page;
	u32 cursor = 0;

	if (!record->bytes || record->bytes > SLOT_BYTES_MAX)
		return false;
	for (block = 0; block < SLOT_BLOCKS && cursor < record->bytes; block++) {
		if (block_bad(first + block))
			continue;
		for (page = 0; page < PAGES_PER_BLOCK && cursor < record->bytes; page++) {
			u32 amount = min(record->bytes - cursor, PAGE_BYTES);

			if (!read_page((first + block) * PAGES_PER_BLOCK + page,
				       page_buffer))
				return false;
			memcpy(destination + cursor, page_buffer, amount);
			cursor += amount;
		}
	}
	if (cursor != record->bytes)
		return false;
	sha256_csum_wd(destination, record->bytes, digest, CHUNKSZ_SHA256);
	if (memcmp(digest, record->sha256, sizeof(digest)))
		return false;
	if (readl(LOAD_ADDRESS + 0x24) != ZIMAGE_MAGIC ||
	    readl(LOAD_ADDRESS + 0x2c) != record->bytes)
		return false;
	return true;
}

static void set_handoff(u32 slot, const struct ab_metadata *metadata)
{
	struct boot_handoff *handoff = (struct boot_handoff *)HANDOFF_ADDRESS;

	handoff->booted_slot = slot;
	handoff->active_slot = metadata->active;
	handoff->pending_slot = metadata->pending;
	handoff->attempts = metadata->attempts;
	handoff->boot_limit = metadata->boot_limit;
	handoff->generation = metadata->generation;
	handoff->schema = 2;
	memcpy(handoff->version, metadata->slots[slot].version,
	       sizeof(handoff->version));
	memset(handoff->reserved, 0, sizeof(handoff->reserved));
	handoff->magic = HANDOFF_MAGIC;
	flush_dcache_range(HANDOFF_ADDRESS,
			   HANDOFF_ADDRESS + sizeof(*handoff));
}

static int rollback(struct ab_metadata *metadata, int *source, const char *why)
{
	printf("Lefony A/B: rolling back pending slot (%s)\n", why);
	metadata->pending = NO_SLOT;
	metadata->attempts = 0;
	metadata->generation++;
	if (!commit_metadata(metadata, source)) {
		printf("ERROR: Lefony A/B rollback metadata commit failed\n");
		return CMD_RET_FAILURE;
	}
	return CMD_RET_SUCCESS;
}

static int do_ab_boot(void)
{
	struct ab_metadata metadata;
	u32 selected;
	bool pending_boot = false;
	int source;

	if (!geometry_valid()) {
		printf("ERROR: Lefony A/B NAND geometry mismatch\n");
		return CMD_RET_FAILURE;
	}
	if (!read_metadata(&metadata, &source)) {
		printf("Lefony A/B: no valid metadata; factory seed required\n");
		return CMD_RET_FAILURE;
	}
	selected = metadata.active;
	if (metadata.pending <= 1) {
		if (metadata.attempts >= metadata.boot_limit) {
			if (rollback(&metadata, &source, "boot limit reached"))
				return CMD_RET_FAILURE;
		} else {
			selected = metadata.pending;
			metadata.attempts++;
			metadata.generation++;
			printf("Lefony A/B: pending slot %c attempt %u/%u\n",
			       'A' + selected, metadata.attempts, metadata.boot_limit);
			if (!commit_metadata(&metadata, &source)) {
				printf("ERROR: Lefony A/B attempt commit failed\n");
				return CMD_RET_FAILURE;
			}
			pending_boot = true;
		}
	}
	if (!load_slot(selected, &metadata.slots[selected])) {
		printf("ERROR: Lefony A/B slot %c verification failed\n",
		       'A' + selected);
		if (!pending_boot || rollback(&metadata, &source, "verification failed"))
			return CMD_RET_FAILURE;
		selected = metadata.active;
		if (!load_slot(selected, &metadata.slots[selected])) {
			printf("ERROR: Lefony A/B active slot %c verification failed\n",
			       'A' + selected);
			return CMD_RET_FAILURE;
		}
	}
	set_handoff(selected, &metadata);
	printf("Lefony A/B: verified slot %c (%u bytes); booting\n",
	       'A' + selected, metadata.slots[selected].bytes);
	return CMD_RET_SUCCESS;
}

static int do_ab_seed(ulong address, u32 bytes)
{
	struct ab_metadata metadata;
	u8 digest[SHA256_SUM_LEN];
	const u8 *image = (const u8 *)address;
	int source;

	if (!geometry_valid() || !bytes || bytes > SLOT_BYTES_MAX ||
	    readl(address + 0x24) != ZIMAGE_MAGIC ||
	    readl(address + 0x2c) != bytes) {
		printf("ERROR: Lefony A/B invalid factory capsule\n");
		return CMD_RET_FAILURE;
	}
	if (read_metadata(&metadata, &source)) {
		printf("ERROR: Lefony A/B metadata already exists\n");
		return CMD_RET_FAILURE;
	}
	sha256_csum_wd(image, bytes, digest, CHUNKSZ_SHA256);
	printf("Lefony A/B: seeding factory slot A (%u bytes)\n", bytes);
	if (!write_slot(0, image, bytes)) {
		printf("ERROR: Lefony A/B factory slot write failed\n");
		return CMD_RET_FAILURE;
	}
	memset(&metadata, 0, sizeof(metadata));
	metadata.magic = METADATA_MAGIC;
	metadata.schema = 1;
	metadata.bytes = sizeof(metadata);
	metadata.generation = 1;
	metadata.active = 0;
	metadata.pending = NO_SLOT;
	metadata.boot_limit = 3;
	metadata.slots[0].bytes = bytes;
	metadata.slots[0].version[0] = 1;
	memcpy(metadata.slots[0].sha256, digest, sizeof(digest));
	metadata.committed = METADATA_COMMITTED;
	source = -1;
	if (!commit_metadata(&metadata, &source) ||
	    !load_slot(0, &metadata.slots[0])) {
		printf("ERROR: Lefony A/B factory verification failed\n");
		return CMD_RET_FAILURE;
	}
	set_handoff(0, &metadata);
	printf("Lefony A/B: factory slot A verified; booting\n");
	return CMD_RET_SUCCESS;
}

static int do_lefony_ab(struct cmd_tbl *cmdtp, int flag, int argc,
			char *const argv[])
{
	if (argc == 2 && !strcmp(argv[1], "boot"))
		return do_ab_boot();
	if (argc == 4 && !strcmp(argv[1], "seed"))
		return do_ab_seed(simple_strtoul(argv[2], NULL, 16),
				  simple_strtoul(argv[3], NULL, 16));
	return CMD_RET_USAGE;
}

U_BOOT_CMD(
	lefony_ab, 4, 0, do_lefony_ab,
	"load, verify, and select a Lefony OS A/B slot",
	"boot\n"
	"lefony_ab seed <address> <bytes>"
);
