import java.util.*;

/** Pure host tests: no VM/native/memory/input access. */
public class TestNativeBattleControls {
  static void check(boolean value){if(!value)throw new AssertionError();}
  static void refuse(Runnable operation){try{operation.run();throw new AssertionError("Unsafe controls accepted");}catch(IllegalArgumentException|IllegalStateException expected){}}
  static NativeBattleControls.Visibility v(String n,int e,int l){return new NativeBattleControls.Visibility(n,e,l);}
  static List<NativeBattleControls.Visibility> panels(String shown){return NativeBattleControls.NORMAL_PANEL_NAMES.stream().map(n->v(n,n.equals(shown)?0:1,n.equals(shown)?0:1)).toList();}
  public static void main(String[] unused){
    check(NativeBattleControls.parseMode(new String[]{"8701","--episode-controls","--frame"}));
    for(String mode:List.of("--episode-fever","--episode-scene","--episode-skills","--episode-touch","--cards"))check(!NativeBattleControls.parseMode(new String[]{"8701",mode,"--frame"}));
    for(String[] args:new String[][]{{"8701","--episode-controls"},{"8701","--episode-controls","--touch"},
      {"8701","--episode-controls","--frame","--source-serial=1000018"},{"--episode-controls","--frame"},
      {"8701","--episode-scene","--episode-controls"},{"8701","--episode-controls-extra","--frame"},
      {"8701","--episode-controls=1","--frame"},{"8701","--episode-controls","--frame","--episode-controls"}})refuse(()->NativeBattleControls.parseMode(args));
    refuse(()->NativeBattleControls.parseMode(null));
    var auto=List.of(v("QUALIFIED_ROOT",0,0),v("AUTO_TOGGLE",0,0));
    var lockHidden=List.of(v("QUALIFIED_ROOT",0,0),v("AUTO_LOCK",1,1));
    var hiddenLock=v("PA_AUTO_LOCK",1,0); // Local visible, hidden by its own parent.
    for(var t:Map.of("PA_AUTO_ALL",NativeBattleControls.Mode.ALL,"PA_AUTO_DASH",NativeBattleControls.Mode.DASH,"PA_AUTO_OFF",NativeBattleControls.Mode.OFF).entrySet())
      check(NativeBattleControls.classifyQualified(auto,panels(t.getKey()),lockHidden,hiddenLock)==t.getValue());
    check(NativeBattleControls.Mode.ALL.setting().orElseThrow()==2);check(NativeBattleControls.Mode.DASH.setting().orElseThrow()==1);check(NativeBattleControls.Mode.OFF.setting().orElseThrow()==0);
    check(NativeBattleControls.Mode.LOCKED.setting().isEmpty());check(NativeBattleControls.Mode.ANCESTOR_HIDDEN.setting().isEmpty());
    var lockVisible=List.of(v("QUALIFIED_ROOT",0,0),v("AUTO_LOCK",0,0));
    check(NativeBattleControls.classifyQualified(auto,panels("NONE"),lockVisible,v("PA_AUTO_LOCK",1,1))==NativeBattleControls.Mode.NONE_VISIBLE);
    var autoHidden=List.of(v("QUALIFIED_ROOT",0,0),v("AUTO_TOGGLE",1,1));
    var hiddenPanels=NativeBattleControls.NORMAL_PANEL_NAMES.stream().map(n->v(n,1,n.equals("PA_AUTO_ALL")?0:1)).toList();
    check(NativeBattleControls.classifyQualified(autoHidden,hiddenPanels,lockVisible,v("PA_AUTO_LOCK",0,0))==NativeBattleControls.Mode.LOCKED);
    check(NativeBattleControls.classifyQualified(autoHidden,hiddenPanels,lockHidden,hiddenLock)==NativeBattleControls.Mode.ANCESTOR_HIDDEN);
    var inherited=List.of(v("QUALIFIED_ROOT",1,0),v("AUTO_TOGGLE",1,0));
    check(NativeBattleControls.classifyQualified(inherited,hiddenPanels,lockHidden,hiddenLock)==NativeBattleControls.Mode.ANCESTOR_HIDDEN);
    refuse(()->v("PA_AUTO_ALL",2,0));refuse(()->v("PA_AUTO_ALL",0,1));refuse(()->v("bad\nname",0,0));
    refuse(()->NativeBattleControls.classifyQualified(List.of(),panels("PA_AUTO_ALL"),lockHidden,hiddenLock));
    refuse(()->NativeBattleControls.classifyQualified(auto,panels("PA_AUTO_ALL").subList(0,2),lockHidden,hiddenLock));
    var duplicate=new ArrayList<>(panels("PA_AUTO_ALL"));duplicate.set(2,duplicate.get(0));refuse(()->NativeBattleControls.classifyQualified(auto,duplicate,lockHidden,hiddenLock));
    var legacy=new ArrayList<>(panels("PA_AUTO_ALL"));legacy.set(2,v("BT_AUTO",1,1));refuse(()->NativeBattleControls.classifyQualified(auto,legacy,lockHidden,hiddenLock));
    var multiple=new ArrayList<>(panels("PA_AUTO_ALL"));multiple.set(1,v("PA_AUTO_DASH",0,0));refuse(()->NativeBattleControls.classifyQualified(auto,multiple,lockHidden,hiddenLock));
    refuse(()->NativeBattleControls.classifyQualified(auto,panels("PA_AUTO_ALL"),lockVisible,v("PA_AUTO_LOCK",0,0)));
    refuse(()->NativeBattleControls.classifyQualified(List.of(v("ROOT",1,1),v("PARENT",0,0)),panels("PA_AUTO_ALL"),lockHidden,hiddenLock));
    refuse(()->NativeBattleControls.classifyQualified(auto,hiddenPanels,lockHidden,hiddenLock));
    refuse(()->NativeBattleControls.classifyQualified(auto,panels("PA_AUTO_ALL"),lockVisible,hiddenLock));
    refuse(()->NativeBattleControls.classifyQualified(auto,panels("PA_AUTO_ALL"),lockHidden,v("WRONG_LOCK",1,0)));
    System.out.println("Battle controls: exact frame-only mode, separate3-panel AUTO/LOCK ancestry, mode2/1/0 vs locked/hidden/none and unsafe-byte/duplicate/missing/legacy/multiple refusal passed; no native/input authority.");
  }
}
