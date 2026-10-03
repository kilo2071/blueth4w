// Persistent AirPods A2DP fix for the nano 7G 1.0.4: at boot (when the exploit glyph is
// rendered) write the 28-byte RTP-timestamp patch directly into osos .text at 0x082b2bb6,
// using the CFF put/write primitive (no host, no SCSI command). Also reinstall the SCSI
// RWX stub as a debug/escape hatch. See na-no CORRECTIONS.md / EXPLOIT_CONSTANTS_104.md.
use crate::payload::exploit_config::ExploitConfig;
use crate::payload::{CffPayloadBuilder, Payload};

#[derive(Default)]
pub struct BtPatchPayload {}

impl Payload for BtPatchPayload {
    fn build_cff<Cfg: ExploitConfig>(&self, b: &mut CffPayloadBuilder) {
        // plenty of headroom for the blind writes
        b.index_write(Cfg::OFFSET_BUILDCHAR_LEN_PTR, i32::MAX as u32);

        // --- 1) BT RTP-timestamp patch: 8 aligned words @ 0x082b2bb4 ---
        // (preserves the original `ldr r1,[pc,#0x94]` @0x082b2bb4 and the first half of the
        //  next instruction @0x082b2bd2; replaces the VFP block @0x082b2bb6..0x082b2bd2 with
        //  `ldr r0,[r1,#4]; add.w r0,r0,ip,lsl #7; str r0,[r1,#4]; nop*10`).
        const BT_BASE: u32 = 0x082b_2bb4;
        const BT_WORDS: [u32; 8] = [
            0x6848_4925, 0x10cc_eb00, 0xbf00_6048, 0xbf00_bf00,
            0xbf00_bf00, 0xbf00_bf00, 0xbf00_bf00, 0xf8d4_bf00,
        ];
        // ONE base switch only. The CFF "set write base" writes array[OFFSET_BUILDCHAR_PTR];
        // after the first switch the array no longer points at the buildchar struct, so a
        // SECOND base switch would land at BT_BASE+OFFSET_BUILDCHAR_PTR*4 (inside the BT code)
        // instead of the pointer slot. So we write exactly one region: the BT patch.
        b.index_write(Cfg::OFFSET_BUILDCHAR_PTR, BT_BASE);
        for (idx, w) in BT_WORDS.iter().enumerate() {
            b.index_write_array(idx as u16 + Cfg::BUILDCHAR_WRITE_OFFSET / 4, w.to_le_bytes());
        }
    }
}
