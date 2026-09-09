/* Read fixed SRC/clock registers or clock-guarded NAND status via native HID.
 * No kernel-driver detach, USB reset, firmware download, or arbitrary address
 * input is supported. The only output report requests SDP READ_REGISTER.
 * Build: clang -Wall -Wextra -Werror -framework IOKit -framework CoreFoundation
 *        scripts/capture_prime_g2_rom_hid.c -o build/capture-prime-rom-hid
 */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDManager.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    unsigned phase;
    uint32_t value;
    int error;
} Reply;

static uint32_t little32(const uint8_t *p)
{
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 |
           (uint32_t)p[3] << 24;
}

static void received(void *opaque, IOReturn result, void *sender,
                     IOHIDReportType type, uint32_t id,
                     uint8_t *bytes, CFIndex length)
{
    Reply *reply = opaque;
    (void)sender;
    if (result || type != kIOHIDReportTypeInput || length < 5 || bytes[0] != id) {
        reply->error = 1;
    } else if (reply->phase == 0 && id == 3 && little32(bytes + 1) == 0x56787856) {
        reply->phase = 1;
    } else if (reply->phase == 1 && id == 4) {
        reply->value = little32(bytes + 1);
        reply->phase = 2;
    } else {
        reply->error = 1;
    }
}

int main(int argc, char **argv)
{
    const uint32_t src_addresses[] = {0x020d8000, 0x020d8004, 0x020d8008, 0x020d801c,
                                  0x020d8040, 0x020d8044};
    const char *src_names[] = {"SRC_SCR", "SRC_SBMR1", "SRC_SRSR", "SRC_SBMR2",
                           "SRC_GPR9", "SRC_GPR10"};
    /* Documented control registers only: no gated NAND MMIO, FIFO reads,
     * read-to-clear status, or writes to clock controls. */
    const uint32_t clock_addresses[] = {0x020c4004, 0x020c400c, 0x020c4010,
        0x020c4014, 0x020c4018, 0x020c401c, 0x020c4024,
        0x020c4068, 0x020c4078, 0x020c4080,
        0x020c8000, 0x020c8010, 0x020c8030, 0x020c8100};
    const char *clock_names[] = {"CCM_CCDR", "CCM_CCSR", "CCM_CACRR",
        "CCM_CBCDR", "CCM_CBCMR", "CCM_CSCMR1", "CCM_CSCDR1",
        "CCM_CCGR0", "CCM_CCGR4", "CCM_CCGR6",
        "ANATOP_PLL_ARM", "ANATOP_PLL_USB1", "ANATOP_PLL_SYS", "ANATOP_PFD_528"};
    const uint32_t nand_addresses[] = {0x020c4078, 0x020c4080,
        0x01808000, 0x01808010, 0x01808020, 0x01808080, 0x01808090,
        0x01808160, 0x01808170, 0x01806000, 0x01806060,
        0x01806070, 0x01806080, 0x01806090, 0x018060b0};
    const char *nand_names[] = {"CCM_CCGR4", "CCM_CCGR6",
        "BCH_CTRL", "BCH_STATUS0", "BCH_MODE", "BCH_FLASH0LAYOUT0", "BCH_FLASH0LAYOUT1",
        "BCH_VERSION", "BCH_DEBUG1", "GPMI_CTRL0", "GPMI_CTRL1",
        "GPMI_TIMING0", "GPMI_TIMING1", "GPMI_TIMING2", "GPMI_STAT"};
    int clocks = argc == 2 && !strcmp(argv[1], "--clocks");
    const uint32_t dma_addresses[] = {0x020c4068, 0x01804000, 0x01804010,
        0x01804020, 0x01804030, 0x01804100, 0x01804110, 0x01804120,
        0x01804130, 0x01804140, 0x01804150, 0x01804160};
    const char *dma_names[] = {"CCM_CCGR0", "APBH_CTRL0", "APBH_CTRL1",
        "APBH_CTRL2", "APBH_CHANNEL_CTRL", "APBH_CH0_CURCMDAR", "APBH_CH0_NXTCMDAR",
        "APBH_CH0_CMD", "APBH_CH0_BAR", "APBH_CH0_SEMA", "APBH_CH0_DEBUG1", "APBH_CH0_DEBUG2"};
    int buffers = argc == 2 && !strcmp(argv[1], "--dma-buffers");
    int chain = buffers || (argc == 2 && !strcmp(argv[1], "--dma-chain"));
    int dma = chain || (argc == 2 && !strcmp(argv[1], "--dma-status"));
    int nand = argc == 2 && !strcmp(argv[1], "--nand-status");
    if (argc != 1 && !clocks && !nand && !dma) {
        fprintf(stderr, "Usage: %s [--clocks|--nand-status|--dma-status|--dma-chain|--dma-buffers]\n", argv[0]);
        return 2;
    }
    const uint32_t *addresses = dma ? dma_addresses : nand ? nand_addresses : clocks ? clock_addresses : src_addresses;
    const char **names = dma ? dma_names : nand ? nand_names : clocks ? clock_names : src_names;
    unsigned count = buffers ? 796 : chain ? 268 : dma ? 12 : nand ? 15 : clocks ? 14 : 6;
    const char *key = dma ? "dma_registers" : nand ? "nand_registers" : clocks ? "clock_registers" : "src_registers";
    uint32_t values[796] = {0}, chain_addresses[796] = {0};
    const char *chain_names[796];char ram_names[784][24];
    if (chain) {
        memcpy(chain_addresses, dma_addresses, sizeof(dma_addresses));
        memcpy(chain_names, dma_names, sizeof(dma_names));
        addresses = chain_addresses;names = chain_names;
    }
    int status = 1, vid = 0x15a2, pid = 0x0080;
    IOHIDManagerRef manager = IOHIDManagerCreate(kCFAllocatorDefault, 0);
    CFMutableDictionaryRef match = CFDictionaryCreateMutable(kCFAllocatorDefault, 0,
        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFNumberRef vendor = CFNumberCreate(NULL, kCFNumberIntType, &vid);
    CFNumberRef product = CFNumberCreate(NULL, kCFNumberIntType, &pid);
    CFDictionarySetValue(match, CFSTR(kIOHIDVendorIDKey), vendor);
    CFDictionarySetValue(match, CFSTR(kIOHIDProductIDKey), product);
    IOHIDManagerSetDeviceMatching(manager, match);
    CFRelease(vendor);
    CFRelease(product);
    CFRelease(match);
    IOReturn result = IOHIDManagerOpen(manager, kIOHIDOptionsTypeNone);
    if (result) {
        fprintf(stderr, "HID manager open failed: 0x%08x\n", result);
        CFRelease(manager);
        return 1;
    }
    CFSetRef devices = IOHIDManagerCopyDevices(manager);
    if (!devices || CFSetGetCount(devices) != 1) {
        fprintf(stderr, "Expected exactly one Prime ROM HID device\n");
        goto manager_done;
    }
    const void *device_value = NULL;
    CFSetGetValues(devices, &device_value);
    IOHIDDeviceRef device = (IOHIDDeviceRef)device_value;
    result = IOHIDDeviceOpen(device, kIOHIDOptionsTypeNone);
    if (result) {
        fprintf(stderr, "HID device open failed: 0x%08x\n", result);
        goto manager_done;
    }
    uint8_t buffer[1025] = {0};
    Reply reply = {0};
    IOHIDDeviceRegisterInputReportCallback(device, buffer, sizeof(buffer), received, &reply);
    IOHIDDeviceScheduleWithRunLoop(device, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);
    for (unsigned i = 0; i < count; i++) {
        if (buffers && i == 268) {
            unsigned matches = 0;uint32_t payload = 0, auxiliary = 0;
            for (unsigned word = 12; word + 8 < 268; word++) {
                if (((values[word + 1] >> 12) & 15) >= 6 &&
                    ((values[word + 3] >> 24) & 3) == 1 &&
                    (values[word + 5] & 0x1000) &&
                    values[word + 6] >= 2048 && values[word + 6] <= 2112) {
                    payload = values[word + 7];auxiliary = values[word + 8];matches++;
                }
            }
            if (matches != 1 || (payload & 3) || (auxiliary & 3) ||
                payload < 0x00900000u || payload > 0x0091f800u ||
                auxiliary < 0x00900000u || auxiliary > 0x0091ffc0u) {
                fprintf(stderr, "DMA buffers refused: ambiguous descriptor or buffers outside OCRAM\n");
                goto device_done;
            }
            for (unsigned word = 0; word < 528; word++) {
                uint32_t address = word < 512 ? payload + word * 4 : auxiliary + (word - 512) * 4;
                chain_addresses[268 + word] = address;
                snprintf(ram_names[256 + word], sizeof(ram_names[0]), "%s_%08x",
                         word < 512 ? "PAYLOAD" : "AUX", address);
                chain_names[268 + word] = ram_names[256 + word];
            }
        }
        if (chain && i == 12) {
            uint32_t cursor = values[5];
            /* MX6ULL on-chip SRAM is 0x00900000..0x0091ffff. Follow only
             * a stopped channel's aligned pointer, never arbitrary MMIO or
             * external RAM. Capture 768 bytes before and 256 after it. */
            if ((values[9] & 0x00ff0000u) || (cursor & 3) ||
                cursor < 0x00900300u || cursor > 0x0091ff00u) {
                fprintf(stderr, "DMA chain capture refused: active channel or pointer outside bounded OCRAM\n");
                goto device_done;
            }
            for (unsigned word = 0; word < 256; word++) {
                chain_addresses[12 + word] = cursor - 768 + word * 4;
                snprintf(ram_names[word], sizeof(ram_names[word]), "OCRAM_%08x", chain_addresses[12 + word]);
                chain_names[12 + word] = ram_names[word];
            }
        }
        if (dma && i == 1 && (values[0] & 0x30u) != 0x30u) {
            fprintf(stderr, "DMA status capture refused: APBHDMA clock gate is not enabled\n");
            goto device_done;
        }
        /* Require all documented NAND APB/core/interconnect clock gates in
         * always-on mode before touching the NAND register windows. Do not
         * attempt to enable them when the guard fails. */
        if (nand && i == 2 && ((values[0] & 0xff003000u) != 0xff003000u ||
                              (values[1] & 0x3c0u) != 0x3c0u)) {
            fprintf(stderr, "NAND status capture refused: clock gates are not all enabled\n");
            goto device_done;
        }
        /* Report ID 1, command 0x0101, BE address, format=32, count=4. */
        uint8_t command[17] = {1, 1, 1, 0, 0, 0, 0, 32, 0, 0, 0, 4};
        command[3] = addresses[i] >> 24;
        command[4] = addresses[i] >> 16;
        command[5] = addresses[i] >> 8;
        command[6] = addresses[i];
        memset(&reply, 0, sizeof(reply));
        result = IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, 1,
                                      command, sizeof(command));
        if (result) {
            fprintf(stderr, "READ_REGISTER %s submission failed: 0x%08x\n", names[i], result);
            goto device_done;
        }
        CFAbsoluteTime deadline = CFAbsoluteTimeGetCurrent() + 3;
        while (!reply.error && reply.phase != 2 && CFAbsoluteTimeGetCurrent() < deadline) {
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.05, true);
        }
        if (reply.error || reply.phase != 2) {
            fprintf(stderr, "READ_REGISTER %s reply failed: phase=%u error=%d\n",
                    names[i], reply.phase, reply.error);
            goto device_done;
        }
        values[i] = reply.value;
    }
    printf("{\"transport\":\"macOS IOHID\",\"%s\":{\n", key);
    for (unsigned i = 0; i < count; i++) {
        printf("\"%s\":{\"address\":\"0x%08x\",\"value\":\"0x%08x\"}%s\n",
               names[i], addresses[i], values[i], i + 1 == count ? "" : ",");
    }
    puts("}}");
    status = 0;
device_done:
    IOHIDDeviceUnscheduleFromRunLoop(device, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);
    IOHIDDeviceRegisterInputReportCallback(device, buffer, sizeof(buffer), NULL, NULL);
    IOHIDDeviceClose(device, 0);
manager_done:
    if (devices) CFRelease(devices);
    IOHIDManagerClose(manager, 0);
    CFRelease(manager);
    return status;
}
