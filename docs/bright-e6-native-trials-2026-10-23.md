# Bright in Episode 6: native trials, no verified heal

The user restored BlueStacks and exclusive input resumed. Two CB0602 attempts
used the unchanged +15 APK and the Bright-enabled server revision 9882693
(139 groups, stamp 1634683). No reward, victory or healing success is claimed.

The first Episode formation was Nene, Bright, Captain, Mowgli and fixed Karl.
The editor's Back button returned to preparation with strength 34200. Unlike
the ordinary editor, this did not write SetDeck or change any saved server
deck. The fixed Karl remains an original Episode participant, not an owned
Hunter. The native party persisted within this client session on re-entry.

The new read-only observer qualified Bright C049/1000018 in a paused CB0602:
HP 1720, exact serial-map and concrete Hunter owner, camp 0, unique friendly
Rage group, SP 2.916827. Nene's HP was 324.208374. This was not enough for
cost 4. Bright subsequently became front after Nene died and also died.
The battle ended in the native loss dialogue. Its third option returned to
the E6 map; Story 04 remained uncleared. Ordinary attacks were sent as
bounded bursts, stopping on the loss screen.

For the second attempt the native editor placed Bright fourth: Nene,
Captain, Mowgli, Bright, fixed Karl. Removal leaves a hole; reselecting fills
the earliest hole. Dragging Captain to the empty second slot did not move
him. Removing/reselecting Captain and then Mowgli produced the desired order.
Back returned to the correct five-enemy preparation, strength 34200.

A second paused snapshot qualified Bright alive at HP 1720 and SP 4.287144;
Mowgli was front at HP 518.740234. Normal bench-heart contacts did not yield
an attributable Bright cut-in, Rage debit or HP-delivery proof. Between
observations the battle and moving bench positions advanced substantially;
fixed coordinates must not be treated as successful contacts. A subsequent
front-heart contact displayed the native message that Bomber and Support
Hunters can only use skills in the ornithopter. Bright front activation is
therefore explicitly refused; use a currently observed bench heart.

After all friendly bodies disappeared, the second attempt crashed rather
than reaching the loss dialogue. Native signal evidence:

- client PID 7068, render Thread-9, ARM signal 11, fault 0x271, r0 = 0;
- ARM PC library offset 0x7782b1, CMUpdatable::SetVisible;
- ARM LR library offset 0x9c298b, CSRGameBase::SetFeverLV;
- translated Houdini subsequently reported SIGSEGV at address 0.

The null visibility receiver is separate from the qualified Bright actor.
The exact fever UI lookup/lifetime needs investigation before more trials.
Do not label this a Bright skill crash or patch the heal graph from it.

Both attempts left the entire private state file byte-exact to the immediate
pretrial backup. After relaunch, all three game objects remained exact too.
Client 23461 freshly reached Village, AP 58/BP 10, 132 stars, no active battle
or observer. The server process/revision, profile and installed APK did not
change. JDWP 8701 still points to the dead PID and must be rebound before use.

Private evidence remains ignored under local/verification:
bright-e6-paused-before-20261023.txt,
bright-e6-second-contact-20261023.txt,
bright-e6-exit-logcat-20261023.txt.
The server's local/private trial backup is retained. No original app, phone,
DataDump, Docker, collector or inference service was changed.

The observer footer selectedSourceSerial=0 describes the legacy touch-source
field, not the explicit read-only heal selection. Use the explicit
"Episode heal source serial=1000018 ref=C049" line for this mode's identity;
inputAuthorization=none still applies. The C004 touch helper was not used.
