.syntax unified
.thumb
.fpu neon
.global boutique_zero_width_guard_body
.type boutique_zero_width_guard_body, %function
/* Proposal body only. A relocation-aware B.W to the original resume address
 * is appended by the host planner. No original code cave has been approved. */
boutique_zero_width_guard_body:
    push {r2}
    vmov r2, s4
    lsl.w r2, r2, #1
    cbnz r2, .Lpositive
    vmov s0, r2
    b .Lrestore
.Lpositive:
    vdiv.f32 s0, s0, s4
.Lrestore:
    pop {r2}
.size boutique_zero_width_guard_body, .-boutique_zero_width_guard_body
