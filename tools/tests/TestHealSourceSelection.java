/** Pure host argument tests. No VM attachment, memory access or input. Compile
 * alongside NativeCampaignMarkers.java and InspectNativeInput.java. */
public class TestHealSourceSelection {
  static void check(boolean condition) {if(!condition)throw new AssertionError();}
  static void refuse(String... args) {
    try {InspectNativeInput.parseHealSourceSelection(args);throw new AssertionError("Accepted unsafe selection");}
    catch(IllegalArgumentException expected) {}
  }
  public static void main(String[] ignored) {
    check(InspectNativeInput.parseHealSourceSelection(new String[]{"8701","--episode-badge","--frame"})==null);
    check(InspectNativeInput.parseHealSourceSelection(new String[]{"8701","--episode-skills","--frame"})==null);
    var bright=InspectNativeInput.parseHealSourceSelection(new String[]{"8701","--episode-skills","--frame","--heal-source-ref=C049","--heal-source-serial=1000018"});
    check(bright.ref().equals("C049")&&bright.serial()==1000018L);
    var tyltyl=InspectNativeInput.parseHealSourceSelection(new String[]{"8701","--episode-skills","--frame","--heal-source-serial=1000005","--heal-source-ref=C004"});
    check(tyltyl.ref().equals("C004")&&tyltyl.serial()==1000005L);
    for(String mode:new String[]{"--episode-badge","--episode-touch","--cards"})
      refuse("8701",mode,"--frame","--heal-source-ref=C049","--heal-source-serial=1000018");
    refuse("8701","--episode-skills","--heal-source-ref=C049","--heal-source-serial=1000018");
    refuse("8701","--episode-skills","--frame","--heal-source-ref=C049");
    refuse("8701","--episode-skills","--frame","--heal-source-serial=1000018");
    refuse("8701","--episode-skills","--frame","--heal-source-ref=C049","--heal-source-ref=C049");
    refuse("8701","--episode-skills","--frame","--heal-source-serial=1000018","--heal-source-serial=1000018");
    refuse("8701","--episode-skills","--frame","--heal-source-ref=C005","--heal-source-serial=1000018");
    for(String serial:new String[]{"0","-1","01000018","+1000018","4294967296","99999999999","1e6",""})
      refuse("8701","--episode-skills","--frame","--heal-source-ref=C049","--heal-source-serial="+serial);
    refuse("8701","--episode-skills","--frame","--heal-source-ref=C049","--heal-source-serial=1000018","extra");
    refuse("--heal-source-ref=C049","--episode-skills","--frame","extra","--heal-source-serial=1000018");
    refuse("8701","--episode-skills","--frame","--heal-source-ref=C049","--heal-source-bogus=1000018");
    check(InspectNativeInput.parseHealSourceSelection(new String[]{"8701","--episode-skills","--frame","--heal-source-ref=C049","--heal-source-serial=4294967295"}).serial()==0xffffffffL);
    System.out.println("Heal source selection: closed refs, paired opt-in/frame-only CLI, low-word bounds and old default isolation passed; no native access.");
  }
}
