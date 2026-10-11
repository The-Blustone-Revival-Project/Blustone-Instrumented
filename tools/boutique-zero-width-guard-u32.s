.syntax unified
.thumb
.fpu neon
.global boutique_zero_width_guard_u32_body
.type boutique_zero_width_guard_u32_body, %function
/* Context-specific: original VCvt.F32.U32 immediately before the hook ensures
 * s4 is +zero or a positive finite integer conversion. Never advertise -zero
 * handling for this smaller variant. Placement remains proposal-only. */
boutique_zero_width_guard_u32_body:
    push {r2}
    vmov r2, s4
    cbnz r2, .Lpositive
    vmov s0, r2
    b .Lrestore
.Lpositive:
    vdiv.f32 s0, s0, s4
.Lrestore:
    pop {r2}
.size boutique_zero_width_guard_u32_body, .-boutique_zero_width_guard_u32_body
