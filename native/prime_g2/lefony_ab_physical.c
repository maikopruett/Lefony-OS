// SPDX-License-Identifier: GPL-2.0+
/*
 * Lefony OS A/B boot policy for the physical HP Prime G2 U-Boot.
 *
 * Flash writes during an update are performed by the recovery Linux image,
 * using the board's proven MXS GPMI/BCH driver.  U-Boot owns only the small,
 * redundant boot-control record: it selects a slot, persists an attempt
 * before booting it, commits a success token left by Lefony, and rolls back a
 * candidate that cannot boot successfully.
 */

#include <common.h>
#include <command.h>
#include <nand.h>
#include <asm/io.h>
#include <u-boot/crc.h>
#include <u-boot/sha256.h>

#define PAGE_BYTES              2048U
#define ERASE_BYTES             (128U * 1024U)
#define TOTAL_BYTES             (512ULL * 1024ULL * 1024ULL)
#define SLOT_BYTES_MAX          (8U * 1024U * 1024U)
#define SLOT_A_OFFSET           (4ULL * 1024ULL * 1024ULL)
#define SLOT_B_OFFSET           (496ULL * 1024ULL * 1024ULL)
#define METADATA_A_OFFSET       (13ULL * 1024ULL * 1024ULL)
#define METADATA_B_OFFSET       (METADATA_A_OFFSET + ERASE_BYTES)
#define METADATA_MAGIC          0x314d4241U /* ABM1 */
#define METADATA_COMMITTED      0x434f4d4dU /* COMM */
#define NO_SLOT                 0xffffffffU
#define LOAD_ADDRESS            0x80800000UL
#define HANDOFF_ADDRESS         0x87fff000UL
#define HANDOFF_MAGIC           0x3142464cU /* LFB1 */
#define CONFIRM_MAGIC_ADDRESS   0x020cc068UL
#define CONFIRM_SLOT_ADDRESS    0x020cc06cUL
#define CONFIRM_MAGIC           0x4b4f464cU /* LFOK */
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

static u8 page_buffer[PAGE_BYTES] __aligned(ARCH_DMA_MINALIGN);

static struct mtd_info *physical_nand(void)
{
	return get_nand_dev_by_index(0);
}

static bool geometry_valid(void)
{
	struct mtd_info *mtd = physical_nand();

	return mtd && mtd->size == TOTAL_BYTES &&
		mtd->writesize == PAGE_BYTES && mtd->oobsize == 64 &&
		mtd->erasesize == ERASE_BYTES;
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

static bool read_exact(loff_t offset, void *destination, size_t bytes,
		       loff_t limit)
{
	struct mtd_info *mtd = physical_nand();
	size_t length = bytes;
	size_t actual = 0;
	int result;

	result = nand_read_skip_bad(mtd, offset, &length, &actual, limit,
				    destination);
	return !result && length == bytes;
}

static bool read_metadata_copy(int copy, struct ab_metadata *metadata)
{
	loff_t offset = copy ? METADATA_B_OFFSET : METADATA_A_OFFSET;

	if (nand_block_isbad(physical_nand(), offset) ||
	    !read_exact(offset, page_buffer, PAGE_BYTES, ERASE_BYTES))
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

static bool erase_metadata_copy(int copy)
{
	nand_erase_options_t options;

	memset(&options, 0, sizeof(options));
	options.offset = copy ? METADATA_B_OFFSET : METADATA_A_OFFSET;
	options.length = ERASE_BYTES;
	options.lim = ERASE_BYTES;
	options.quiet = 1;
	return nand_erase_opts(physical_nand(), &options) == 0;
}

static bool write_metadata_copy(const struct ab_metadata *metadata, int copy)
{
	struct ab_metadata verify;
	loff_t offset = copy ? METADATA_B_OFFSET : METADATA_A_OFFSET;
	size_t length = PAGE_BYTES;
	size_t actual = 0;

	if (nand_block_isbad(physical_nand(), offset) ||
	    !erase_metadata_copy(copy))
		return false;
	memset(page_buffer, 0xff, sizeof(page_buffer));
	memcpy(page_buffer, metadata, sizeof(*metadata));
	if (nand_write_skip_bad(physical_nand(), offset, &length, &actual,
				ERASE_BYTES, page_buffer, WITH_WR_VERIFY) ||
	    length != PAGE_BYTES ||
	    !read_exact(offset, page_buffer, PAGE_BYTES, ERASE_BYTES))
		return false;
	memcpy(&verify, page_buffer, sizeof(verify));
	return metadata_valid(&verify) &&
		!memcmp(&verify, metadata, sizeof(verify));
}

static bool commit_metadata(struct ab_metadata *metadata, int *source)
{
	int first = *source == 0 ? 1 : 0;

	metadata->crc = metadata_crc(metadata);
	/* Never erase the only valid copy as a fallback. If the stale copy is
	 * physically unusable, stop and keep the current generation bootable. */
	if (!write_metadata_copy(metadata, first))
		return false;
	*source = first;
	/* The first verified copy is the commit point; mirroring is best effort. */
	(void)write_metadata_copy(metadata, 1 - first);
	return true;
}

static bool load_slot(u32 slot, const struct slot_metadata *record)
{
	loff_t offset = slot ? SLOT_B_OFFSET : SLOT_A_OFFSET;
	u8 *destination = (u8 *)LOAD_ADDRESS;
	u8 digest[SHA256_SUM_LEN];

	if (!record->bytes || record->bytes > SLOT_BYTES_MAX ||
	    !read_exact(offset, destination, record->bytes, SLOT_BYTES_MAX))
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

static int rollback(struct ab_metadata *metadata, int *source,
		    const char *reason)
{
	printf("Lefony A/B: rolling back pending slot (%s)\n", reason);
	metadata->pending = NO_SLOT;
	metadata->attempts = 0;
	metadata->generation++;
	return commit_metadata(metadata, source) ? CMD_RET_SUCCESS :
		CMD_RET_FAILURE;
}

static int accept_boot_success(struct ab_metadata *metadata, int *source)
{
	u32 slot;

	if (readl(CONFIRM_MAGIC_ADDRESS) != CONFIRM_MAGIC)
		return CMD_RET_SUCCESS;
	slot = readl(CONFIRM_SLOT_ADDRESS);
	writel(0, CONFIRM_MAGIC_ADDRESS);
	writel(0, CONFIRM_SLOT_ADDRESS);
	if (slot > 1 || metadata->pending != slot) {
		printf("Lefony A/B: ignored stale success token for slot %u\n", slot);
		return CMD_RET_SUCCESS;
	}
	printf("Lefony A/B: accepting successful slot %c\n", 'A' + slot);
	metadata->active = slot;
	metadata->pending = NO_SLOT;
	metadata->attempts = 0;
	metadata->generation++;
	if (!commit_metadata(metadata, source)) {
		printf("ERROR: Lefony A/B success commit failed\n");
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
		printf("ERROR: Lefony A/B physical NAND geometry mismatch\n");
		return CMD_RET_FAILURE;
	}
	if (!read_metadata(&metadata, &source)) {
		printf("ERROR: Lefony A/B metadata is not provisioned\n");
		return CMD_RET_FAILURE;
	}
	if (accept_boot_success(&metadata, &source))
		return CMD_RET_FAILURE;

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
			       'A' + selected, metadata.attempts,
			       metadata.boot_limit);
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
		if (!pending_boot ||
		    rollback(&metadata, &source, "verification failed"))
			return CMD_RET_FAILURE;
		selected = metadata.active;
		if (!load_slot(selected, &metadata.slots[selected]))
			return CMD_RET_FAILURE;
	}
	set_handoff(selected, &metadata);
	printf("Lefony A/B: verified slot %c (%u bytes); booting\n",
	       'A' + selected, metadata.slots[selected].bytes);
	return CMD_RET_SUCCESS;
}

static int do_lefony_ab(cmd_tbl_t *cmdtp, int flag, int argc,
			char * const argv[])
{
	if (argc == 2 && !strcmp(argv[1], "boot"))
		return do_ab_boot();
	return CMD_RET_USAGE;
}

U_BOOT_CMD(
	lefony_ab, 2, 0, do_lefony_ab,
	"verify and select a physical Lefony OS A/B slot",
	"boot"
);
