#!/usr/bin/env python3
"""
Patch the serial number (and optionally the ANT+ device ID) in a
Wahoo KICKR CORE (nRF52832) flash dump.

Identity record = flash page 0x78000, 6 x uint32 little-endian:
  +0x00  unused (0xFFFFFFFF)
  +0x04  ANT+ device number (1..65534; 0xFFFFFFFF/0 -> firmware generates a random one)
  +0x08  byte 0 = factory flag, rest unused
  +0x0C  serial number (uint32, shown as "%09u" in BLE Device Information,
         and as "40" + "%09u" in the Wahoo app protocol)

By default it reads your own dump (flash_template.bin / uicr.bin) sitting next
to this script. Dump these from YOUR OWN trainer first (see README.md); the
shipped flash_template.bin has the serial / ANT+ ID erased, so patch in your
own values before flashing.

Usage:
  python3 patch_serial.py                        # just show current values
  python3 patch_serial.py 211002195              # set serial
  python3 patch_serial.py 211002195 --ant 12345  # also set ANT+ ID
  python3 patch_serial.py 211002195 --in my.bin  # patch a different dump

Writes flash_patched.bin and kickr_core_patched.hex (flash + UICR) next to
this script. The input dump is never modified.
"""
import argparse, os, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ID_PAGE = 0x78000
UICR_BASE = 0x10001000


def show(d, title):
    w = struct.unpack_from('<6I', d, ID_PAGE)
    print(f'{title}:')
    print(f'  serial       = {w[3]:09d}  (raw 0x{w[3]:08X})  -> app shows "40{w[3]:09d}"')
    print(f'  ANT+ ID      = {w[1]}  (raw 0x{w[1]:08X})')
    print(f'  factory flag = {d[ID_PAGE + 8]}')


def ihex(chunks):
    """chunks: list of (address, bytes). Returns Intel HEX text."""
    out, upper = [], None
    def rec(t, addr, data):
        b = bytes([len(data), (addr >> 8) & 0xFF, addr & 0xFF, t]) + data
        return ':' + (b + bytes([(-sum(b)) & 0xFF])).hex().upper()
    for base, data in chunks:
        for i in range(0, len(data), 16):
            part = data[i:i + 16]
            if part == b'\xff' * len(part):
                continue  # erased flash, no need to program
            a = base + i
            if a >> 16 != upper:
                upper = a >> 16
                out.append(rec(4, 0, struct.pack('>H', upper)))
            out.append(rec(0, a & 0xFFFF, part))
    out.append(':00000001FF')
    return '\n'.join(out) + '\n'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('serial', nargs='?', type=int, help='serial number (digits after the leading "40")')
    p.add_argument('--ant', type=int, help='ANT+ device ID 1..65534')
    p.add_argument('--in', dest='infile', default='flash_template.bin',
                   help='input flash dump (default: flash_template.bin)')
    p.add_argument('--uicr', default='uicr.bin',
                   help='input UICR dump (default: uicr.bin)')
    a = p.parse_args()

    infile = a.infile if os.path.isabs(a.infile) else os.path.join(HERE, a.infile)
    uicrfile = a.uicr if os.path.isabs(a.uicr) else os.path.join(HERE, a.uicr)
    flash = bytearray(open(infile, 'rb').read())
    uicr = open(uicrfile, 'rb').read()
    assert len(flash) == 0x80000, 'expected 512 KB nRF52832 flash dump'
    show(flash, 'Current dump')
    if a.serial is None:
        return

    if not 0 <= a.serial <= 0xFFFFFFFE:
        p.error('serial must fit in 32 bits')
    struct.pack_into('<I', flash, ID_PAGE + 0x0C, a.serial)
    if a.ant is not None:
        if not 1 <= a.ant <= 0xFFFE:
            p.error('ANT+ ID must be 1..65534')
        struct.pack_into('<I', flash, ID_PAGE + 0x04, a.ant)

    open(os.path.join(HERE, 'flash_patched.bin'), 'wb').write(flash)
    open(os.path.join(HERE, 'kickr_core_patched.hex'), 'w').write(
        ihex([(0, bytes(flash)), (UICR_BASE, uicr)]))
    show(flash, 'Patched')
    print('Wrote flash_patched.bin and kickr_core_patched.hex')


if __name__ == '__main__':
    main()
