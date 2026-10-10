.syntax unified
.thumb
.equ NEAR, 0x612c9c
.equ CAVE, 0x210d380
.equ APP, 0x21ef1e0

.macro jump destination
    ldr.w r12, 2f
1:  add r12, pc
    bx r12
    .balign 4
2:  .word (\destination + 1) - (CAVE + (1b - guard_entry) + 4)
.endm

.section .text.search_near,"ax",%progbits
.thumb_func
near_entry:
    ldr.w r12, 2f
1:  add r12, pc
    bx r12
    .balign 4
2:  .word (CAVE + 1) - (NEAR + (1b - near_entry) + 4)
.thumb_func
near_parent:
    ldr.w r12, 2f
1:  add r12, pc
    bx r12
    .balign 4
2:  .word (CAVE + 0x3c + 1) - (NEAR + (1b - near_entry) + 4)
.thumb_func
near_child:
    ldr.w r12, 2f
1:  add r12, pc
    bx r12
    .balign 4
2:  .word (CAVE + 0x64 + 1) - (NEAR + (1b - near_entry) + 4)

.section .text.search_guard,"ax",%progbits
.thumb_func
guard_entry:
    push.w {r0-r3,r12,lr}
    ldr r0, .Lapp_delta
.Lapp_add:
    add r0, pc
    ldr r0, [r0]
    cbz r0, .Lstale
    ldr r0, [r0,#8]
    cbz r0, .Lstale
    ldr r0, [r0,#0x34]
    cbz r0, .Lstale
    ldr r1, [sp]
    ldr r1, [r1,#0x40]
    cmp r0, r1
    bne .Lstale
    pop.w {r0-r3,r12,lr}
    push {r4-r7,lr}
    add r7, sp, #12
    jump 0xe27424
.Lstale:
    pop.w {r0-r3,r12,lr}
    bx lr
    .balign 4
.Lapp_delta:
    .word APP - (CAVE + (.Lapp_add - guard_entry) + 4)
.thumb_func
guard_parent:
    cbz r4, .Lmissing_parent
    adds r1, r4, #4
    add r0, sp, #8
    jump 0xe2745a
.Lmissing_parent:
    movs r0, #0
    str r0, [sp,#8]
    str r0, [sp,#12]
    jump 0xe27460
.thumb_func
guard_child:
    ldr r0, [sp,#8]
    cbz r0, .Lmissing_child
    movs r1, #1
    jump 0xe2749e
.Lmissing_child:
    jump 0xe2766e
