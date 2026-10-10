.syntax unified
.thumb
.equ NEAR, 0x612c90
.equ CAVE, 0x210d320
.equ GET_STATE, 0xf8a956
.equ FIRST, 0xea25f6
.equ ORDINARY, 0xea2726
.equ TUTORIAL, 0xea27f8

.section .text.gym_near,"ax",%progbits
.thumb_func
gym_near:
    ldr.w r12, .Lnear_offset
.Lnear_add:
    add r12, pc
    bx r12
.balign 4
.Lnear_offset:
    .word (CAVE + 1) - (NEAR + (.Lnear_add - gym_near) + 4)

.section .text.gym_resume,"ax",%progbits
.thumb_func
gym_resume:
    // Eight words retain 8-byte AAPCS alignment for the GetState call.
    push.w {r0-r4, r11, r12, lr}
    cmp r0, #1
    ble .Lfallback
    cmp r10, #8
    bne .Lfallback
    cmp r8, #0xa8
    bne .Lfallback
    ldr r0, [r6, #0x24]
    movs r1, #8
    movs r2, #1
    ldr.w r12, .Lstate_offset
.Lstate_add:
    add r12, pc
    blx r12
    cmp r0, #1
    bhi .Lfallback
    pop.w {r0-r4, r11, r12, lr}
    ldr.w r12, .Ltutorial_offset
.Ltutorial_add:
    add r12, pc
    bx r12
.Lfallback:
    pop.w {r0-r4, r11, r12, lr}
    // Reproduce the overwritten CMP/BGT with the original state result.
    cmp r0, #1
    bgt .Lordinary
    ldr.w r12, .Lfirst_offset
.Lfirst_add:
    add r12, pc
    bx r12
.Lordinary:
    ldr.w r12, .Lordinary_offset
.Lordinary_add:
    add r12, pc
    bx r12
.balign 4
.Lstate_offset:
    .word (GET_STATE + 1) - (CAVE + (.Lstate_add - gym_resume) + 4)
.Ltutorial_offset:
    .word (TUTORIAL + 1) - (CAVE + (.Ltutorial_add - gym_resume) + 4)
.Lfirst_offset:
    .word (FIRST + 1) - (CAVE + (.Lfirst_add - gym_resume) + 4)
.Lordinary_offset:
    .word (ORDINARY + 1) - (CAVE + (.Lordinary_add - gym_resume) + 4)
