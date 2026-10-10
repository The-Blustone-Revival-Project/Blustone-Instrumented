.syntax unified
.thumb
.equ ENTRY, 0xe1ffe4
.equ CAVE, 0x210d404
.equ PARTNER, 0x216f2ec

.section .text.empty_guide_entry,"ax",%progbits
.thumb_func
entry_veneer:
    ldr.w r12, 2f
1:  add r12, pc
    bx r12
2:  .word (CAVE + 1) - (ENTRY + (1b - entry_veneer) + 4)

.section .text.empty_guide_guard,"ax",%progbits
.thumb_func
guard_entry:
    push.w {r0-r7,r12,lr}
    cmp r0, #0
    beq original
    tst r0, #3
    bne original
    ldr r1, .Lvptr_delta
.Lvptr_add:
    add r1, pc
    ldr r2, [r0]
    cmp r1, r2
    bne original
    ldr r1, [r0,#0x6ac]
    ldr r2, [r0,#0x6b0]
    orrs r1, r2
    bne original
    ldr r2, [r0,#0x678]
    ldr r3, [r0,#0x67c]
    cmp r2, #4096
    blo original
    orr r1, r2, r3
    tst r1, #3
    bne original
    cmp r3, r2
    blo original
    subs r1, r3, r2
    cmp r1, #224
    bhi original
    movs r6, #0
.Lgroup:
    cmp r2, r3
    beq .Ldone
    subs r1, r3, r2
    cmp r1, #28
    blo original
    ldr r1, [r2]
    cmp r1, #3
    bhi original
    cmp r1, #2
    bne .Lnext_group
    movs r6, #1
    ldr r4, [r2,#0x10]
    ldr r5, [r2,#0x14]
    cmp r4, #0
    bne .Lrows
    cmp r5, #0
    bne original
    b .Lnext_group
.Lrows:
    cmp r4, #4096
    blo original
    orr r1, r4, r5
    tst r1, #3
    bne original
    cmp r5, r4
    blo original
    subs r1, r5, r4
    cmp r1, #1792
    bhi original
.Lrow:
    cmp r4, r5
    beq .Lnext_group
    subs r1, r5, r4
    cmp r1, #56
    blo original
    ldrb r1, [r4,#0x28]
    cmp r1, #0
    bne original
    adds r4, #56
    b .Lrow
.Lnext_group:
    adds r2, #28
    b .Lgroup
.Ldone:
    cmp r6, #1
    bne original
    // Fresh, valid virtual group, no available row: defer BEFORE allocation.
    pop.w {r0-r7,r12,lr}
    bx lr
original:
    pop.w {r0-r7,r12,lr}
    // Replay all twelve overwritten bytes; no PC-relative instructions here.
    push {r4-r7,lr}
    add r7, sp, #12
    push.w {r8-r11}
    sub sp, #188
    mov r5, r0
    ldr.w r12, .Lreturn_delta
.Lreturn_add:
    add r12, pc
    bx r12
    .balign 4
.Lvptr_delta:
    .word PARTNER - (CAVE + (.Lvptr_add - guard_entry) + 4)
.Lreturn_delta:
    .word (ENTRY + 12 + 1) - (CAVE + (.Lreturn_add - guard_entry) + 4)
