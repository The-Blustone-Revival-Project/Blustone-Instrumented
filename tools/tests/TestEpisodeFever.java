/** Pure host tests; never attaches to a VM or reads game memory. */
public class TestEpisodeFever {
  static void check(boolean value) {if(!value)throw new AssertionError();}
  static void refuse(Runnable action) {
    try {action.run();throw new AssertionError("Unsafe fever qualification accepted");}
    catch(IllegalArgumentException|IllegalStateException expected) {}
  }
  public static void main(String[] ignored) {
    check(InspectNativeInput.parseEpisodeFeverMode(new String[]{"8701","--episode-fever","--frame"}));
    check(!InspectNativeInput.parseEpisodeFeverMode(new String[]{"8701","--episode-skills","--frame"}));
    check(!InspectNativeInput.parseEpisodeFeverMode(new String[]{"8701","--episode-badge","--frame"}));
    for(String[] args:new String[][]{{"8701","--episode-fever"},{"8701","--episode-fever","--touch"},
      {"8701","--episode-fever","--frame","extra"},{"8701","--episode-fever","--frame","--source-serial=1000018"},
      {"8701","--episode-fever","--frame","--heal-source-ref=C049","--heal-source-serial=1000018"}})
      refuse(()->InspectNativeInput.parseEpisodeFeverMode(args));
    long base=0x4000000L,control=0x20000000L,object=control+0x10;
    long vptr=base+0x213bd20L,cv=base+0x213b5ccL;
    InspectNativeInput.qualifyFeverImageOwner(base,object,control,vptr,cv,0);
    InspectNativeInput.qualifyFeverImageOwner(base,object,control,vptr,cv,3);
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,0,control,vptr,cv,0));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object,0,vptr,cv,0));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object+4,control,vptr,cv,0));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object+1,control+1,vptr,cv,0));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object,control,base+0x213baccL,cv,0));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object,control,vptr,base+0x2139540L,0));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object,control,vptr,cv,0xffffffffL));
    refuse(()->InspectNativeInput.qualifyFeverImageOwner(base,object,control,vptr,cv,0x80000000L));
    System.out.println("Episode fever: frame-only mode/default isolation and exact UIImage allocation/class/control/lifetime refusal passed; no native access.");
  }
}
