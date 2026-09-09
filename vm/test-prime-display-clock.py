"""Measure modeled LCDIF latch deadlines against actual programmed dividers."""
import importlib
from pathlib import Path
import tempfile

state = importlib.import_module('test-prime-g2-gpt-state')


def main():
    for pre, post, pixel in ((6, 5, 17600000), (8, 4, 16500000)):
        with tempfile.TemporaryDirectory(prefix='lf-lcdclock-') as folder:
            vm = state.VM(Path(folder), 'clock', None, preinitialized=True, panel=True)
            try:
                q = vm.q
                vm.qmp.execute('cont')
                q.writel(0x020c4070, 3 << 28)
                q.writel(0x020c4074, 3 << 10)
                q.writel(0x020c4038, (pre - 1) << 12)
                q.writel(0x020c4018, (post - 1) << 23)
                q.writel(0x021c8090, (1 << 18) | 1132)
                q.writel(0x021c8080, 264)
                q.writel(0x021c8040, 0x8f000040)
                q.writel(0x021c8050, 0x8f04b0c0)
                q.writel(0x021c8000, 1)
                period = 1000000000 * 1132 * 264 // pixel
                q.command(f'clock_step {period - 1}')
                assert q.readl(0x021c8040) == 0x8f000040, 'flip happened early'
                q.command('clock_step 1')
                assert q.readl(0x021c8040) == 0x8f04b0c0, 'flip missed programmed deadline'
                print(f'PASS: LCDIF {pixel} Hz pixel clock latches at {period} ns', flush=True)
            finally:
                vm.close()


if __name__ == '__main__':
    main()
