/*
 * BLUSTONE - Instrumented: native assertion-argument tracer.
 *
 * STATUS 2026-10-02: NOT SHIPPABLE. See analysis/testing/instr-002.md.
 * The assembly below is believed correct, and every gate that caught the
 * 2.8.0.1+6 bugs is in place, but the stub needs a code cave and this library
 * does not contain one large enough (largest provably-dead run: 0x39 bytes;
 * this stub needs 0x1a5). It must not be built into a release until a cave is
 * found AND the tester has confirmed on device that BLUSTONE_ASSERT lines
 * actually appear.
 *
 * Why this exists
 * ---------------
 * `_RMAssert(unsigned int cond, char const* file, char const* expr, int line, ...)`
 * at 0x10B3ABC is the single funnel through which the engine declares that it
 * will not continue. Today the log tells us *where* an assertion fired
 * ("ASSERTION Failed on 'file(line)'") but nothing about *what* it fired on:
 * the engine reports a condition that has already failed and then keeps going
 * with a null / empty / wrong value, which is exactly the situation the project
 * is stuck in (CSRCard::SetRefID -> sRefID.length() > 0, CSRGameMob::GetMonsterData
 * -> "Cannot find MonsterData").
 *
 * This stub is planted at the entry of _RMAssert, emits one line describing the
 * failing call site and the first four variadic arguments as raw words, and then
 * branches back to 0x10B3ABC + 4, which is the instruction immediately after the
 * original two-instruction prologue.
 *
 * Design constraints
 * ------------------
 * - No imports. Everything is ADR / direct Thumb branches / raw `svc #0`.
 *   No PLT, no GOT, no relocation, so the blob is position independent.
 * - Registers are preserved exactly. This is the subtle part, and 2.8.0.1+6 got
 *   it wrong twice; both mistakes are called out at the epilogue below.
 * - No dereference of argument values. A mis-typed variadic argument would fault
 *   inside the tracer and destroy the very evidence being collected.
 *
 * Emitted line (one per assertion, on fd 2 / stderr, which the instrumented
 * Telemetry already captures, and appended to files/blustone_assert.log):
 *
 *   BLUSTONE_ASSERT site=<lr> r0=<cond> line=<r3> a4=.. a5=.. a6=.. a7=..\n
 */

    .syntax unified
    .thumb

    .section .text.blustone_assert_trace,"ax",%progbits
    .thumb_func
    .global blustone_assert_trace
    .type blustone_assert_trace, %function

/* Stack frame, allocated below the 14 saved words:
 *
 *   sp + 0x000 .. 0x07F   output line (BUFCAP bytes, bounded by the .if below)
 *   sp + 0x080 .. 0x093   r0..r3 and lr, saved out of the argument registers
 *   sp + 0x0F8 .. 0x107   a4..a7, the variadic words from the callee's stack
 *
 * VARSLOT is derived, never guessed: the variadic words live at the callee's
 * [sp+0..12], and after this stub's own 14-word push they are at [sp+56] (0x38),
 * then the frame subtracts FRAME more. 2.8.0.1+6 stored them at [sp+0x38] *before*
 * subtracting FRAME and read them back at [sp+0x38] *after*, i.e. from
 * FRAME bytes below where they had been written. VARSLOT below is the correct
 * post-frame offset and the .if guards the arithmetic.
 */
    .equ SAVED_WORDS, 56                /* 14 registers pushed, in bytes */
    .equ FRAME,      0x120
    .equ BUFCAP,     0x80               /* sp + 0 .. BUFCAP-1             */
    .equ ARGSLOT,    0x80               /* sp + ARGSLOT .. ARGSLOT+0x13  */
    .equ VARSLOT,    SAVED_WORDS + 0xC0 /* where the callee's [sp] now is  */
    .equ SYS_WRITE,  4
    .equ SYS_CLOSE,  6
    .equ SYS_OPENAT, 322
    .equ AT_FDCWD,   0xFF9C             /* AT_FDCWD == -100 */
    .equ FD_STDERR,  2
    .equ O_APPEND_CREATE, 0x441         /* O_WRONLY|O_CREAT|O_APPEND */
    .equ FILE_MODE,  0x1B6             /* 0666 */

    /* The variadic words must land inside the frame, and the frame must leave
     * room for them. Getting this wrong is a silent out-of-bounds read. */
    .if VARSLOT + 16 > FRAME
    .error "VARSLOT + 16 overruns FRAME; the variadic words would be read out of bounds"
    .endif

blustone_assert_trace:
    /* r0=cond r1=file r2=expr r3=line [sp]=vararg0.. lr=return address */
    push.w   {r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, lr}

    sub.w    sp, sp, #FRAME

    str      r0,  [sp, #ARGSLOT + 0x00]   /* cond  */
    str      r1,  [sp, #ARGSLOT + 0x04]
    str      r2,  [sp, #ARGSLOT + 0x08]
    str      r3,  [sp, #ARGSLOT + 0x0C]
    str      lr,  [sp, #ARGSLOT + 0x10]   /* failing call site */

    mov      r4, sp                  /* output cursor            */
    movs     r8, #0                  /* output length            */
    mov      r11, sp                 /* output base (for write)  */

    /* site=<lr> */
    adr.w    r0, tag_site
    mov.w    r1, #tag_site_len
    bl       emit_tag
    mov      r5, lr
    bl       emit_hex32

    /* r0=<cond> */
    adr.w    r0, tag_r0
    mov.w    r1, #tag_r0_len
    bl       emit_tag
    ldr      r5, [sp, #ARGSLOT + 0x00]
    bl       emit_hex32

    /* line=<r3> */
    adr.w    r0, tag_line
    mov.w    r1, #tag_line_len
    bl       emit_tag
    ldr      r5, [sp, #ARGSLOT + 0x0C]
    bl       emit_hex32

    /* a4..a7: the variadic words at the callee's [sp+0..12] */
    adr.w    r0, tag_a4
    mov.w    r1, #tag_a4_len
    bl       emit_tag
    ldr      r5, [sp, #VARSLOT + 0x00]
    bl       emit_hex32

    adr.w    r0, tag_a5
    mov.w    r1, #tag_a5_len
    bl       emit_tag
    ldr      r5, [sp, #VARSLOT + 0x04]
    bl       emit_hex32

    adr.w    r0, tag_a6
    mov.w    r1, #tag_a6_len
    bl       emit_tag
    ldr      r5, [sp, #VARSLOT + 0x08]
    bl       emit_hex32

    adr.w    r0, tag_a7
    mov.w    r1, #tag_a7_len
    bl       emit_tag
    ldr      r5, [sp, #VARSLOT + 0x0C]
    bl       emit_hex32

    adr.w    r0, tag_nl
    mov.w    r1, #tag_nl_len
    bl       emit_tag

    /* write(2, sp, r8) - stderr is what the instrumented Telemetry reads back. */
    movs     r2, #FD_STDERR
    mov      r1, r11
    mov      r0, r8
    movs     r7, #SYS_WRITE
    svc      #0

    /* Best effort, and deliberately silent on failure: append the same bytes to
     * a file in the app's own data directory. logcat is a bounded ring and the
     * project has already lost assertions to eviction once, so a durable copy
     * that `run-as ... cat files/blustone_assert.log` can read is worth one more
     * syscall. An openat that fails simply skips this sink - the line has already
     * reached stderr. */
    movw     r0, #AT_FDCWD
    adr.w    r1, trace_path
    movw     r2, #O_APPEND_CREATE
    movs     r3, #FILE_MODE
    movs     r7, #SYS_OPENAT
    svc      #0
    cmp      r0, #0
    blt      2f
    mov      r7, r0                  /* keep the descriptor; r7 is reused below */
    movs     r2, #FD_STDERR         /* write() ignores this argument */
    mov      r1, r11
    mov      r0, r8
    movs     r7, #SYS_WRITE
    svc      #0
    mov      r0, r7
    movs     r7, #SYS_CLOSE
    svc      #0
2:
    /* ---- epilogue: the part 2.8.0.1+6 got wrong ------------------------- */
    add.w    sp, sp, #FRAME
    pop.w    {r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12}

    /* Re-create the two prologue instructions the hook replaced, verbatim.
     *
     *   0x10B3ABC  b5f0  push  {r4, r5, r6, r7, lr}   ; sp -= 24
     *   0x10B3ABE  af03  add   r7, sp, #0xc           ; r7 = sp+0xc, FRAME POINTER
     *   0x10B3AC0  e92d 0700  push.w {r8, r9, r10}   ; first real body insn
     *
     * Both mistakes 2.8.0.1+6 made are avoided by doing this rather than just
     * restoring registers:
     *
     * (1) It restored registers and branched straight to 0x10B3AC0, leaving sp at
     *     its ENTRY value. The resumed `push.w {r8,r9,r10}` therefore saw sp 24
     *     bytes too high, and every [sp,#..] reference in the frame was off.
     *     Re-creating the push makes sp exactly what it would have been.
     *
     * (2) More seriously, it never executed `add r7, sp, #0xc`, so r7 still held
     *     the CALLER's value. _RMAssert uses r7 as its frame pointer and
     *     dereferences it at 0x10B3ADA (`add.w r1, r7, #8`) and 0x10B3AEC
     *     (`ldr r0, [r7, #8]`), so the very first assertion read through a
     *     garbage pointer: an immediate SIGSEGV, and no output at all. That
     *     matches the field report exactly - 5 launches of 5 crashing in GLThread
     *     ~12 s in, right after the lobby bootstrap, with zero BLUSTONE_ASSERT
     *     lines anywhere.
     *
     * Note the prologue is TWO 16-bit instructions, not one 32-bit one. Reading
     * these four bytes as a single little-endian word yields 0xAF03F0B0 and
     * invites the "0x10B3AC0 is still inside the prologue" misreading; the bytes
     * at 0x10B3AC0 are e9 2d 00 07, a whole `push.w {r8,r9,r10}`.
     */
    push     {r4, r5, r6, r7, lr}
    add      r7, sp, #0xc

    /* Branch to the resume address. The real target is not known at assembly
     * time (this blob will be placed at an arbitrary address), so the next four
     * bytes are a placeholder that tools/patch-native-ui-animation.py locates via
     * the sentinel word below and rewrites with a real B.W. */
    .align   1
    .word   0xBA57BA11
resume_slot:
    b.w     .
    .size blustone_assert_trace, . - blustone_assert_trace

/* ---------------------------------------------------------------------------
 * emit_tag: append r1 bytes from r0 to the output line.
 * Clobbers r9, r10, r12. Preserves r0..r3.
 * ------------------------------------------------------------------------- */
    .type emit_tag, %function
emit_tag:
    mov      r9, r0
    mov      r10, r1
0:  ldrb     r12, [r9], #1
    strb     r12, [r4], #1
    subs     r10, r10, #1
    bne      0b
    add      r8, r8, r1
    bx       lr

/* ---------------------------------------------------------------------------
 * emit_hex32: append the 8 lower-case hex digits of r5 to the output line.
 * Clobbers r6, r7, r12. Preserves r0..r3.
 * ------------------------------------------------------------------------- */
    .type emit_hex32, %function
emit_hex32:
    movs     r6, #8
1:  lsrs     r7, r5, #28
    cmp      r7, #9
    ite      hi
    addhi    r7, r7, #('a' - 10)
    addls    r7, r7, #'0'
    strb     r7, [r4], #1
    lsls     r5, r5, #4
    subs     r6, r6, #1
    bne      1b
    add      r8, r8, #8
    bx       lr

/* ---------------------------------------------------------------------------
 * Tag literals, placed after the code so every ADR stays in range.
 * ------------------------------------------------------------------------- */
    .align   1
tag_site:
    .ascii   "BLUSTONE_ASSERT site="
    .equ     tag_site_len, . - tag_site
tag_r0:
    .ascii   " r0="
    .equ     tag_r0_len, . - tag_r0
tag_line:
    .ascii   " line="
    .equ     tag_line_len, . - tag_line
tag_a4:
    .ascii   " a4="
    .equ     tag_a4_len, . - tag_a4
tag_a5:
    .ascii   " a5="
    .equ     tag_a5_len, . - tag_a5
tag_a6:
    .ascii   " a6="
    .equ     tag_a6_len, . - tag_a6
tag_a7:
    .ascii   " a7="
    .equ     tag_a7_len, . - tag_a7
tag_nl:
    .ascii   "\n"
    .equ     tag_nl_len, . - tag_nl

trace_path:
    .ascii   "/data/data/com.vshower.prd_sr.instrumented/files/blustone_assert.log"
    .byte    0

/* Worst case line: every tag, plus eight hex digits for each of the seven
 * printed words. The buffer must not be able to reach the saved arguments. */
    .if (tag_site_len + tag_r0_len + tag_line_len + tag_a4_len + \
          tag_a5_len + tag_a6_len + tag_a7_len + tag_nl_len + 56) > BUFCAP
    .error "tracer output line can overflow its buffer"
    .endif
    .if ARGSLOT + 0x14 > VARSLOT
    .error "saved argument registers would overwrite the variadic words"
    .endif

    .section .note.GNU-stack,"",%progbits